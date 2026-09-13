"""NED's three theories in a trenchcoat.

* :class:`PositiveEvidenceDenier` (PED) detects positive evidence and lowers its
  probative value.
* :class:`NegativeEvidenceAmplifier` (NEA) demonstrates — rather than
  encourages — the asymmetric habit of inflating very weak negative evidence.
  It always pairs the inflated reading with a reality check.
* :class:`SemanticEscapeModule` generates increasingly strained alternative
  explanations as the evidence gets stronger.

None of the three claims to know anything about a real person. They emit
explicitly labelled alternative *hypotheses* with arbitrary plausibility
numbers attached, because attaching numbers to guesses is the joke.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ned.app.core.models import AlternativeExplanation, EvidenceSpan, SignalType
from ned.app.core.rules import EscapeTier, KeywordEscape, RuleBook, resolve_localized
from ned.app.core.scoring import clamp, describe_evidence
from ned.app.core.scoring import discount as compute_discount

#: Plausibility shrinkage applied as NED's escape capacity runs out. Once the
#: good explanations are gone, the remaining ones have to be worse.
CAPACITY_PLAUSIBILITY_PENALTY = 0.25


@dataclass(frozen=True)
class AmplifiedReading:
    """The NEA output: an inflated reading plus the correction."""

    observed_evidence: str
    irrational_interpretation: str
    reality_check: str
    amplification: float
    signal_type: SignalType
    span: EvidenceSpan | None = None


@dataclass
class _Candidate:
    """An alternative explanation before truncation and ranking."""

    category: str
    rule_id: str
    plausibility: float
    is_keyword: bool = False


class PositiveEvidenceDenier:
    """PED — the module that decides what your good news is worth."""

    def __init__(self, book: RuleBook) -> None:
        self.book = book

    def is_positive(self, span: EvidenceSpan) -> bool:
        return span.polarity == "positive"

    def discount(
        self, mode_id: str, escape_press: float, amplification: float
    ) -> tuple[float, float]:
        """Return ``(discount, escape_bonus)`` for the configured mode."""

        profile = self.book.mode(mode_id)
        return compute_discount(
            self.book.scoring,
            discount_base=profile.discount_base,
            escape_press=escape_press,
            amplification=amplification,
        )

    def baseline_discount(self, mode_id: str) -> float:
        """The share of positive evidence NED discards before reading it."""

        return self.book.mode(mode_id).discount_base


class NegativeEvidenceAmplifier:
    """NEA — shows the asymmetric reading, then shows what it is worth."""

    def __init__(self, book: RuleBook) -> None:
        self.book = book

    def amplify(
        self, spans: list[EvidenceSpan], language: str, amplification: float
    ) -> AmplifiedReading | None:
        """Build the amplified reading for the strongest negative signal."""

        negatives = [span for span in spans if span.polarity == "negative"]
        if not negatives:
            return None
        span = max(negatives, key=lambda item: item.base_strength)
        rule = next((item for item in self.book.signals if item.id == span.rule_id), None)
        interpretation = ""
        if rule is not None:
            interpretation = rule.text_for(rule.amplified_interpretation, language)
        if not interpretation:
            interpretation = {
                "zh": "对方不想理我。",
                "en": "They do not want to talk to me.",
            }.get(language, "They do not want to talk to me.")

        observed = describe_evidence(span, language)
        check_id = (
            "latency_only" if span.signal_type == SignalType.RESPONSE_LATENCY else "negative_only"
        )
        reality_check = self.book.reality_check(
            check_id,
            language,
            {
                "duration": observed,
                "negative_desc": observed,
            },
        )
        return AmplifiedReading(
            observed_evidence=observed,
            irrational_interpretation=interpretation,
            reality_check=reality_check,
            amplification=amplification,
            signal_type=span.signal_type,
            span=span,
        )


class SemanticEscapeModule:
    """The escape ladder: evidence up, plausibility down."""

    def __init__(self, book: RuleBook) -> None:
        self.book = book
        self._templates: dict[str, dict[str, str]] = {}
        for rung in book.escape_tiers:
            for template in rung.hypotheses:
                self._templates[f"{rung.id}:{template.category}"] = template.texts

    # -- selection helpers -------------------------------------------------
    def tier_for(self, mass: float) -> EscapeTier:
        """Pick the ladder rung that matches the accumulated positive mass."""

        tiers = self.book.escape_tiers
        for tier in tiers:
            if tier.min_strength <= mass <= tier.max_strength:
                return tier
        below = [tier for tier in tiers if tier.min_strength <= mass]
        return below[-1] if below else tiers[0]

    def matching_keyword_escapes(
        self, text: str, signal_type: SignalType | None
    ) -> list[KeywordEscape]:
        """Keyword escapes are literal-wording triggered and signal-type gated."""

        found: list[KeywordEscape] = []
        for escape in self.book.keyword_escapes:
            if escape.applies_to_signal_types and signal_type not in escape.applies_to_signal_types:
                continue
            if any(re.search(pattern, text, re.IGNORECASE) for pattern in escape.patterns):
                found.append(escape)
        return found

    def _candidates(
        self, text: str, mass: float, signal_type: SignalType | None
    ) -> tuple[list[_Candidate], EscapeTier]:
        tier = self.tier_for(mass)
        pool: list[_Candidate] = [
            _Candidate(
                category=escape.category,
                rule_id=escape.id,
                plausibility=escape.plausibility,
                is_keyword=True,
            )
            for escape in self.matching_keyword_escapes(text, signal_type)
        ]
        pool.extend(
            _Candidate(
                category=template.category,
                rule_id=tier.id,
                plausibility=clamp(tier.plausibility + template.plausibility_offset),
                is_keyword=False,
            )
            for template in tier.hypotheses
        )
        return pool, tier

    def generate(
        self,
        *,
        text: str,
        mass: float,
        mode_id: str,
        language: str,
        capacity: float,
        limit: int,
        signal_type: SignalType | None = None,
    ) -> list[AlternativeExplanation]:
        """Produce the ranked alternative explanations for one analysis."""

        profile = self.book.mode(mode_id)
        pool, _tier = self._candidates(text, mass, signal_type)
        keyword_texts = {escape.id: escape.texts for escape in self.book.keyword_escapes}

        penalty = 1.0 - CAPACITY_PLAUSIBILITY_PENALTY * clamp(capacity, 0.0, 1.0)
        rendered: list[tuple[_Candidate, str, float]] = []
        for candidate in pool:
            mapping = (
                keyword_texts[candidate.rule_id]
                if candidate.is_keyword
                else self._templates.get(f"{candidate.rule_id}:{candidate.category}", {})
            )
            hypothesis = resolve_localized(mapping, language, candidate.category)
            plausibility = clamp(candidate.plausibility * profile.plausibility_scale * penalty)
            rendered.append((candidate, hypothesis, plausibility))

        # Keyword escapes are specific to this exact sentence, so they survive
        # truncation; within each group the more plausible reading comes first.
        rendered.sort(key=lambda item: (0 if item[0].is_keyword else 1, -item[2]))

        seen_categories: set[str] = set()
        results: list[AlternativeExplanation] = []
        for candidate, hypothesis, plausibility in rendered:
            if candidate.category in seen_categories:
                continue
            seen_categories.add(candidate.category)
            results.append(
                AlternativeExplanation(
                    hypothesis=hypothesis,
                    category=candidate.category,
                    plausibility=round(plausibility, 2),
                    source="local-rule",
                    rule_id=candidate.rule_id,
                    note="Alternative hypothesis, not a finding.",
                )
            )
            if len(results) >= limit:
                break
        return results


__all__ = [
    "CAPACITY_PLAUSIBILITY_PENALTY",
    "AmplifiedReading",
    "NegativeEvidenceAmplifier",
    "PositiveEvidenceDenier",
    "SemanticEscapeModule",
]
