"""The analyzer: where every module meets.

``NedAnalyzer`` is deliberately framework-free. The FastAPI routes and the Typer
CLI are thin adapters over this class, so the engine can be embedded, tested or
reused without importing a web server (or a terminal).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ned.app.core import parser as text_parser
from ned.app.core.asymmetry import EvidenceAsymmetryDetector
from ned.app.core.fnbp import NotificationBranchPredictor
from ned.app.core.models import (
    AnalysisResult,
    AnalyzeRequest,
    AsymmetryResult,
    EasterEggHit,
    EngineInfo,
    EvidenceSpan,
    ExampleCase,
    FnbpRequest,
    FnbpResult,
    Mode,
    ModeDescription,
    ScoringBreakdown,
    SignalType,
)
from ned.app.core.rules import RuleBook
from ned.app.core.scoring import (
    describe_evidence,
    duration_label,
    escape_capacity,
    escape_pressure,
    history_pressure,
    information_content,
    negative_amplification,
    negative_mass,
    noisy_or,
    positive_mass,
    reaching_label,
    reaching_level,
)
from ned.app.core.theories import NegativeEvidenceAmplifier, PositiveEvidenceDenier
from ned.app.core.verdict import VerdictEngine
from ned.app.providers import ExplanationContext, ExplanationProvider, get_provider
from ned.app.version import ENGINE_NAME, __version__

#: Why reaching high levels is not a compliment.
REACHING_ALERT_LEVEL = 80.0

#: Where the shipped example cases live (they ship inside the package so that
#: ``ned examples`` works after ``pip install``).
EXAMPLES_PATH = Path(__file__).resolve().parents[2] / "examples" / "cases.json"


class NedAnalyzer:
    """Offline analysis facade. Stateless: NED stores nothing about you."""

    def __init__(self, book: RuleBook | None = None, provider_name: str = "local") -> None:
        self.book = book if book is not None else RuleBook.load()
        #: Registry key of the active provider (``/api/providers`` reports it).
        self.provider_key = provider_name
        self.provider: ExplanationProvider = get_provider(provider_name, self.book)
        self.ped = PositiveEvidenceDenier(self.book)
        self.nea = NegativeEvidenceAmplifier(self.book)
        self.asymmetry = EvidenceAsymmetryDetector(self.book)
        self.verdicts = VerdictEngine(self.book)
        self.fnbp = NotificationBranchPredictor(self.book)

    # -- analysis ----------------------------------------------------------
    def analyze(self, request: AnalyzeRequest) -> AnalysisResult:
        """Analyse an API request."""

        return self.analyze_text(
            request.text,
            mode=request.mode,
            history=request.history,
            top_k=request.top_k,
        )

    def analyze_text(
        self,
        text: str,
        mode: Mode = "normal",
        history: Sequence[str] | None = None,
        top_k: int | None = None,
    ) -> AnalysisResult:
        """Analyse one message or event description."""

        book = self.book
        history = list(history or [])
        language = text_parser.detect_language(text)
        spans = text_parser.detect(text, book)
        primary = text_parser.primary_span(spans)
        # An explicit refusal or boundary is an observation, not a fuzzy signal.
        # It is tracked apart from ``primary`` because positive evidence keeps the
        # primary slot (PED exists to de-weight it), while the verdict must never
        # turn a stated boundary into an escape.
        explicit_rejection = any(span.signal_type is SignalType.DIRECT_REJECTION for span in spans)

        pos_mass = positive_mass(spans)
        neg_mass = negative_mass(spans)
        pos_info = information_content(spans, "positive")
        neg_info = information_content(spans, "negative")
        amplification = negative_amplification(
            neg_mass, neg_info, book.scoring.negative_amplification_floor
        )

        history_mass = self.history_mass(history)
        pressure = history_pressure(history_mass)
        capacity = escape_capacity(book.scoring, pos_mass, pressure)
        exhausted = capacity >= book.scoring.capacity_exhausted_threshold

        profile = book.mode(mode)
        limit = top_k or profile.escape_count
        signal_type = primary.signal_type if primary is not None else SignalType.NONE
        signal_label = primary.label if primary is not None else book.no_signal_label_for(language)

        # PED only de-weights positive evidence. With none on the table, NED has
        # nothing to explain away, and inventing excuses for a negative reading
        # would be the opposite of the point.
        explanations = (
            self.provider.explain(
                ExplanationContext(
                    text=text,
                    language=language,
                    mode=mode,
                    positive_mass=pos_mass,
                    signal_type=signal_type,
                    signal_label=signal_label,
                    escape_capacity=capacity,
                    limit=limit,
                )
            )
            if pos_mass > 0
            else []
        )
        press = escape_pressure([item.plausibility for item in explanations])
        discount, discount_bonus = self.ped.discount(mode, press, amplification)
        reaching, positive_term, escape_term, history_term = reaching_level(
            book.scoring, pos_mass, press, pressure
        )
        label = reaching_label(book.scoring, reaching)

        asymmetry = self.asymmetry.from_analysis(text, mode, spans)
        stronger_duration = duration_label(spans, language)
        comparison = {
            "duration": stronger_duration,
            "signal_label": signal_label,
            "positive_desc": self._side_description(text, "positive", language, pos_mass),
            "negative_desc": self._side_description(text, "negative", language, neg_mass),
            "strength": f"{pos_mass:.1f}" if pos_mass > 0 else f"{neg_mass:.1f}",
        }
        reality_check = book.reality_check(
            self._reality_check_id(spans, pos_mass, neg_mass), language, comparison
        )
        amplified = self.nea.amplify(spans, language, amplification)

        verdict = self.verdicts.decide(
            self._verdict_context(
                mode=mode,
                language=language,
                primary=primary,
                pos_mass=pos_mass,
                neg_mass=neg_mass,
                amplification=amplification,
                discount=discount,
                reaching=reaching,
                capacity=capacity,
                exhausted=exhausted,
                asymmetry=asymmetry,
                duration=stronger_duration,
                direct_rejection=explicit_rejection,
            )
        )
        eggs = book.egg_hits(text, mode, language, pos_mass)

        return AnalysisResult(
            input=text,
            mode=mode,
            language=language,
            signal_type=signal_type,
            signal_label=signal_label,
            signal_strength=round(pos_mass if pos_mass > 0 else neg_mass, 4),
            raw_interpretation=text_parser.raw_interpretation(primary, book, language),
            alternative_explanations=explanations,
            positive_evidence_discount=discount,
            negative_evidence_amplification=amplification,
            ned_reaching_level=reaching,
            reaching_label=label,
            reality_check=reality_check,
            asymmetry_reality_check=(asymmetry.reality_check if asymmetry is not None else ""),
            verdict=verdict,
            mode_notes=self._mode_notes(
                mode=mode,
                language=language,
                explanations=len(explanations),
                reaching=reaching,
                capacity=capacity,
                exhausted=exhausted,
                history=history,
                history_mass=history_mass,
                eggs=eggs,
                direct_rejection=explicit_rejection,
            ),
            evidence=spans,
            observed_evidence=amplified.observed_evidence if amplified else "",
            irrational_amplification=(amplified.irrational_interpretation if amplified else ""),
            asymmetry=asymmetry,
            easter_eggs=eggs,
            breakdown=ScoringBreakdown(
                positive_mass=round(pos_mass, 4),
                negative_mass=round(neg_mass, 4),
                positive_information=round(pos_info, 4),
                negative_information=round(neg_info, 4),
                discount_base=profile.discount_base,
                discount_escape_bonus=discount_bonus,
                escape_pressure=press,
                history_pressure=pressure,
                history_mass=round(history_mass, 4),
                escape_capacity=capacity,
                negative_amplification=amplification,
                reaching_positive_term=positive_term,
                reaching_escape_term=escape_term,
                reaching_history_term=history_term,
                asymmetry_score=(asymmetry.asymmetry_score if asymmetry else None),
            ),
            engine=EngineInfo(
                name=ENGINE_NAME,
                version=__version__,
                provider=self.provider.name,
                offline=bool(self.provider.offline),
                escapes_used=len(explanations),
            ),
            disclaimer=book.disclaimer,
        )

    # -- other surfaces ----------------------------------------------------
    def compare(self, request: Any) -> AsymmetryResult:
        """Delegate to the asymmetry detector."""

        return self.asymmetry.compare_request(request)

    def fnbp_analysis(self, request: FnbpRequest, language: str = "zh") -> FnbpResult:
        return self.fnbp.run(request, language=language)

    def modes(self) -> list[ModeDescription]:
        return [
            ModeDescription(id=profile.id, label=profile.label, blurb=profile.blurb)
            for profile in self.book.modes.values()
        ]

    def examples(self, path: Path | None = None) -> list[ExampleCase]:
        """Load the shipped example cases (never user data)."""

        target = path or EXAMPLES_PATH
        if not target.is_file():
            return []
        with target.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return [ExampleCase.model_validate(item) for item in payload.get("cases", [])]

    def history_mass(self, history: Sequence[str]) -> float:
        """Cumulative positive mass of everything the user said before."""

        masses = [
            positive_mass(text_parser.detect(item, self.book)) for item in history if item.strip()
        ]
        return noisy_or(masses)

    # -- internals ---------------------------------------------------------
    def _side_description(self, text: str, polarity: str, language: str, mass: float) -> str:
        if mass <= 0:
            return "—"
        spans = [span for span in text_parser.detect(text, self.book) if span.polarity == polarity]
        if not spans:
            return text.strip() or "—"
        strongest = max(spans, key=lambda span: span.information_content)
        return describe_evidence(strongest, language, fallback=text.strip() or "—")

    def _reality_check_id(self, spans: list[EvidenceSpan], pos_mass: float, neg_mass: float) -> str:
        has_positive = pos_mass > 0
        has_negative = neg_mass > 0
        has_discount = any(span.polarity == "self_discount" for span in spans)
        primary = text_parser.primary_span(spans)

        # An explicit boundary is the most informative thing in the input, so it
        # chooses the reality check even when positive evidence is also present.
        if any(span.signal_type is SignalType.DIRECT_REJECTION for span in spans):
            return "direct_rejection"
        if has_positive and has_negative:
            return "asymmetry_pair"
        if has_negative:
            if primary is not None and primary.signal_type == SignalType.RESPONSE_LATENCY:
                return "latency_only"
            return "negative_only"
        if has_positive:
            return "strong_positive_only" if pos_mass >= 75 else "moderate_positive"
        if has_discount:
            return "self_discount_only"
        return "no_signal"

    def _verdict_context(
        self,
        *,
        mode: Mode,
        language: str,
        primary: EvidenceSpan | None,
        pos_mass: float,
        neg_mass: float,
        amplification: float,
        discount: float,
        reaching: float,
        capacity: float,
        exhausted: bool,
        asymmetry: AsymmetryResult | None,
        duration: str,
        direct_rejection: bool,
    ) -> dict[str, Any]:
        return {
            "mode": mode,
            "language": language,
            "signal_type": (primary.signal_type.value if primary else SignalType.NONE.value),
            "signal_label": primary.label if primary else self.book.no_signal_label_for(language),
            "polarity": primary.polarity if primary else "neutral",
            "signal_strength": round(pos_mass if pos_mass > 0 else neg_mass, 4),
            "positive_mass": round(pos_mass, 4),
            "negative_mass": round(neg_mass, 4),
            "negative_amplification": amplification,
            "positive_evidence_discount": discount,
            "reaching": reaching,
            "escape_capacity": capacity,
            "escape_capacity_exhausted": exhausted,
            "asymmetry_score": asymmetry.asymmetry_score if asymmetry else 0.0,
            "has_positive": pos_mass > 0,
            "has_negative": neg_mass > 0,
            "direct_rejection": direct_rejection,
            "duration": duration,
        }

    def _mode_notes(
        self,
        *,
        mode: Mode,
        language: str,
        explanations: int,
        reaching: float,
        capacity: float,
        exhausted: bool,
        history: Sequence[str],
        history_mass: float,
        eggs: list[EasterEggHit],
        direct_rejection: bool,
    ) -> list[str]:
        profile = self.book.mode(mode)
        notes = [f"mode: {profile.label} ({profile.id}) — {profile.blurb}"]
        if explanations == 0:
            if direct_rejection:
                notes.append(
                    "explicit boundary: NED has nothing to de-weight here. The refusal is "
                    "reported as stated and is given no semantic escape."
                )
            else:
                notes.append(
                    "no positive evidence: PED has nothing to de-weight, so no alternative "
                    "hypotheses were generated. NED notes that a negative reading is equally "
                    "not a measurement."
                )
        if reaching >= REACHING_ALERT_LEVEL:
            notes.append(self.book.escape_messages.get("reaching", "NED is currently reaching."))
        if exhausted:
            notes.append(
                self.book.escape_messages.get(
                    "capacity_exhausted", "NED has run out of explanations."
                )
            )
        elif capacity >= self.book.scoring.capacity_warning_threshold:
            notes.append(
                self.book.escape_messages.get(
                    "capacity_warning", "NED semantic escape capacity approaching limit."
                )
            )
        if history:
            notes.append(
                f"history: {len(history)} previous turn(s), cumulative evidence mass "
                f"{history_mass:.1f}/100 — NED notes that you brought receipts."
            )
        if mode == "scientific":
            notes.append("register: peer review. vocabulary: formal. conclusion: unchanged.")
        notes.append(
            f"engine: {self.provider.name} (offline={self.provider.offline}), "
            f"{explanations} alternative explanation(s) generated"
        )
        notes.extend(f"[easter egg {egg.id}] {egg.message}" for egg in eggs)
        notes.append(
            "no input text was stored, transmitted or logged; NED has no database and no telemetry."
        )
        return notes


__all__ = ["EXAMPLES_PATH", "REACHING_ALERT_LEVEL", "NedAnalyzer"]
