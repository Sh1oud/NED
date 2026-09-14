"""NED Personality Layer tests.

The layer may choose display copy from completed scores, but it must never
participate in calculation or extend an API result.
"""

from __future__ import annotations

import pytest
from ned.app.ui.personality import (
    FNBP_HIT_FEEDBACK,
    FNBP_MISS_FEEDBACK,
    analysis_feedback,
    asymmetry_feedback,
    fnbp_feedback,
    web_personality_catalog,
)


@pytest.mark.parametrize(
    ("score", "level"),
    [(59.9, None), (60.0, 1), (80.0, 2), (100.0, 3)],
)
def test_analysis_feedback_levels(score: float, level: int | None) -> None:
    feedback = analysis_feedback(score)
    assert (feedback.level if feedback else None) == level


@pytest.mark.parametrize(
    ("score", "level"),
    [(59.9, None), (81.8, 1), (90.0, 2), (100.0, 3)],
)
def test_asymmetry_feedback_levels(score: float, level: int | None) -> None:
    feedback = asymmetry_feedback(score)
    assert (feedback.level if feedback else None) == level


def test_personality_catalog_is_display_only_bilingual_copy() -> None:
    catalog = web_personality_catalog()
    assert catalog["analysis"]
    assert catalog["asymmetry"]
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
