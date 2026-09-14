"""Engine configuration objects.

Configuration is data: it lives in the JSON rule packs under ``ned/app/rules``
and is loaded into the typed models below. Users can override the whole
directory with the ``NED_RULES_DIR`` environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

#: Environment variable pointing at an alternative rule-pack directory.
RULES_DIR_ENV = "NED_RULES_DIR"

#: Maximum accepted input length. NED analyses one message or one event
#: description, not an archive; a hard cap keeps the API cheap and predictable.
MAX_INPUT_CHARS = 8000

DEFAULT_MODE = "normal"


class ModeProfile(BaseModel):
    """Tuning knobs for one analysis mode.

    The modes are the only place where "how far NED is willing to go" is
    configured, so adding a mode is a data change, not a code change.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    label: str
    blurb: str
    #: Baseline share of positive evidence that NED discards, 0-100.
    discount_base: float = Field(ge=0, le=100)
    #: How many alternative explanations to surface.
    escape_count: int = Field(ge=1, le=10)
    #: Multiplier applied to the plausibility of every alternative explanation.
    plausibility_scale: float = Field(gt=0)
    #: Free-form tone tag, surfaced in the "mode notes" of a result.
    tone: str


class RealityCheckTemplate(BaseModel):
    """A bilingual reality-check sentence template."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    zh: str
    en: str


class ComparabilityConfig(BaseModel):
    """When two clues may not be compared as symmetric samples of one question.

    The detector measures an *interpretive* asymmetry: the same standard applied
    unevenly. That reading is only available when both sides are candidate
    answers to a similar question. An explicit boundary answers a different
    question (where the interaction now stands) and settles it by itself, and
    clues that sit in different states of the relationship are two observations
    rather than two standards, so in both cases NED declines the comparison
    instead of printing a severity band.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    #: Evidence classes that declare a rule about the interaction itself.
    boundary_classes: list[str] = Field(default_factory=lambda: ["boundary"])
    #: ``signal_type`` -> evidence class. Anything absent is "unclassified".
    evidence_classes: dict[str, str] = Field(default_factory=dict)
    #: Language-keyed markers that situate a clue in a later state.
    later_state_markers: dict[str, list[str]] = Field(default_factory=dict)
    #: Reported instead of a severity band when the comparison is declined.
    not_applicable_label: str = "NOT DIRECTLY COMPARABLE"
    #: Reported for both admission thresholds in that case.
    threshold_label: str = "NOT_COMPARABLE"


class AsymmetryConfig(BaseModel):
    """Weights and priors of the Evidence Asymmetry Detector.

    ``prior`` encodes the classic asymmetric prior NED assumes when the user
    supplies no interpretation of their own: positive evidence is discounted
    hard, negative evidence is accepted almost immediately. It is an explicit,
    documented assumption, not a measurement.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = "asymmetry"
    weight_gap_weight: float = Field(default=0.45, ge=0, le=1)
    information_gap_weight: float = Field(default=0.25, ge=0, le=1)
    categorical_weight: float = Field(default=0.30, ge=0, le=1)
    prior_positive_discount_multiplier: float = Field(default=0.35, ge=0, le=1)
    prior_negative_amplification_multiplier: float = Field(default=1.0, ge=0, le=3)
    categorical_negative_threshold: float = Field(default=75.0, ge=0, le=100)
    categorical_positive_threshold: float = Field(default=25.0, ge=0, le=100)
    high_positive_threshold: float = Field(default=25.0, ge=0, le=100)
    low_negative_threshold: float = Field(default=75.0, ge=0, le=100)
    #: Whether the two sides of a comparison are comparable at all.
    comparability: ComparabilityConfig = Field(default_factory=ComparabilityConfig)
    bands: list[tuple[float, float, str]] = Field(
        default_factory=lambda: [
            (0.0, 19.999, "NEGLIGIBLE"),
            (20.0, 39.999, "MILD"),
            (40.0, 59.999, "MODERATE"),
            (60.0, 79.999, "SEVERE"),
            (80.0, 100.0, "EXTREME"),
        ]
    )


class ReachingBand(BaseModel):
    """Maps a NED Reaching Level range to a human label."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min: float = Field(ge=0, le=100)
    max: float = Field(ge=0, le=100)
    label: str


class ScoringConfig(BaseModel):
    """Weights of the (deliberately transparent) NED scoring model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reaching_positive_weight: float = Field(default=0.62, ge=0, le=2)
    reaching_escape_weight: float = Field(default=28.0, ge=0, le=100)
    reaching_history_weight: float = Field(default=20.0, ge=0, le=100)
    capacity_positive_weight: float = Field(default=0.60, ge=0, le=1)
    capacity_history_weight: float = Field(default=0.40, ge=0, le=1)
    capacity_exhausted_threshold: float = Field(default=0.95, ge=0, le=1)
    capacity_warning_threshold: float = Field(default=0.80, ge=0, le=1)
    discount_escape_bonus: float = Field(default=12.0, ge=0, le=100)
    discount_amplification_bonus: float = Field(default=8.0, ge=0, le=100)
    negative_amplification_floor: float = Field(default=5.0, ge=0, le=100)
    reaching_bands: list[ReachingBand] = Field(
        default_factory=lambda: [
            ReachingBand(min=0, max=19.999, label="Reasonable skepticism"),
            ReachingBand(min=20, max=39.999, label="Routine doubt"),
            ReachingBand(min=40, max=59.999, label="Advanced overthinking"),
            ReachingBand(min=60, max=79.999, label="Industrial-grade denial"),
            ReachingBand(min=80, max=99.999, label="NED is currently reaching."),
            ReachingBand(min=100, max=100, label="人好。👍"),
        ]
    )


def rules_dir() -> Path:
    """Return the rule-pack directory, honouring ``NED_RULES_DIR``."""

    override = os.environ.get(RULES_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent / "rules"


__all__ = [
    "DEFAULT_MODE",
    "MAX_INPUT_CHARS",
    "RULES_DIR_ENV",
    "AsymmetryConfig",
    "ComparabilityConfig",
    "ModeProfile",
    "ReachingBand",
    "RealityCheckTemplate",
    "ScoringConfig",
    "rules_dir",
]
