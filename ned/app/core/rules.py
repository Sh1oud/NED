"""Rule packs: the configurable brain of NED.

NED's judgement calls live in JSON files under ``ned/app/rules`` (or wherever
``NED_RULES_DIR`` points), not in Python. Python only knows *how* to evaluate
rules; the JSON knows *what* NED believes, which is the part that should be
easy to argue with in a pull request.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ned.app.config import (
    AsymmetryConfig,
    ModeProfile,
    RealityCheckTemplate,
    ScoringConfig,
    rules_dir,
)
from ned.app.core.models import EasterEggHit, Mode, Severity, SignalType

#: Every analysis mode, used as the default scope of a verdict rule.
ALL_MODES: list[Mode] = ["normal", "scientific", "extreme"]


class SignalRule(BaseModel):
    """One pattern-based detection rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    signal_type: SignalType
    label: str
    #: Language-keyed labels so a Chinese report does not print English labels.
    labels: dict[str, str] = Field(default_factory=dict)
    polarity: str
    weight: float = Field(ge=0, le=100)
    information_content: float = Field(ge=0, le=100)
    patterns: list[str] = Field(min_length=1)
    exclude: list[str] = Field(default_factory=list)
    interpretations: dict[str, str] = Field(default_factory=dict)
    description: dict[str, str] = Field(default_factory=dict)
    #: NEA's deliberately irrational reading of this signal. Displayed next to a
    #: reality check so the asymmetry is visible rather than encouraged.
    amplified_interpretation: dict[str, str] = Field(default_factory=dict)
    uses_duration: bool = False
    #: How urgently this signal should be surfaced when several match.
    salience: float = Field(default=1.0, ge=0)
    notes: str = ""

    def text_for(self, mapping: dict[str, str], language: str, fallback: str = "") -> str:
        """Resolve a language-keyed string with graceful degradation."""

        return resolve_localized(mapping, language, fallback)

    def label_for(self, language: str) -> str:
        """Localized label, falling back to the canonical English one."""

        return resolve_localized(self.labels, language, self.label)


class HypothesisTemplate(BaseModel):
    """One alternative explanation inside an escape tier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str
    texts: dict[str, str]
    plausibility_offset: float = 0.0
    absurdity: float = Field(default=0.0, ge=0, le=1)


class EscapeTier(BaseModel):
    """A rung of the Semantic Escape ladder."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    min_strength: float = Field(ge=0, le=100)
    max_strength: float = Field(ge=0, le=100)
    plausibility: float = Field(ge=0, le=100)
    hypotheses: list[HypothesisTemplate] = Field(min_length=1)


class KeywordEscape(BaseModel):
    """A specific, high-priority escape triggered by literal wording."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    category: str
    patterns: list[str] = Field(min_length=1)
    plausibility: float = Field(ge=0, le=100)
    absurdity: float = Field(default=0.8, ge=0, le=1)
    texts: dict[str, str]
    #: Restrict to inputs whose strongest positive signal is one of these types.
    applies_to_signal_types: list[SignalType] = Field(default_factory=list)


class VerdictRule(BaseModel):
    """A conditional verdict rule.

    ``when`` is a small declarative predicate language evaluated against the
    flat analysis context; the first matching rule wins.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    priority: int
    when: dict[str, Any]
    severity: Severity
    emoji: str = ""
    texts: dict[str, str]
    modes: list[Mode] = Field(default_factory=lambda: list(ALL_MODES))


class EasterEggRule(BaseModel):
    """A cosmetic easter egg. Never allowed to influence a verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    patterns: list[str] = Field(min_length=1)
    modes: list[str] = Field(default_factory=lambda: ["normal", "scientific", "extreme"])
    min_strength: float = Field(default=0.0, ge=0, le=100)
    message: dict[str, str]
    emoji: str = ""
    trigger: str = ""


class FnbpVerdictSpec(BaseModel):
    """The verdict shown by the FNBP lab module (rules, not code)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    severity: Severity
    emoji: str = ""
    texts: dict[str, str]


class _SafeFormat(dict[str, Any]):
    """``str.format_map`` helper that never raises on a missing key."""

    def __missing__(self, key: str) -> str:
        return "—"


def format_template(template: str, values: dict[str, Any]) -> str:
    """Format ``template`` with ``values``, tolerating unknown placeholders."""

    try:
        return template.format_map(_SafeFormat(values))
    except (IndexError, ValueError):
        # A malformed placeholder in a user-supplied rule pack must not 500.
        return template


def resolve_localized(mapping: dict[str, str], language: str, fallback: str = "") -> str:
    """Pick the best available string for ``language``.

    Order: exact language, ``default``, English, first non-empty value,
    then ``fallback``.
    """

    if not mapping:
        return fallback
    for key in (language, "default", "en"):
        value = mapping.get(key)
        if value:
            return value
    for value in mapping.values():
        if value:
            return value
    return fallback


def resolve_verdict_text(
    texts: dict[str, str], language: str, mode: str, values: dict[str, Any] | None = None
) -> str:
    """Resolve a verdict string using ``lang.mode`` → ``mode`` → ``lang`` keys."""

    ordered = (f"{language}.{mode}", mode, language, "default", "en")
    raw = ""
    for key in ordered:
        candidate = texts.get(key)
        if candidate:
            raw = candidate
            break
    if not raw:
        raw = next((v for v in texts.values() if v), "")
    return format_template(raw, values or {})


class RuleBook(BaseModel):
    """Every rule pack, loaded and validated."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    version: str = "0.1.0"
    source_dir: Path
    signals: list[SignalRule] = Field(default_factory=list)
    modes: dict[str, ModeProfile] = Field(default_factory=dict)
    escape_tiers: list[EscapeTier] = Field(default_factory=list)
    keyword_escapes: list[KeywordEscape] = Field(default_factory=list)
    escape_messages: dict[str, str] = Field(default_factory=dict)
    verdicts: list[VerdictRule] = Field(default_factory=list)
    reality_checks: dict[str, RealityCheckTemplate] = Field(default_factory=dict)
    asymmetry: AsymmetryConfig = Field(default_factory=AsymmetryConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    easter_eggs: list[EasterEggRule] = Field(default_factory=list)
    fnbp: dict[str, FnbpVerdictSpec] = Field(default_factory=dict)
    fnbp_note: dict[str, str] = Field(default_factory=dict)
    #: The honesty clause shipped with every report.
    disclaimer: str = ""
    no_signal_label: str = "No emotional evidence detected"
    no_signal_labels: dict[str, str] = Field(default_factory=dict)
    no_signal_interpretation: dict[str, str] = Field(default_factory=dict)

    def no_signal_label_for(self, language: str) -> str:
        """Localized label used when nothing matched."""

        return resolve_localized(self.no_signal_labels, language, self.no_signal_label)

    def no_signal_text_for(self, language: str) -> str:
        """Localized plain reading used when nothing matched."""

        return resolve_localized(self.no_signal_interpretation, language, self.no_signal_label)

    @property
    def mode_ids(self) -> list[str]:
        return list(self.modes.keys())

    def mode(self, mode_id: str) -> ModeProfile:
        """Return a mode profile, falling back to the first configured mode."""

        if mode_id in self.modes:
            return self.modes[mode_id]
        return next(iter(self.modes.values()))

    def rules_for_polarity(self, polarity: str) -> list[SignalRule]:
        return [rule for rule in self.signals if rule.polarity == polarity]

    def reality_check(self, check_id: str, language: str, values: dict[str, Any]) -> str:
        template = self.reality_checks.get(check_id)
        if template is None:
            return ""
        return format_template(
            resolve_localized({"zh": template.zh, "en": template.en}, language), values
        )

    @classmethod
    def load(cls, directory: Path | None = None) -> RuleBook:
        """Load every rule pack from ``directory`` (default: packaged rules)."""

        base = directory or rules_dir()
        if not base.is_dir():
            raise FileNotFoundError(f"rule pack directory not found: {base}")

        def read(name: str) -> dict[str, Any]:
            path = base / name
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                raise ValueError(f"rule pack {name} must contain a JSON object")
            return payload

        signals_pack = read("signals.json")
        modes_pack = read("modes.json")
        escaping_pack = read("escaping.json")
        verdicts_pack = read("verdicts.json")
        reality_pack = read("reality_checks.json")
        asymmetry_pack = read("asymmetry.json")
        eggs_pack = read("easter_eggs.json")

        tiers = [EscapeTier.model_validate(item) for item in escaping_pack.get("tiers", [])]
        tiers.sort(key=lambda tier: tier.min_strength)

        verdicts = [VerdictRule.model_validate(item) for item in verdicts_pack.get("rules", [])]
        verdicts.sort(key=lambda rule: rule.priority)

        signals = [SignalRule.model_validate(item) for item in signals_pack.get("signals", [])]
        signal_ids = {rule.id for rule in signals}
        if len(signal_ids) != len(signals):
            raise ValueError("duplicate signal rule ids in signals.json")

        modes = {
            item["id"]: ModeProfile.model_validate(item) for item in modes_pack.get("modes", [])
        }
        if not modes:
            raise ValueError("modes.json defines no modes")

        asymmetry = AsymmetryConfig.model_validate(asymmetry_pack.get("config", {}) or {})
        scoring = ScoringConfig.model_validate(asymmetry_pack.get("scoring", {}) or {})

        reality_checks = {
            item["id"]: RealityCheckTemplate.model_validate(item)
            for item in reality_pack.get("checks", [])
        }

        return cls(
            version=str(signals_pack.get("version", "0.1.0")),
            source_dir=base,
            signals=signals,
            modes=modes,
            escape_tiers=tiers,
            keyword_escapes=[
                KeywordEscape.model_validate(item)
                for item in escaping_pack.get("keyword_escapes", [])
            ],
            escape_messages=dict(escaping_pack.get("messages", {})),
            verdicts=verdicts,
            reality_checks=reality_checks,
            asymmetry=asymmetry,
            scoring=scoring,
            easter_eggs=[EasterEggRule.model_validate(item) for item in eggs_pack.get("eggs", [])],
            fnbp={
                key: FnbpVerdictSpec.model_validate(value)
                for key, value in (verdicts_pack.get("fnbp") or {}).items()
            },
            fnbp_note=dict(verdicts_pack.get("fnbp_note") or {}),
            disclaimer=str(verdicts_pack.get("disclaimer", "")),
            no_signal_label=str(
                signals_pack.get("no_signal", {}).get("label", "No emotional evidence detected")
            ),
            no_signal_labels=dict(signals_pack.get("no_signal", {}).get("labels") or {}),
            no_signal_interpretation=dict(
                signals_pack.get("no_signal", {}).get("interpretation") or {}
            ),
        )

    def egg_hits(self, text: str, mode: str, language: str, strength: float) -> list[EasterEggHit]:
        """Evaluate easter-egg rules. Cosmetic only."""

        hits: list[EasterEggHit] = []
        for egg in self.easter_eggs:
            if mode not in egg.modes or strength < egg.min_strength:
                continue
            for pattern in egg.patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    hits.append(
                        EasterEggHit(
                            id=egg.id,
                            trigger=match.group(0),
                            message=resolve_localized(egg.message, language),
                            emoji=egg.emoji,
                        )
                    )
                    break
        return hits


__all__ = [
    "EasterEggRule",
    "EscapeTier",
    "HypothesisTemplate",
    "KeywordEscape",
    "RuleBook",
    "SignalRule",
    "VerdictRule",
    "format_template",
    "resolve_localized",
    "resolve_verdict_text",
]
