"""NED Personality Layer tests.

The layer may choose display copy from completed scores, but it must never
participate in calculation or extend an API result.
"""

from __future__ import annotations

import pytest
from ned.app.core.analyzer import NedAnalyzer
from ned.app.ui.personality import (
    FNBP_HIT_FEEDBACK,
    FNBP_MISS_FEEDBACK,
    NEA_FRAMING,
    READING_STATUS_MESSAGES,
    analysis_feedback,
    fnbp_feedback,
    nea_framing,
    reading_message,
    web_personality_catalog,
)


@pytest.mark.parametrize(
    ("score", "level"),
    [(59.9, None), (60.0, 1), (80.0, 2), (100.0, 3)],
)
def test_analysis_feedback_levels(score: float, level: int | None) -> None:
    feedback = analysis_feedback(score)
    assert (feedback.level if feedback else None) == level


def test_reaching_copy_belongs_to_ned() -> None:
    """Second-person attribution is not allowed on the reaching path."""

    for feedback in (analysis_feedback(100.0), analysis_feedback(80.0), analysis_feedback(60.0)):
        assert feedback is not None
        for text in (feedback.zh, feedback.en, feedback.technical):
            lowered = text.lower()
            assert "你的" not in text
            assert "your " not in lowered
            assert "you " not in lowered
    assert analysis_feedback(59.9) is None


def test_reading_copy_is_gated_by_the_user_layer() -> None:
    """Only a detected double standard yields copy about the reader."""

    assert reading_message("not_present", "zh") == (
        "输入中没有你的判断语言，NED 不评估你的证据标准。"
    )
    assert reading_message("not_present", "en").startswith("There is no interpretation language")
    assert "你的证据标准是否不对称" in reading_message("partial_basis", "zh")
    assert "你的证据标准不对称" in reading_message("asymmetric_standard_detected", "zh")
    assert "不可比" in reading_message("not_comparable", "zh")
    assert web_personality_catalog()["user_reading"] == READING_STATUS_MESSAGES


def test_no_second_person_copy_reaches_the_page_catalog() -> None:
    """The embedded catalog must not carry reader-directed copy by default."""

    catalog = web_personality_catalog()
    analysis = " ".join(item["zh"] + item["en"] + item["technical"] for item in catalog["analysis"])
    assert "你的结论" not in analysis
    assert "your questioning" not in analysis.lower()


def test_personality_catalog_is_display_only_bilingual_copy() -> None:
    catalog = web_personality_catalog()
    assert catalog["analysis"]
    assert catalog["user_reading"]
    assert "asymmetry" not in catalog, "the score-driven asymmetry copy is gone"
    assert catalog["fnbp"] == {"hit": FNBP_HIT_FEEDBACK, "miss": FNBP_MISS_FEEDBACK}


def test_fnbp_feedback_uses_completed_prediction_outcome() -> None:
    assert fnbp_feedback(0) == FNBP_HIT_FEEDBACK
    assert fnbp_feedback(1) == FNBP_MISS_FEEDBACK


def test_fnbp_hit_copy_says_one_hit_is_not_a_pattern() -> None:
    """A successful prediction keeps its verdict and gains the reminder."""

    feedback = fnbp_feedback(0)
    assert feedback == FNBP_HIT_FEEDBACK
    assert feedback["title"] == "🎯 命中了。"
    assert "一次预测成功，不等于发现了规律" in feedback["zh"]
    assert (
        feedback["en"] == "One successful prediction does not mean a pattern has been discovered."
    )


def test_fnbp_miss_copy_says_prediction_is_not_evidence() -> None:
    """A misprediction keeps its verdict and gains the reminder."""

    feedback = fnbp_feedback(4)
    assert feedback == FNBP_MISS_FEEDBACK
    assert feedback["title"] == "NED 提醒："
    assert "预测不是事实。期待也不是证据" in feedback["zh"]
    assert feedback["en"] == "Prediction is not reality. Expectation is not evidence."


def test_fnbp_reminder_is_display_only_and_not_in_the_api_payload() -> None:
    """The reminder is personality copy: it must never extend the FNBP result."""

    from ned.app.core.fnbp import NotificationBranchPredictor
    from ned.app.core.models import FnbpRequest
    from ned.app.core.rules import RuleBook

    result = NotificationBranchPredictor(RuleBook.load()).run(FnbpRequest(notifications=3))
    payload = result.model_dump(mode="json")

    assert "personality" not in payload
    assert "personality_feedback" not in payload
    blob = str(payload)
    assert "预测不是事实" not in blob
    assert "一次预测成功" not in blob


def test_nea_framing_is_bilingual_and_denies_being_a_conclusion() -> None:
    """The NEA panel says what the amplified reading is, and what it is not."""

    assert nea_framing("en") == (
        "This is the exaggerated interpretation NED is checking — not its conclusion."
    )
    assert nea_framing("zh") == "这是 NED 正在检查的夸大解读，不是 NED 的结论。"
    assert nea_framing("unknown") == NEA_FRAMING["zh"]
    assert web_personality_catalog()["nea_framing"] == NEA_FRAMING


def test_nea_framing_is_display_only_and_not_in_the_api_payload(analyzer: NedAnalyzer) -> None:
    """The framing line is personality copy: it must never extend an analysis."""

    result = analyzer.analyze_text("他让我滚出去别烦他了", mode="normal")
    blob = str(result.model_dump(mode="json"))

    assert "夸大解读" not in blob
    assert "exaggerated interpretation" not in blob
    assert "nea_framing" not in blob
