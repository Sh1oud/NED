"""Public data models.

Everything NED produces is structured. The satire only lands if the output
looks like a lab report; a wall of text would look like a horoscope instead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ned.app.config import MAX_INPUT_CHARS

Mode = Literal["normal", "scientific", "extreme"]
Polarity = Literal["positive", "negative", "neutral", "self_discount"]
Severity = Literal["info", "warning", "reject", "chaos"]
Language = Literal["zh", "en", "unknown"]
ProviderKind = Literal["local-rule", "llm"]


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class SignalType(StrEnum):
    """Classification of a single detected evidence signal."""

    EXPLICIT_AFFECTION = "explicit_affection"
    EXPRESSED_LOVE = "expressed_love"
    MISSING_YOU = "missing_you"
    COMMITMENT_OFFER = "commitment_offer"
    MARRIAGE = "marriage"
    INITIATION = "initiation"
    SUSTAINED_INTERACTION = "sustained_interaction"
    COMPLIMENT = "compliment"
    CARE = "care"
    MEETUP_INVITATION = "meetup_invitation"
    RESPONSIVENESS = "responsiveness"
    DIRECT_REJECTION = "direct_rejection"
    HOSTILE_EXPRESSION = "hostile_expression"
    RESPONSE_LATENCY = "response_latency"
    COLD_REPLY = "cold_reply"
    PLAN_CANCELLED = "plan_cancelled"
    SELF_NEGATIVE_BELIEF = "self_negative_belief"
    SELF_DISCOUNT = "self_discount"
    NONE = "none"


class Duration(BaseModel):
    """A duration lifted out of the input text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seconds: float = Field(ge=0)
    surface: str
    unit: str
    amount: float = Field(ge=0)

    @property
    def is_trivial(self) -> bool:
        """True when the interval carries almost no information (minutes)."""

        return self.seconds < 3600


class EvidenceSpan(BaseModel):
    """One matched piece of evidence, with its provenance kept visible."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    text: str
    signal_type: SignalType
    label: str
    polarity: Polarity
    base_strength: float = Field(ge=0, le=100)
    information_content: float = Field(ge=0, le=100)
    occurrences: int = Field(default=1, ge=1)
    matched_keywords: list[str] = Field(default_factory=list)
    start: int = Field(default=-1)
    end: int = Field(default=-1)
    duration: Duration | None = None
    description: str = ""

    @property
    def weight(self) -> float:
        """Strength after a repeated-statement bonus (diminishing, capped)."""

        if self.occurrences <= 1:
            return self.base_strength
        bonus = 1.0 + 0.15 * min(self.occurrences - 1, 4)
        return min(100.0, self.base_strength * bonus)


class AlternativeExplanation(BaseModel):
    """An alternative reading of the evidence.

    These are generated hypotheses. The ``note`` field exists so no consumer can
    mistake them for findings.
    """

    model_config = ConfigDict(extra="forbid")

    hypothesis: str
    category: str
    plausibility: float = Field(ge=0, le=100)
    source: ProviderKind = "local-rule"
    rule_id: str = ""
    note: str = "Alternative hypothesis, not a finding."


class Verdict(BaseModel):
    """The NED verdict: a string, a severity and the rule that produced it."""

    model_config = ConfigDict(extra="forbid")

    code: str
    text: str
    severity: Severity
    emoji: str = ""
    rule_id: str = ""


class EasterEggHit(BaseModel):
    """A purely cosmetic easter egg hit, kept out of the verdict path."""

    model_config = ConfigDict(extra="forbid")

    id: str
    trigger: str
    message: str
    emoji: str = ""


class AsymmetrySide(BaseModel):
    """One side of an evidence-threshold comparison."""

    model_config = ConfigDict(extra="forbid")

    text: str
    signal_type: SignalType
    signal_label: str
    raw_strength: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=100)
    information_content: float = Field(ge=0, le=100)
    description: str = ""
    discount_applied: float = Field(default=0.0, ge=0, le=100)
    amplification_applied: float = Field(default=0.0, ge=0, le=100)
    interpretation: str = ""


class AsymmetryResult(BaseModel):
    """Output of the Evidence Asymmetry Detector."""

    model_config = ConfigDict(extra="forbid")

    mode: Mode
    positive: AsymmetrySide | None = None
    negative: AsymmetrySide | None = None
    positive_threshold: str
    negative_threshold: str
    asymmetry_score: float = Field(ge=0, le=100)
    asymmetry_label: str
    reality_check: str
    sub_scores: dict[str, float] = Field(default_factory=dict)
    verdict: Verdict
    disclaimer: str
    generated_at: datetime = Field(default_factory=utcnow)


class AnalyzeRequest(BaseModel):
    """Request body of ``POST /api/analyze``."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    mode: Mode = "normal"
    #: Earlier turns, oldest first. Used only to model NED's escalating
    #: unwillingness to update; NED stores nothing server-side.
    history: list[str] = Field(default_factory=list)
    #: Optional cap on the number of alternative explanations.
    top_k: int | None = Field(default=None, ge=1, le=10)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value

    @field_validator("history")
    @classmethod
    def _history_bounded(cls, value: list[str]) -> list[str]:
        if len(value) > 20:
            raise ValueError("history accepts at most 20 previous turns")
        total = sum(len(item) for item in value)
        if total > MAX_INPUT_CHARS:
            raise ValueError("history is longer than the accepted input budget")
        return value


class AsymmetryEvent(BaseModel):
    """One event handed to the asymmetry detector."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    label: Literal["auto", "positive", "negative"] = "auto"
    interpretation: str = ""


class AsymmetryRequest(BaseModel):
    """Request body of ``POST /api/asymmetry``.

    Supply either the two sides explicitly, or a free ``text`` (NED splits it
    into clauses and classifies them), or an ``events`` list. At least one
    source is required.
    """

    model_config = ConfigDict(extra="forbid")

    positive_text: str | None = Field(default=None, max_length=MAX_INPUT_CHARS)
    negative_text: str | None = Field(default=None, max_length=MAX_INPUT_CHARS)
    positive_interpretation: str = ""
    negative_interpretation: str = ""
    text: str | None = Field(default=None, max_length=MAX_INPUT_CHARS)
    events: list[AsymmetryEvent] = Field(default_factory=list)
    mode: Mode = "normal"


class FnbpRequest(BaseModel):
    """Request body of ``POST /api/fnbp`` (the Lab easter egg)."""

    model_config = ConfigDict(extra="forbid")

    expected_sender: str = Field(default="Fuyuki", min_length=1, max_length=64)
    actual_senders: list[str] = Field(default_factory=lambda: ["张三", "李四"])
    notifications: int = Field(default=5, ge=1, le=200)
    seed: int = 7
    base_rate: float | None = Field(default=None, ge=0, le=1)


class FnbpNotification(BaseModel):
    """One simulated notification and its (mis)prediction."""

    model_config = ConfigDict(extra="forbid")

    index: int
    predicted_sender: str
    predicted_probability: float = Field(ge=0, le=100)
    actual_sender: str
    hit: bool
    pipeline_flushed: bool


class FnbpResult(BaseModel):
    """Output of the Fuyuki Notification Branch Predictor."""

    model_config = ConfigDict(extra="forbid")

    expected_sender: str
    notifications: int
    prediction_hits: int
    prediction_misses: int
    mispredict_rate: float = Field(ge=0, le=100)
    pipeline_flushes: int
    wasted_cycles: int
    per_notification: list[FnbpNotification]
    verdict: Verdict
    codename_note: str
    disclaimer: str
    generated_at: datetime = Field(default_factory=utcnow)


class ScoringBreakdown(BaseModel):
    """Internal numbers behind the verdict, exposed for auditability."""

    model_config = ConfigDict(extra="forbid")

    positive_mass: float = 0.0
    negative_mass: float = 0.0
    positive_information: float = 0.0
    negative_information: float = 0.0
    discount_base: float = 0.0
    discount_escape_bonus: float = 0.0
    escape_pressure: float = 0.0
    history_pressure: float = 0.0
    history_mass: float = 0.0
    escape_capacity: float = 0.0
    negative_amplification: float = 0.0
    reaching_positive_term: float = 0.0
    reaching_escape_term: float = 0.0
    reaching_history_term: float = 0.0
    asymmetry_score: float | None = None


class EngineInfo(BaseModel):
    """Which engine produced a result (v0.1 is always local)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    provider: str
    offline: bool = True
    escapes_used: int = 0


class AnalysisResult(BaseModel):
    """The full NED report for one input."""

    model_config = ConfigDict(extra="forbid")

    input: str
    mode: Mode
    language: Language
    signal_type: SignalType
    signal_label: str
    signal_strength: float = Field(ge=0, le=100)
    raw_interpretation: str
    alternative_explanations: list[AlternativeExplanation] = Field(default_factory=list)
    positive_evidence_discount: float = Field(ge=0, le=100)
    negative_evidence_amplification: float = Field(ge=0, le=100)
    ned_reaching_level: float = Field(ge=0, le=100)
    reaching_label: str
    reality_check: str
    asymmetry_reality_check: str = ""
    verdict: Verdict
    mode_notes: list[str] = Field(default_factory=list)
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    observed_evidence: str = ""
    irrational_amplification: str = ""
    asymmetry: AsymmetryResult | None = None
    easter_eggs: list[EasterEggHit] = Field(default_factory=list)
    breakdown: ScoringBreakdown = Field(default_factory=ScoringBreakdown)
    engine: EngineInfo
    disclaimer: str
    generated_at: datetime = Field(default_factory=utcnow)


class HealthResponse(BaseModel):
    """Response of ``GET /api/health``."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    version: str
    uptime_seconds: float
    local_only: bool = True
    engine: str


class VersionResponse(BaseModel):
    """Response of ``GET /api/version``."""

    model_config = ConfigDict(extra="forbid")

    name: str
    full_name: str
    version: str
    api_version: str
    python: str
    tagline: str
    motto: str


class ModeDescription(BaseModel):
    """One entry of ``GET /api/modes``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    blurb: str


class ExampleCase(BaseModel):
    """One entry of ``GET /api/examples``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    mode: str
    note: str = ""


__all__ = [
    "AlternativeExplanation",
    "AnalysisResult",
    "AnalyzeRequest",
    "AsymmetryEvent",
    "AsymmetryRequest",
    "AsymmetryResult",
    "AsymmetrySide",
    "Duration",
    "EasterEggHit",
    "EngineInfo",
    "EvidenceSpan",
    "ExampleCase",
    "FnbpNotification",
    "FnbpRequest",
    "FnbpResult",
    "HealthResponse",
    "Language",
    "Mode",
    "ModeDescription",
    "Polarity",
    "ScoringBreakdown",
    "Severity",
    "SignalType",
    "Verdict",
    "VersionResponse",
    "utcnow",
]
