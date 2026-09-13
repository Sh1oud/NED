"""FNBP (easter egg) tests."""

from __future__ import annotations

import pytest
from ned.app.core.fnbp import NotificationBranchPredictor
from ned.app.core.models import FnbpRequest
from ned.app.core.rules import RuleBook


@pytest.fixture
def predictor(book: RuleBook) -> NotificationBranchPredictor:
    return NotificationBranchPredictor(book)


def test_predictor_never_hits_when_the_sender_is_always_someone_else(
    predictor: NotificationBranchPredictor,
) -> None:
    result = predictor.run(
        FnbpRequest(expected_sender="Fuyuki", actual_senders=["张三"], notifications=5)
    )
    assert result.prediction_hits == 0
    assert result.prediction_misses == 5
    assert result.mispredict_rate == 100.0
    assert result.pipeline_flushes == 5
    assert result.wasted_cycles > 0
    assert result.verdict.code == "fnbp.mispredict"


def test_predictor_hits_when_the_sender_matches(
    predictor: NotificationBranchPredictor,
) -> None:
    result = predictor.run(
        FnbpRequest(expected_sender="Fuyuki", actual_senders=["Fuyuki"], notifications=4)
    )
    assert result.prediction_hits == 4
    assert result.prediction_misses == 0
    assert result.mispredict_rate == 0.0
    assert result.wasted_cycles == 0
    assert result.verdict.code == "fnbp.hit"


def test_confidence_rises_with_training(predictor: NotificationBranchPredictor) -> None:
    low = predictor.confidence_after(0)
    high = predictor.confidence_after(4)
    assert low < high
    assert high <= 0.99


def test_per_notification_report_is_complete(predictor: NotificationBranchPredictor) -> None:
    result = predictor.run(
        FnbpRequest(expected_sender="Fuyuki", actual_senders=["张三", "李四"], notifications=6)
    )
    assert len(result.per_notification) == 6
    for index, item in enumerate(result.per_notification, start=1):
        assert item.index == index
        assert item.predicted_sender == "Fuyuki"
        assert 0 <= item.predicted_probability <= 100
        assert item.actual_sender in {"张三", "李四"}
        assert item.pipeline_flushed is (not item.hit)


def test_empty_sender_list_degrades(predictor: NotificationBranchPredictor) -> None:
    result = predictor.run(
        FnbpRequest(expected_sender="Fuyuki", actual_senders=[], notifications=2)
    )
    assert len(result.per_notification) == 2
    assert result.prediction_misses == 2


def test_simulation_is_deterministic(predictor: NotificationBranchPredictor) -> None:
    request = FnbpRequest(
        expected_sender="Fuyuki", actual_senders=["张三"], notifications=5, seed=7
    )
    first = predictor.run(request)
    second = predictor.run(request)
    assert first.model_dump(exclude={"generated_at"}) == second.model_dump(exclude={"generated_at"})


def test_codename_note_states_that_fuyuki_is_fictional(
    predictor: NotificationBranchPredictor,
) -> None:
    chinese = predictor.run(FnbpRequest())
    assert "虚构" in chinese.codename_note
    assert "不是现实中的人物" in chinese.codename_note

    english = predictor.run(FnbpRequest(), language="en")
    assert "fictional" in english.codename_note.lower()
    assert "not a real person" in english.codename_note.lower()


def test_english_render(predictor: NotificationBranchPredictor) -> None:
    result = predictor.run(FnbpRequest(expected_sender="Alex"), language="en")
    assert result.verdict.text == "Why-is-it-never-her effect"
