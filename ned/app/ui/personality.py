"""NED's display-only personality layer.

This module receives scores that have already been calculated and chooses copy for
the web UI and the human-readable CLI. It must never be imported by the core
analysis or scoring modules, and it deliberately adds nothing to API payloads.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PersonalityFeedback:
    """One bilingual display message for a completed result."""

    level: int
    minimum: float
    technical: str
    zh: str
    en: str


TECHNICAL_OVERREACH = "NED has detected evidence overreach."

ANALYSIS_FEEDBACK = (
    PersonalityFeedback(
        3,
        100.0,
        TECHNICAL_OVERREACH,
        "NED 认为，当前推理正在尝试逃离证据约束。请重新提交现实。👍",
        (
            "NED believes the current reasoning is attempting to escape evidence constraints. "
            "Please resubmit reality."
        ),
    ),
    PersonalityFeedback(
        2,
        80.0,
        TECHNICAL_OVERREACH,
        "警告：你的结论已经超过证据许可范围。🤠",
        "Warning: Your conclusion has exceeded the allowed evidence range.",
    ),
    PersonalityFeedback(
        1,
        60.0,
        TECHNICAL_OVERREACH,
        "NED 已经开始怀疑你的怀疑。🤠",
        "NED has started questioning your questioning.",
    ),
)

# An 81.8 asymmetry score is intentionally still Level 1: the detector has
# exposed a double standard, but NED reserves theatrical warnings for the
# near-total (90+) and total (100) states.
ASYMMETRY_FEEDBACK = (
    PersonalityFeedback(
        3,
        100.0,
        TECHNICAL_OVERREACH,
        "NED 认为，当前推理正在尝试逃离证据约束。请重新提交现实。👍",
        (
            "NED believes the current reasoning is attempting to escape evidence constraints. "
            "Please resubmit reality."
        ),
    ),
    PersonalityFeedback(
        2,
        90.0,
        TECHNICAL_OVERREACH,
        "警告：你的结论已经超过证据许可范围。🤠",
        "Warning: Your conclusion has exceeded the allowed evidence range.",
    ),
    PersonalityFeedback(
        1,
        60.0,
        TECHNICAL_OVERREACH,
        "NED 已经开始怀疑你的怀疑。🤠",
        "NED has started questioning your questioning.",
    ),
)

FNBP_HIT_FEEDBACK = {
    "title": "🎯 命中了。",
    "zh": "但 NED 提醒：一次预测成功，不等于发现了规律。🤠",
    "en": "One successful prediction does not mean a pattern has been discovered.",
}

FNBP_MISS_FEEDBACK = {
    "title": "NED 提醒：",
    "zh": "预测不是事实。期待也不是证据。🤠",
    "en": "Prediction is not reality. Expectation is not evidence.",
}


#: One-line framing for the Negative Evidence Amplifier panel: the amplified
#: reading is the interpretation under test, never NED's own conclusion.
NEA_FRAMING = {
    "en": "This is the exaggerated interpretation NED is checking — not its conclusion.",
    "zh": "这是 NED 正在检查的夸大解读，不是 NED 的结论。",
}


def nea_framing(language: str) -> str:
    """Framing line for the NEA panel, in the language of the analysis."""

    return NEA_FRAMING["en"] if language == "en" else NEA_FRAMING["zh"]


def _feedback_for(
    score: float, levels: tuple[PersonalityFeedback, ...]
) -> PersonalityFeedback | None:
    """Return display copy for an already-calculated score."""

    return next((feedback for feedback in levels if score >= feedback.minimum), None)


def analysis_feedback(reaching_level: float) -> PersonalityFeedback | None:
    """Personality copy for an Analyze Evidence reaching level."""

    return _feedback_for(reaching_level, ANALYSIS_FEEDBACK)


def asymmetry_feedback(asymmetry_score: float) -> PersonalityFeedback | None:
    """Personality copy for an Asymmetry Detector score."""

    return _feedback_for(asymmetry_score, ASYMMETRY_FEEDBACK)


def fnbp_feedback(prediction_misses: int) -> dict[str, str]:
    """Choose display-only FNBP copy from an already-calculated outcome."""

    return FNBP_MISS_FEEDBACK if prediction_misses > 0 else FNBP_HIT_FEEDBACK


def web_personality_catalog() -> dict[str, object]:
    """Serialize display copy for the local web page, never an API response."""

    return {
        "analysis": [asdict(feedback) for feedback in ANALYSIS_FEEDBACK],
        "asymmetry": [asdict(feedback) for feedback in ASYMMETRY_FEEDBACK],
        "fnbp": {"hit": FNBP_HIT_FEEDBACK, "miss": FNBP_MISS_FEEDBACK},
        "nea_framing": NEA_FRAMING,
    }


__all__ = [
    "ANALYSIS_FEEDBACK",
    "ASYMMETRY_FEEDBACK",
    "FNBP_HIT_FEEDBACK",
    "FNBP_MISS_FEEDBACK",
    "NEA_FRAMING",
    "PersonalityFeedback",
    "analysis_feedback",
    "asymmetry_feedback",
    "fnbp_feedback",
    "nea_framing",
    "web_personality_catalog",
]
