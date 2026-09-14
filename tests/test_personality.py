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
