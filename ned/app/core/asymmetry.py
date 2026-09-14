"""Evidence Comparison — three layers, three subjects.

The module used to fold three different things into one number and attribute the
result to the reader. It now reports them separately:

* :class:`EvidenceProfile` — **the clues.** Raw strength, information content and
  evidence class of each side, plus the two pairwise gaps. Self-authored framing
  (``self_discount``, ``self_negative_belief``) is *not* evidence and never
  enters this layer. No policy, no second person.
* :class:`NedTreatment` — **what NED does.** The mode's discount, its configured
  priors and the weights it derives from them. Everything here is about NED.
* :class:`UserInterpretation` — **the reader's own words.** Populated only from
  self-discount language and self-authored negative conclusions (plus an
  interpretation supplied through the API). This is the only layer allowed to say
  anything about the reader's standard, and it requires a real basis to do so.

``asymmetry_score`` and ``sub_scores`` remain as the **legacy composite** (see
``_legacy_composite``): they mix the layers on purpose, are computed exactly as
before, and are never used by the new layers, verdicts, personality copy or UI.
"""

from __future__ import annotations

from typing import cast

from ned.app.config import AsymmetryConfig, ModeProfile
from ned.app.core import parser as text_parser
from ned.app.core.models import (
    AsymmetryRequest,
    AsymmetryResult,
    AsymmetrySide,
    EvidenceProfile,
    EvidenceSpan,
    Mode,
    NedTreatment,
    SignalType,
    UserInterpretation,
    UserReadingStatus,
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

#: Signal types that describe the reader's own framing rather than the other
#: person's behaviour. They belong to User Interpretation, never to evidence.
SELF_FRAMING_SIGNAL_TYPES: tuple[SignalType, ...] = (
    SignalType.SELF_NEGATIVE_BELIEF,
    SignalType.SELF_DISCOUNT,
)

#: Reasons a comparison is declined instead of scored.
REASON_INSUFFICIENT_INPUT = "insufficient_input"
#: Both sides have something, but at least one has no external evidence: only the
#: reader's own framing sits there, so there is nothing to compare.
REASON_MISSING_EXTERNAL_EVIDENCE = "missing_external_evidence"
REASON_EXPLICIT_BOUNDARY = "explicit_boundary_not_comparable"
REASON_TEMPORAL_STATE_CHANGE = "temporal_state_change_not_comparable"


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
            reading_text=text,
        )

    def from_analysis(
        self, text: str, mode: Mode, spans: list[EvidenceSpan]
    ) -> AsymmetryResult | None:
        """Build an asymmetry report from an already-parsed analysis.

        Returns ``None`` when the input only tells one side of the story.
        """

        external_positive = [span for span in spans if span.polarity == "positive"]
        external_negative = [
            span
            for span in spans
            if span.polarity == "negative"
            and span.signal_type is not SignalType.SELF_NEGATIVE_BELIEF
        ]
        reader_positive = [span for span in spans if span.polarity == "self_discount"]
        reader_negative = [
            span for span in spans if span.signal_type is SignalType.SELF_NEGATIVE_BELIEF
        ]

        if not (external_positive or reader_positive) or not (external_negative or reader_negative):
            return None

        clauses = text_parser.split_clauses(text)
        positive_clause = self._clause_with(clauses, external_positive or reader_positive) or text
        negative_clause = self._clause_with(clauses, external_negative or reader_negative) or text

        return self.compare(
            positive_text=positive_clause,
            negative_text=negative_clause,
            mode=mode,
            reading_text=text,
        )

    def compare(
        self,
        *,
        positive_text: str,
        negative_text: str,
        mode: Mode = "normal",
        positive_interpretation: str = "",
        negative_interpretation: str = "",
        reading_text: str = "",
    ) -> AsymmetryResult:
        """Compare two clues and report the three layers separately.

        ``reading_text`` is scanned for the reader's own language only; it never
        contributes evidence. The engine passes the whole message there so a
        self-discount in one clause is still attributed to the right side.
        """

        config = self.book.asymmetry
        profile = self.book.mode(mode)
        language = self._language(positive_text, negative_text)

        positive = self._profile_side(positive_text, "positive", language, profile, config)
        negative = self._profile_side(negative_text, "negative", language, profile, config)
        reading = self._user_reading(
            positive_text,
            negative_text,
            positive_interpretation,
            negative_interpretation,
            reading_text,
        )

        if (positive is None and not reading["positive_present"]) or (
            negative is None and not reading["negative_present"]
        ):
            return self._insufficient_result(
                mode, language, positive, negative, reading, profile, config
            )

        applicable, reason = self._comparability(positive, negative)
        interpretation = self._interpretation(reading, applicable)
        legacy_score, legacy_sub_scores = self._legacy_composite(
            positive_text, negative_text, mode, positive_interpretation, negative_interpretation
        )
        reality_check = self.book.reality_check(
            self._comparison_check_id(applicable, reason),
            language,
            {
                "positive_desc": self._describe(positive_text, "positive", language),
                "negative_desc": self._describe(negative_text, "negative", language),
            },
        )
        verdict = self.verdicts.decide(
            {
                "mode": mode,
                "language": language,
                "comparison_context": True,
                "comparison_applicable": applicable,
                "user_double_standard": interpretation.double_standard,
                "user_reading_present": interpretation.reading_present,
                "positive_mass": positive.raw_strength if positive is not None else 0.0,
                "negative_mass": negative.raw_strength if negative is not None else 0.0,
                "negative_amplification": (
                    negative.amplification_applied if negative is not None else 0.0
                ),
                "has_positive": positive is not None,
                "has_negative": negative is not None,
                "polarity": "negative",
                "signal_type": negative.signal_type.value if negative is not None else "none",
            }
        )
        return AsymmetryResult(
            mode=mode,
            positive=positive,
            negative=negative,
            positive_threshold=(
                threshold_label(positive.weight, positive_side=True, config=config)
                if applicable and positive is not None
                else config.comparability.threshold_label
            ),
            negative_threshold=(
                threshold_label(negative.weight, positive_side=False, config=config)
                if applicable and negative is not None
                else config.comparability.threshold_label
            ),
            asymmetry_score=legacy_score,
            asymmetry_label=self._legacy_label(legacy_score, applicable, config),
            comparison_applicable=applicable,
            comparison_reason=reason,
            evidence_profile=self._evidence_profile(positive, negative, applicable, reason),
            ned_treatment=self._treatment(mode, positive, negative, profile, config, applicable),
            user_interpretation=interpretation,
            reality_check=reality_check,
            sub_scores=legacy_sub_scores,
            verdict=verdict,
            disclaimer=self.book.disclaimer,
        )

    # -- layers ------------------------------------------------------------
    def _evidence_profile(
        self,
        positive: AsymmetrySide | None,
        negative: AsymmetrySide | None,
        applicable: bool,
        reason: str,
    ) -> EvidenceProfile:
        """The clues themselves: no policy, no reader, no second person."""

        positive_raw = positive.raw_strength if positive is not None else None
        negative_raw = negative.raw_strength if negative is not None else None
        positive_info = positive.information_content if positive is not None else None
        negative_info = negative.information_content if negative is not None else None
        raw_gap: float | None = None
        info_gap: float | None = None
        if applicable and positive_raw is not None and negative_raw is not None:
            raw_gap = _ratio(negative_raw - positive_raw, negative_raw + positive_raw)
        if applicable and positive_info is not None and negative_info is not None:
            info_gap = _ratio(positive_info - negative_info, positive_info + negative_info)
        return EvidenceProfile(
            comparable=applicable,
            comparison_reason=reason,
            positive_class=positive.evidence_class if positive is not None else "",
            negative_class=negative.evidence_class if negative is not None else "",
            positive_raw_strength=positive_raw,
            negative_raw_strength=negative_raw,
            positive_information=positive_info,
            negative_information=negative_info,
            raw_strength_gap=raw_gap,
            information_gap=info_gap,
        )

    def _treatment(
        self,
        mode: Mode,
        positive: AsymmetrySide | None,
        negative: AsymmetrySide | None,
        profile: ModeProfile,
        config: AsymmetryConfig,
        applicable: bool,
    ) -> NedTreatment:
        """What the current mode does to evidence. About NED, never the reader."""

        discount = profile.discount_base
        prior_positive = config.prior_positive_discount_multiplier
        prior_negative = config.prior_negative_amplification_multiplier
        return NedTreatment(
            mode=mode,
            positive_discount=round(discount, 4),
            prior_positive=prior_positive,
            prior_negative=prior_negative,
            positive_treated_weight=(
                round(clamp(positive.raw_strength * (1.0 - discount / 100.0) * prior_positive), 4)
                if positive is not None
                else None
            ),
            negative_treated_weight=(
                round(clamp(negative.raw_strength * prior_negative), 4)
                if negative is not None
                else None
            ),
            negative_amplification=(
                round(
                    negative_amplification(negative.raw_strength, negative.information_content), 4
                )
                if negative is not None
                else None
            ),
            treatment_gap=(
                _ratio(
                    negative.raw_strength * prior_negative
                    - positive.raw_strength * (1.0 - discount / 100.0) * prior_positive,
                    negative.raw_strength * prior_negative
                    + positive.raw_strength * (1.0 - discount / 100.0) * prior_positive,
                )
                if applicable and positive is not None and negative is not None
                else None
            ),
        )

    def _interpretation(self, reading: dict[str, object], applicable: bool) -> UserInterpretation:
        """The reader's own words — and only when they are actually there."""

        positive_present = bool(reading["positive_present"])
        negative_present = bool(reading["negative_present"])
        status: UserReadingStatus
        if not applicable:
            status = "not_comparable"
        elif positive_present and negative_present:
            status = "asymmetric_standard_detected"
        elif positive_present or negative_present:
            status = "partial_basis"
        else:
            status = "not_present"
        return UserInterpretation(
            status=status,
            reading_present=positive_present or negative_present,
            positive_self_discount_present=positive_present,
            negative_self_conclusion_present=negative_present,
            basis=[str(code) for code in cast("list[object]", reading["basis"])],
            positive_reading=cast("str | None", reading["positive_reading"]),
            negative_reading=cast("str | None", reading["negative_reading"]),
            double_standard=status == "asymmetric_standard_detected",
            interpretive_score=None,
        )

    def _insufficient_result(
        self,
        mode: Mode,
        language: str,
        positive: AsymmetrySide | None,
        negative: AsymmetrySide | None,
        reading: dict[str, object],
        profile: ModeProfile,
        config: AsymmetryConfig,
    ) -> AsymmetryResult:
        """One side has nothing at all: there is no comparison to make."""

        interpretation = self._interpretation(reading, applicable=False)
        return AsymmetryResult(
            mode=mode,
            positive=positive,
            negative=negative,
            positive_threshold="UNKNOWN",
            negative_threshold="UNKNOWN",
            asymmetry_score=None,
            asymmetry_label="INSUFFICIENT_INPUT",
            comparison_applicable=False,
            comparison_reason=REASON_INSUFFICIENT_INPUT,
            evidence_profile=self._evidence_profile(
                positive, negative, False, REASON_INSUFFICIENT_INPUT
            ),
            ned_treatment=self._treatment(mode, positive, negative, profile, config, False),
            user_interpretation=interpretation,
            reality_check=self.book.reality_check("asymmetry_insufficient", language, {}),
            sub_scores={},
            verdict=self.verdicts.decide(
                {
                    "mode": mode,
                    "language": language,
                    "legacy_asymmetry_score": 0.0,
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

    # -- legacy ------------------------------------------------------------
    def _legacy_composite(
        self,
        positive_text: str,
        negative_text: str,
        mode: Mode,
        positive_interpretation: str,
        negative_interpretation: str,
    ) -> tuple[float | None, dict[str, float]]:
        """The original composite, reproduced exactly for historical clients.

        It mixes evidence properties with NED policy and folds in the reader's own
        discount, which is precisely why it is no longer authoritative.
        """

        config = self.book.asymmetry
        legacy_positive = self._legacy_side(
            positive_text, "positive", mode, positive_interpretation, is_positive=True
        )
        legacy_negative = self._legacy_side(
            negative_text, "negative", mode, negative_interpretation, is_positive=False
        )
        if legacy_positive is None or legacy_negative is None:
            return None, {}
        weight_gap = _ratio(
            legacy_negative.weight - legacy_positive.weight,
            legacy_negative.weight + legacy_positive.weight,
        )
        information_gap = _ratio(
            legacy_positive.information_content - legacy_negative.information_content,
            legacy_positive.information_content + legacy_negative.information_content,
        )
        categorical = self._categorical(legacy_positive.weight, legacy_negative.weight)
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
        applicable, _ = self._comparability(legacy_positive, legacy_negative)
        return (score if applicable else None), {
            "weight_gap": round(weight_gap, 4),
            "information_gap": round(information_gap, 4),
            "categorical": round(categorical, 4),
        }

    @staticmethod
    def _legacy_label(score: float | None, applicable: bool, config: AsymmetryConfig) -> str:
        if not applicable or score is None:
            return config.comparability.not_applicable_label
        return band_label(config.bands, score)

    @staticmethod
    def _comparison_check_id(applicable: bool, reason: str) -> str:
        if applicable:
            return "asymmetry_pair"
        if reason == REASON_TEMPORAL_STATE_CHANGE:
            return "comparison_temporal_not_applicable"
        return "comparison_not_applicable"

    def _user_reading(
        self,
        positive_text: str,
        negative_text: str,
        positive_interpretation: str,
        negative_interpretation: str,
        reading_text: str,
    ) -> dict[str, object]:
        """Collect the reader's own language. Evidence is not involved."""

        scanned = reading_text or f"{positive_text}\n{negative_text}"
        spans = text_parser.detect(scanned, self.book) if scanned.strip() else []
        discount = next((span for span in spans if span.polarity == "self_discount"), None)
        conclusion = next(
            (span for span in spans if span.signal_type is SignalType.SELF_NEGATIVE_BELIEF), None
        )

        basis: list[str] = []
        if discount is not None:
            basis.append("positive_self_discount")
        if positive_interpretation.strip():
            basis.append("positive_interpretation_supplied")
        if conclusion is not None:
            basis.append("negative_self_conclusion")
        if negative_interpretation.strip():
            basis.append("negative_interpretation_supplied")

        return {
            "positive_present": discount is not None or bool(positive_interpretation.strip()),
            "negative_present": conclusion is not None or bool(negative_interpretation.strip()),
            "basis": basis,
            "positive_reading": (
                discount.text if discount is not None else (positive_interpretation.strip() or None)
            ),
            "negative_reading": (
                conclusion.text
                if conclusion is not None
                else (negative_interpretation.strip() or None)
            ),
        }

    def _profile_side(
        self,
        text: str,
        polarity: str,
        language: str,
        profile: ModeProfile,
        config: AsymmetryConfig,
    ) -> AsymmetrySide | None:
        """One side of the Evidence Profile, built from external evidence only."""

        if not text.strip():
            return None
        spans = self._external_spans(text, polarity)
        if not spans:
            return None
        raw = noisy_or([span.weight for span in spans])
        info = noisy_or([span.information_content for span in spans])
        strongest = max(spans, key=lambda span: (span.base_strength, span.information_content))
        discount = profile.discount_base
        prior_positive = config.prior_positive_discount_multiplier
        prior_negative = config.prior_negative_amplification_multiplier
        if polarity == "positive":
            return AsymmetrySide(
                text=text,
                signal_type=strongest.signal_type,
                signal_label=strongest.label,
                evidence_class=self._class_of(strongest.signal_type.value),
                raw_strength=round(raw, 4),
                weight=round(clamp(raw * (1.0 - discount / 100.0) * prior_positive), 4),
                information_content=round(info, 4),
                description=describe_evidence(strongest, language),
                discount_applied=round(discount, 4),
            )
        return AsymmetrySide(
            text=text,
            signal_type=strongest.signal_type,
            signal_label=strongest.label,
            evidence_class=self._class_of(strongest.signal_type.value),
            raw_strength=round(raw, 4),
            weight=round(clamp(raw * prior_negative), 4),
            information_content=round(info, 4),
            description=describe_evidence(strongest, language),
            amplification_applied=round(negative_amplification(raw, info), 4),
        )

    def _external_spans(self, text: str, polarity: str) -> list[EvidenceSpan]:
        """Evidence spans only. Self-authored framing belongs to the reader."""

        return [
            span
            for span in text_parser.detect(text, self.book)
            if span.polarity == polarity and span.signal_type not in SELF_FRAMING_SIGNAL_TYPES
        ]

    def _clause_with(self, clauses: list[str], spans: list[EvidenceSpan]) -> str | None:
        needles = [span.text for span in spans if span.text]
        for clause in clauses:
            if any(needle in clause for needle in needles):
                return clause
        return None

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

    def _legacy_side(
        self,
        text: str,
        polarity: str,
        mode: Mode,
        interpretation: str,
        *,
        is_positive: bool,
    ) -> AsymmetrySide | None:
        """Legacy side builder: mixes policy with the reader's own discount.

        Kept verbatim so the legacy composite reproduces its historical numbers.
        The Evidence Profile uses :meth:`_profile_side` instead.
        """

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
                evidence_class=self._class_of(strongest.signal_type.value),
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
                evidence_class=self._class_of(strongest.signal_type.value),
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
            evidence_class=self._class_of(strongest.signal_type.value),
            raw_strength=round(raw, 4),
            weight=round(clamp(raw * config.prior_negative_amplification_multiplier), 4),
            information_content=round(info, 4),
            description=describe_evidence(strongest, language),
            amplification_applied=round(negative_amplification(raw, info), 4),
            interpretation=interpretation,
        )

    # -- comparability -----------------------------------------------------
    def _class_of(self, signal_type: str) -> str:
        """Evidence class of a signal type, from the configured map."""

        classes = self.book.asymmetry.comparability.evidence_classes
        return classes.get(signal_type, "unclassified")

    def _comparability(
        self, positive: AsymmetrySide | None, negative: AsymmetrySide | None
    ) -> tuple[bool, str]:
        """Are these two clues candidate answers to a similar question?

        Declining the comparison is not the same as scoring zero: zero means the
        standards were compared and came out symmetric, while a declined
        comparison means the comparison itself does not hold.
        """

        config = self.book.asymmetry.comparability
        if positive is None or negative is None:
            return False, REASON_MISSING_EXTERNAL_EVIDENCE
        if not config.enabled:
            return True, ""
        for side in (positive, negative):
            if side.evidence_class in config.boundary_classes:
                return False, REASON_EXPLICIT_BOUNDARY
        for side in (positive, negative):
            if self._later_state_marker(side):
                return False, REASON_TEMPORAL_STATE_CHANGE
        return True, ""

    def _later_state_marker(self, side: AsymmetrySide) -> str:
        """A marker that places this side's clue after a change of state.

        The marker alone is not enough: the matched evidence has to sit *after*
        it in the sentence, so "最后我还是没忍住" is not read as a state change
        for a clue that appears earlier.
        """

        text = side.text or ""
        if not text:
            return ""
        config = self.book.asymmetry.comparability
        language = text_parser.detect_language(text)
        markers = config.later_state_markers.get(language) or []
        if not markers:
            return ""
        lowered = text.lower()
        spans = text_parser.detect(text, self.book)
        for marker in markers:
            index = lowered.find(marker.lower())
            if index < 0:
                continue
            after = index + len(marker)
            if any(span.start >= after for span in spans):
                return marker
        return ""

    def _has_self_discount(self, text: str) -> bool:
        if not text:
            return False
        return any(span.polarity == "self_discount" for span in text_parser.detect(text, self.book))


def _ratio(numerator: float, denominator: float) -> float:
    """Bounded symmetric ratio, clamped to ``[0, 1]``."""

    if denominator <= 0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


__all__ = [
    "DEFAULT_NEGATIVE_SIDE_POLARITIES",
    "REASON_EXPLICIT_BOUNDARY",
    "REASON_INSUFFICIENT_INPUT",
    "REASON_MISSING_EXTERNAL_EVIDENCE",
    "REASON_TEMPORAL_STATE_CHANGE",
    "SELF_DISCOUNT_PENALTY",
    "SELF_FRAMING_SIGNAL_TYPES",
    "EvidenceAsymmetryDetector",
]
