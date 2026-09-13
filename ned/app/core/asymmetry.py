"""Evidence Asymmetry Detector — NED's signature module.

The premise: a person in an anxious state will demand enormous proof before
accepting good news, and almost none before accepting bad news. This module
measures that gap instead of endorsing it, and prints both thresholds side by
side in the same vocabulary.

The score is composed of three sub-scores (documented in the README and exposed
in ``sub_scores``):

* ``weight_gap`` — ``(N − P) / (N + P)``: how far apart the two accepted
  weights are, as a bounded symmetric ratio.
* ``information_gap`` — the same ratio computed on the *information* each piece
  of evidence actually carries, which is where the asymmetry usually lives.
* ``categorical`` — whether both extreme conditions hold at once: the negative
  reading is near-maximal *and* the positive reading has been wiped out.
"""

from __future__ import annotations

from ned.app.core import parser as text_parser
from ned.app.core.models import (
    AsymmetryRequest,
    AsymmetryResult,
    AsymmetrySide,
    EvidenceSpan,
    Mode,
)
from ned.app.core.rules import RuleBook
from ned.app.core.scoring import (
    band_label,
    clamp,
    describe_evidence,
    information_content,
    negative_amplification,
    negative_mass,
    noisy_or,
    positive_mass,
    threshold_label,
)
from ned.app.core.verdict import VerdictEngine

#: Extra discount applied when the user's own interpretation already discounts
#: the evidence ("可能只是人好"), on top of the mode baseline.
SELF_DISCOUNT_PENALTY = 25.0

#: Prior discount multiplier used when the user states no interpretation of their
#: own. It encodes the classic asymmetric reading; it is an assumption, and it is
#: declared in ``rules/asymmetry.json`` rather than buried here.
DEFAULT_NEGATIVE_SIDE_POLARITIES: tuple[str, ...] = ("negative", "self_discount")


class EvidenceAsymmetryDetector:
    """Compares two evidence standards and reports the gap."""

    def __init__(self, book: RuleBook) -> None:
        self.book = book
        self.verdicts = VerdictEngine(book)

    # -- public API --------------------------------------------------------
    def compare_request(self, request: AsymmetryRequest) -> AsymmetryResult:
        """Handle an API request in any of its supported shapes."""

        if request.positive_text or request.negative_text:
            return self.compare(
                positive_text=request.positive_text or "",
                negative_text=request.negative_text or "",
                mode=request.mode,
                positive_interpretation=request.positive_interpretation,
                negative_interpretation=request.negative_interpretation,
            )
        if request.events:
            positives = [
                event
                for event in request.events
                if event.label == "positive"
                or (event.label == "auto" and self._polarity_of(event.text) == "positive")
            ]
            negatives = [
                event
                for event in request.events
                if event.label == "negative"
                or (event.label == "auto" and self._polarity_of(event.text) == "negative")
            ]
            return self.compare(
                positive_text=" ".join(event.text for event in positives),
                negative_text=" ".join(event.text for event in negatives),
                mode=request.mode,
                positive_interpretation=request.positive_interpretation,
                negative_interpretation=request.negative_interpretation,
            )
        if request.text:
            return self.from_text(request.text, mode=request.mode)
        # Pydantic-level validation should make this unreachable.
        return self.compare(positive_text="", negative_text="", mode=request.mode)

    def from_text(self, text: str, mode: Mode = "normal") -> AsymmetryResult:
        """Split free text into clauses and compare the two strongest sides."""

        best_positive: tuple[float, str] | None = None
        best_negative: tuple[float, str] | None = None
        for clause in text_parser.split_clauses(text):
            spans = text_parser.detect(clause, self.book)
            positive_score = positive_mass(spans)
            negative_score = max(negative_mass(spans), self._discount_weight(spans))
            if positive_score > 0 and (best_positive is None or positive_score > best_positive[0]):
                best_positive = (positive_score, clause)
            if negative_score > 0 and (best_negative is None or negative_score > best_negative[0]):
                best_negative = (negative_score, clause)
        return self.compare(
            positive_text=best_positive[1] if best_positive else "",
            negative_text=best_negative[1] if best_negative else "",
            mode=mode,
        )

    def from_analysis(
        self, text: str, mode: Mode, spans: list[EvidenceSpan]
    ) -> AsymmetryResult | None:
        """Build an asymmetry report from an already-parsed analysis.

        Returns ``None`` when the input only tells one side of the story.
        """

        positives = [span for span in spans if span.polarity == "positive"]
        negatives = [span for span in spans if span.polarity == "negative"]
        discounts = [span for span in spans if span.polarity == "self_discount"]
        if not positives or not (negatives or discounts):
            return None

        clauses = text_parser.split_clauses(text)
        positive_clause = self._clause_for(clauses, positives, "positive") or text

        negative_interpretation = ""
        positive_interpretation = ""
        if negatives:
            negative_clause = self._clause_for(clauses, negatives, "negative") or text
        else:
            negative_clause = self._clause_for(clauses, discounts, "self_discount") or text
            negative_interpretation = negative_clause
        if discounts:
            positive_interpretation = self._clause_for(clauses, discounts, "self_discount") or ""

        return self.compare(
            positive_text=positive_clause,
            negative_text=negative_clause,
            mode=mode,
            positive_interpretation=positive_interpretation,
            negative_interpretation=negative_interpretation,
        )

    def compare(
        self,
        *,
        positive_text: str,
        negative_text: str,
        mode: Mode = "normal",
        positive_interpretation: str = "",
        negative_interpretation: str = "",
    ) -> AsymmetryResult:
        """Compare two evidence standards and produce the report."""

        config = self.book.asymmetry
        positive = self._side(
            positive_text, "positive", mode, positive_interpretation, is_positive=True
        )
        negative = self._side(
            negative_text, "negative", mode, negative_interpretation, is_positive=False
        )
        language = self._language(positive_text, negative_text)

        if positive is None or negative is None:
            return AsymmetryResult(
                mode=mode,
                positive=positive,
                negative=negative,
                positive_threshold="UNKNOWN",
                negative_threshold="UNKNOWN",
                asymmetry_score=0.0,
                asymmetry_label="INSUFFICIENT_INPUT",
                reality_check=self.book.reality_check("asymmetry_insufficient", language, {}),
                sub_scores={},
                verdict=self.verdicts.decide(
                    {
                        "mode": mode,
                        "language": language,
                        "asymmetry_score": 0.0,
                        "positive_mass": 0.0,
                        "negative_mass": 0.0,
                        "negative_amplification": 0.0,
                        "has_positive": positive is not None,
                        "has_negative": negative is not None,
                        "polarity": "neutral",
                        "signal_type": "none",
                    }
                ),
                disclaimer=self.book.disclaimer,
            )

        weight_gap = _ratio(negative.weight - positive.weight, negative.weight + positive.weight)
        information_gap = _ratio(
            positive.information_content - negative.information_content,
            positive.information_content + negative.information_content,
        )
        categorical = self._categorical(positive.weight, negative.weight)
        score = round(
            clamp(
                100.0
                * (
                    config.weight_gap_weight * weight_gap
                    + config.information_gap_weight * information_gap
                    + config.categorical_weight * categorical
                )
            ),
            4,
        )
        reality_check = self.book.reality_check(
            "asymmetry_pair",
            language,
            {
                "positive_desc": self._describe(positive_text, "positive", language),
                "negative_desc": self._describe(
                    negative_text, "negative", language, include_discount=True
                ),
            },
        )
        verdict = self.verdicts.decide(
            {
                "mode": mode,
                "language": language,
                "asymmetry_score": score,
                "positive_mass": positive.weight,
                "negative_mass": negative.weight,
                "negative_amplification": negative.amplification_applied,
                "has_positive": positive.raw_strength > 0,
                "has_negative": negative.raw_strength > 0,
                "polarity": "negative",
                "signal_type": negative.signal_type.value,
            }
        )
        return AsymmetryResult(
            mode=mode,
            positive=positive,
            negative=negative,
            positive_threshold=threshold_label(positive.weight, positive_side=True, config=config),
            negative_threshold=threshold_label(negative.weight, positive_side=False, config=config),
            asymmetry_score=score,
            asymmetry_label=band_label(config.bands, score),
            reality_check=reality_check,
            sub_scores={
                "weight_gap": round(weight_gap, 4),
                "information_gap": round(information_gap, 4),
                "categorical": round(categorical, 4),
            },
            verdict=verdict,
            disclaimer=self.book.disclaimer,
        )

    # -- internals ---------------------------------------------------------
    def _categorical(self, positive_weight: float, negative_weight: float) -> float:
        config = self.book.asymmetry
        negative_high = 1.0 if negative_weight > config.categorical_negative_threshold else 0.0
        positive_wiped = 1.0 if positive_weight < config.categorical_positive_threshold else 0.0
        return (negative_high + positive_wiped) / 2.0

    def _polarity_of(self, text: str) -> str:
        spans = text_parser.detect(text, self.book)
        positives = positive_mass(spans)
        negatives = max(negative_mass(spans), self._discount_weight(spans))
        if positives > negatives and positives > 0:
            return "positive"
        if negatives > 0:
            return "negative"
        return "neutral"

    def _discount_weight(self, spans: list[EvidenceSpan]) -> float:
        """The user's own discounting language, treated as their rejection bar."""

        return noisy_or([span.weight for span in spans if span.polarity == "self_discount"])

    def _clause_for(
        self, clauses: list[str], spans: list[EvidenceSpan], polarity: str
    ) -> str | None:
        """Find the clause that produced these spans."""

        needles = [span.text for span in spans if span.polarity == polarity and span.text]
        for clause in clauses:
            if any(needle in clause for needle in needles):
                return clause
        return None

    def _spans_for(
        self, text: str, polarity: str, include_discount: bool = False
    ) -> list[EvidenceSpan]:
        wanted = {polarity}
        if include_discount:
            wanted.add("self_discount")
        return [span for span in text_parser.detect(text, self.book) if span.polarity in wanted]

    def _describe(
        self, text: str, polarity: str, language: str, include_discount: bool = False
    ) -> str:
        spans = self._spans_for(text, polarity, include_discount)
        if not spans:
            return text.strip() or "—"
        strongest = max(spans, key=lambda span: span.information_content)
        return describe_evidence(strongest, language, fallback=text.strip() or "—")

    def _language(self, positive_text: str, negative_text: str) -> str:
        for candidate in (positive_text, negative_text):
            language = text_parser.detect_language(candidate)
            if language != "unknown":
                return language
        return "en"

    def _side(
        self,
        text: str,
        polarity: str,
        mode: Mode,
        interpretation: str,
        *,
        is_positive: bool,
    ) -> AsymmetrySide | None:
        """Build one side of the comparison, or ``None`` if that side is absent."""

        if not text.strip():
            return None
        spans = text_parser.detect(text, self.book)
        config = self.book.asymmetry
        profile = self.book.mode(mode)
        language = text_parser.detect_language(text)

        if is_positive:
            positives = [span for span in spans if span.polarity == "positive"]
            if not positives:
                return None
            raw = positive_mass(positives)
            info = information_content(positives, "positive")
            discount = profile.discount_base
            prior = config.prior_positive_discount_multiplier
            if interpretation and self._has_self_discount(interpretation):
                # The user already discounted it themselves; NED does not need
                # the prior, it can use the discount they volunteered.
                discount = min(95.0, discount + SELF_DISCOUNT_PENALTY)
                prior = 1.0
            elif interpretation:
                prior = 0.5
            weight = clamp(raw * (1.0 - discount / 100.0) * prior)
            strongest = max(positives, key=lambda span: span.information_content)
            return AsymmetrySide(
                text=text,
                signal_type=strongest.signal_type,
                signal_label=strongest.label,
                raw_strength=round(raw, 4),
                weight=round(weight, 4),
                information_content=round(info, 4),
                description=describe_evidence(strongest, language),
                discount_applied=round(discount, 4),
                interpretation=interpretation,
            )

        negatives = [span for span in spans if span.polarity == "negative"]
        if not negatives:
            discounts = [span for span in spans if span.polarity == "self_discount"]
            if not discounts:
                return None
            raw = self._discount_weight(discounts)
            info = information_content(discounts, "self_discount")
            strongest = max(discounts, key=lambda span: span.base_strength)
            return AsymmetrySide(
                text=text,
                signal_type=strongest.signal_type,
                signal_label=strongest.label,
                raw_strength=round(raw, 4),
                weight=round(clamp(raw), 4),
                information_content=round(info, 4),
                description=describe_evidence(strongest, language),
                amplification_applied=round(negative_amplification(raw, info), 4),
                interpretation=interpretation,
            )

        raw = negative_mass(negatives)
        info = information_content(negatives, "negative")
        strongest = max(negatives, key=lambda span: span.base_strength)
        return AsymmetrySide(
            text=text,
            signal_type=strongest.signal_type,
            signal_label=strongest.label,
            raw_strength=round(raw, 4),
            weight=round(clamp(raw * config.prior_negative_amplification_multiplier), 4),
            information_content=round(info, 4),
            description=describe_evidence(strongest, language),
            amplification_applied=round(negative_amplification(raw, info), 4),
            interpretation=interpretation,
        )

    def _has_self_discount(self, text: str) -> bool:
        if not text:
            return False
        return any(span.polarity == "self_discount" for span in text_parser.detect(text, self.book))


def _ratio(numerator: float, denominator: float) -> float:
    """Bounded symmetric ratio, clamped to ``[0, 1]``."""

    if denominator <= 0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


__all__ = ["DEFAULT_NEGATIVE_SIDE_POLARITIES", "SELF_DISCOUNT_PENALTY", "EvidenceAsymmetryDetector"]
