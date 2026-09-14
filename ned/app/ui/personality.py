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


TECHNICAL_REACHING = "NED's own explanations are getting strained."

#: Reaching is about NED's own behaviour: how hard it is working to keep
#: uncertainty alive about evidence it has already read. No second person here —
#: anything about the reader's standard belongs to the user-interpretation layer.
ANALYSIS_FEEDBACK = (
    PersonalityFeedback(
        3,
        100.0,
        TECHNICAL_REACHING,
        "NED 已经没有更好的解释，只能重复自己。👍",
        "NED has run out of better explanations and is repeating itself.",
    ),
    PersonalityFeedback(
        2,
        80.0,
        TECHNICAL_REACHING,
        "NED 正在为了维持不确定性而越来越用力。🤠",
        "NED is leaning harder and harder to keep uncertainty alive. 🤠",
    ),
    PersonalityFeedback(
        1,
        60.0,
        TECHNICAL_REACHING,
        "NED 的替代解释正在开始变得牵强。🤠",
        "NED's alternative explanations are starting to get strained. 🤠",
    ),
)


#: Display-only sentences for the user-interpretation layer. They are the only
#: copy allowed to speak about the reader's standard, and the last one is only
#: used when the layer detected a basis on both sides.
READING_STATUS_MESSAGES = {
    "not_present": {
        "zh": "输入中没有你的判断语言，NED 不评估你的证据标准。",
        "en": (
            "There is no interpretation language in the input, so NED does not assess "
            "your evidential standard."
        ),
    },
    "partial_basis": {
        "zh": "输入里的判断语言只出现在一侧；NED 不据此判断你的证据标准是否不对称。",
        "en": (
            "The input contains interpretation language on one side only, so NED does not judge "
            "your standard from it."
        ),
    },
    "asymmetric_standard_detected": {
        "zh": "检测到你的证据标准不对称：你对正向证据做了降权，又对负向证据下了结论。",
        "en": (
            "Your evidential standard looks uneven: you discounted the good news and drew a "
            "conclusion from the bad news."
        ),
    },
    "not_comparable": {
        "zh": "这对证据不可比，NED 不评估你的证据标准。",
        "en": (
            "These two clues are not comparable, so NED does not assess your evidential standard."
        ),
    },
}


def reading_message(status: str, language: str) -> str:
    """Display copy for one user-reading status."""

    messages = READING_STATUS_MESSAGES.get(status) or READING_STATUS_MESSAGES["not_present"]
    return messages["en"] if language == "en" else messages["zh"]


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
    score: float | None, levels: tuple[PersonalityFeedback, ...]
) -> PersonalityFeedback | None:
    """Return display copy for an already-calculated score.

    ``None`` means no comparable score was produced, so there is nothing to
    comment on and no copy is shown.
    """

    if score is None:
        return None
    return next((feedback for feedback in levels if score >= feedback.minimum), None)


def analysis_feedback(reaching_level: float) -> PersonalityFeedback | None:
    """Personality copy for an Analyze Evidence reaching level."""

    return _feedback_for(reaching_level, ANALYSIS_FEEDBACK)


def fnbp_feedback(prediction_misses: int) -> dict[str, str]:
    """Choose display-only FNBP copy from an already-calculated outcome."""

    return FNBP_MISS_FEEDBACK if prediction_misses > 0 else FNBP_HIT_FEEDBACK


def web_personality_catalog() -> dict[str, object]:
    """Serialize display copy for the local web page, never an API response."""

    return {
        "analysis": [asdict(feedback) for feedback in ANALYSIS_FEEDBACK],
        "fnbp": {"hit": FNBP_HIT_FEEDBACK, "miss": FNBP_MISS_FEEDBACK},
        "nea_framing": NEA_FRAMING,
        "user_reading": READING_STATUS_MESSAGES,
    }


__all__ = [
    "ANALYSIS_FEEDBACK",
    "FNBP_HIT_FEEDBACK",
    "FNBP_MISS_FEEDBACK",
    "NEA_FRAMING",
    "READING_STATUS_MESSAGES",
    "TECHNICAL_REACHING",
    "PersonalityFeedback",
    "analysis_feedback",
    "fnbp_feedback",
    "nea_framing",
    "reading_message",
    "web_personality_catalog",
]
