"""M4B: temporal windows - the pinned cases, the provable boundary, and property tests.

The whole point of the batch is that ``governing`` and ``superseded`` may only appear when the
order is *proved*. So the comparator is tested the way a proof is tested:

* the pinned cases the commander named;
* the boundary condition of the safety envelope, at the edge and one hour inside it;
* property tests: for randomly generated window pairs, every ``BEFORE``/``AFTER`` verdict is
  attacked with sampled instants and *adversarial* zone offsets (independent for a naive value,
  shared for two naive values) - no counterexample may exist;
* and every refusal carries a witness: an admissible pair of instants that really does contradict
  an order, or two windows that really do share an instant.
"""

from __future__ import annotations

import dataclasses
import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from ned.app.core.analyzer import NedAnalyzer
from ned.app.review import (
    MAX_OFFSET_EAST,
    MAX_OFFSET_WEST,
    ZONE_ENVELOPE,
    Frame,
    MaterialFacts,
    Order,
    OrderReason,
    Relation,
    TemporalWindow,
    build_casebook_review,
    compare,
    current_case_facts,
    strictly_before,
)
from ned.app.review import longitudinal as longitudinal_module

REPO = Path(__file__).resolve().parents[1]
TEMPORAL_SOURCE = (REPO / "ned" / "app" / "review" / "temporal.py").read_text(encoding="utf-8")
LONGITUDINAL_SOURCE = (REPO / "ned" / "app" / "review" / "longitudinal.py").read_text(
    encoding="utf-8"
)


def window(value: str | None, precision: str, source: str = "user") -> TemporalWindow:
    return TemporalWindow.of(value, precision, source)


# ------------------------------------------------------------------ the pinned cases ---
def test_a_month_is_ordered_against_another_month() -> None:
    """2026-03 < 2026-04: two whole months, same frame, disjoint windows."""

    result = compare(window("2026-03", "month"), window("2026-04", "month"))
    assert result.order is Order.BEFORE
    assert result.reason is OrderReason.DISJOINT_LOCAL


def test_a_month_that_contains_a_day_is_not_ordered() -> None:
    """2026-03 vs 2026-03-15: containment, so nothing may be claimed."""

    result = compare(window("2026-03-15", "day"), window("2026-03", "month"))
    assert result.order is Order.NOT_COMPARABLE
    assert result.reason is OrderReason.CONTAINMENT


def test_a_year_that_contains_a_month_is_not_ordered() -> None:
    """2026 vs 2026-08: the year is the wider window."""

    result = compare(window("2026", "year"), window("2026-08", "month"))
    assert result.order is Order.NOT_COMPARABLE
    assert result.reason is OrderReason.CONTAINMENT


def test_a_zoned_value_is_never_ordered_against_a_close_naive_one() -> None:
    """The M3 unsafe case: 2026-02-06T18Z against 2026-02-07T07 with no zone."""

    result = compare(window("2026-02-06T18Z", "hour"), window("2026-02-07T07", "hour"))
    assert result.order is Order.NOT_COMPARABLE
    assert result.reason is OrderReason.ZONE_FRAME_MISMATCH


def test_two_zoned_values_are_ordered_exactly() -> None:
    result = compare(window("2026-03-15T13Z", "hour"), window("2026-03-15T14Z", "hour"))
    assert result.order is Order.BEFORE
    assert result.reason is OrderReason.DISJOINT_UTC
    # a minute contains that second: exactness cuts both ways
    assert (
        compare(
            window("2026-03-15T14:30:30Z", "second"), window("2026-03-15T14:30Z", "minute")
        ).order
        is Order.NOT_COMPARABLE
    )


def test_two_naive_values_in_one_frame_are_ordered_when_their_windows_separate() -> None:
    result = compare(window("2025-12", "month"), window("2026-03-15", "day"))
    assert result.order is Order.BEFORE
    assert result.reason is OrderReason.DISJOINT_LOCAL


def test_a_mixed_pair_with_a_large_gap_is_still_ordered() -> None:
    """Zoned vs naive is refused only when the envelope overlaps: a wide gap settles it."""

    far = compare(window("2026-02-06T18Z", "hour"), window("2026-02-09T07", "hour"))
    assert far.order is Order.BEFORE
    assert far.reason is OrderReason.DISJOINT_BEYOND_ZONE_ENVELOPE
    # ... and a pair an hour apart is refused, which is the whole point.
    near = compare(window("2026-02-06T18Z", "hour"), window("2026-02-06T19", "hour"))
    assert near.order is Order.NOT_COMPARABLE


def test_input_relative_never_takes_part_in_ordering() -> None:
    for source in ("input_relative", "unknown"):
        result = compare(window("2026-02-07", "day", source), window("2026-02-06", "day", "user"))
        assert result.order is Order.NOT_COMPARABLE
        assert result.reason is OrderReason.NO_DERIVED_WINDOW


def test_two_records_with_no_window_are_not_the_same_record() -> None:
    """No window on either side is "cannot compare", not "identical"."""

    unreadable = window(None, "unknown", "unknown")
    result = compare(unreadable, window(None, "unknown", "unknown"))
    assert result.order is Order.NOT_COMPARABLE
    assert result.reason is OrderReason.NO_DERIVED_WINDOW
    relative = compare(
        window("2026-03", "month", "input_relative"), window("2026-04", "month", "input_relative")
    )
    assert relative.order is Order.NOT_COMPARABLE


def test_two_undated_records_do_not_become_a_support() -> None:
    """The engine-level consequence: an undated positive stays uncomparable, it is not promoted."""

    analyzer = NedAnalyzer()
    review = _review(
        analyzer,
        "她给我带了早餐",
        [
            ("en1", "她记得我生日", None, "unknown"),
            ("en2", "她说我们只是朋友", None, "unknown"),
        ],
    )
    assert next(item for item in review.items if item.item_id == "en1").relation is (
        Relation.NOT_COMPARABLE
    )
    assert review.counts.supports == 0
    assert review.counts.superseded == 0
    assert review.governing is None


def test_an_identical_record_is_same_rather_than_later() -> None:
    result = compare(window("2026-08-03", "day"), window("2026-08-03", "day"))
    assert result.order is Order.SAME
    assert result.reason is OrderReason.SAME_RECORDED_VALUE


# ----------------------------------------------------------------- window shapes ---
@pytest.mark.parametrize(
    ("value", "precision", "lower", "upper"),
    [
        ("2026", "year", datetime(2026, 1, 1), datetime(2027, 1, 1)),
        ("2026-03", "month", datetime(2026, 3, 1), datetime(2026, 4, 1)),
        ("2026-12", "month", datetime(2026, 12, 1), datetime(2027, 1, 1)),
        ("2026-03-15", "day", datetime(2026, 3, 15), datetime(2026, 3, 16)),
        ("2026-03-15T14", "hour", datetime(2026, 3, 15, 14), datetime(2026, 3, 15, 15)),
        (
            "2026-03-15T14:30",
            "minute",
            datetime(2026, 3, 15, 14, 30),
            datetime(2026, 3, 15, 14, 31),
        ),
        (
            "2026-03-15T14:30:12",
            "second",
            datetime(2026, 3, 15, 14, 30, 12),
            datetime(2026, 3, 15, 14, 30, 13),
        ),
    ],
)
def test_each_precision_is_a_window_not_a_timestamp(value, precision, lower, upper) -> None:
    built = window(value, precision)
    assert built.frame is Frame.NAIVE
    assert built.window == (lower, upper)


def test_a_trailing_zone_is_a_frame_and_not_decoration() -> None:
    zoned = window("2026-03-15T14Z", "hour")
    naive = window("2026-03-15T14", "hour")
    assert zoned.frame is Frame.ZONED and naive.frame is Frame.NAIVE
    assert zoned.window == naive.window  # same numbers, different frames
    assert zoned.utc_span() == zoned.window
    assert naive.utc_span() == (
        naive.window[0] - MAX_OFFSET_EAST,
        naive.window[1] + MAX_OFFSET_WEST,
    )


@pytest.mark.parametrize(
    ("value", "precision", "source"),
    [
        (None, "unknown", "unknown"),
        ("", "unknown", "unknown"),
        ("2026-03", "month", "input_relative"),
        ("2026-03", "month", "unknown"),
        ("not-a-date", "day", "user"),
        ("2026-03", "day", "user"),  # wrong shape for the declared precision
        ("2026-13", "month", "user"),  # a month that does not exist
        ("2026-03-15T25Z", "hour", "user"),
    ],
)
def test_a_value_without_a_readable_window_is_unknown(value, precision, source) -> None:
    built = window(value, precision, source)
    assert built.frame is Frame.UNKNOWN
    assert built.window is None
    assert not built.comparable


# ---------------------------------------------------- the envelope, provably ---
def test_the_envelope_is_the_world_offset_range_and_not_a_threshold() -> None:
    assert timedelta(hours=14) == MAX_OFFSET_EAST
    assert timedelta(hours=12) == MAX_OFFSET_WEST
    assert ZONE_ENVELOPE == MAX_OFFSET_EAST + MAX_OFFSET_WEST
    assert "UTC+14" in TEMPORAL_SOURCE and "UTC-12" in TEMPORAL_SOURCE
    assert "image of the local window" in TEMPORAL_SOURCE


def test_a_naive_value_earlier_by_exactly_the_west_envelope_still_precedes() -> None:
    """The edge: the naive window's latest possible UTC instant *is* the zoned instant."""

    naive = window("2026-03-14", "day")
    assert naive.window[1] + MAX_OFFSET_WEST == window("2026-03-15T12Z", "hour").window[0]
    assert compare(naive, window("2026-03-15T12Z", "hour")).order is Order.BEFORE
    # one hour of calendar closer and the proof is gone
    assert compare(naive, window("2026-03-15T11Z", "hour")).order is Order.NOT_COMPARABLE


def test_a_zoned_value_earlier_by_exactly_the_east_envelope_still_precedes() -> None:
    zoned = window("2026-03-15T12Z", "hour")
    later = window("2026-03-16T03", "hour")
    assert later.window[0] - MAX_OFFSET_EAST == zoned.window[1]
    assert compare(zoned, later).order is Order.BEFORE
    assert compare(zoned, window("2026-03-16T02", "hour")).order is Order.NOT_COMPARABLE


# ------------------------------------------------------------------ property tests ---
def _instant(lo: datetime, hi: datetime, rng: random.Random) -> datetime:
    span = max((hi - lo).total_seconds(), 1e-6)
    return lo + timedelta(seconds=rng.uniform(0, span - 1e-6))


def _offset(rng: random.Random) -> timedelta:
    return timedelta(
        hours=rng.uniform(
            -MAX_OFFSET_WEST / timedelta(hours=1), MAX_OFFSET_EAST / timedelta(hours=1)
        )
    )


def _random_window(rng: random.Random) -> TemporalWindow:
    precision = rng.choice(["year", "month", "day", "hour", "minute", "second"])
    year = rng.choice([2024, 2025, 2026])
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    hour = rng.randint(0, 23)
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    zoned = rng.random() < 0.5 and precision in ("hour", "minute", "second")
    suffix = "Z" if zoned else ""
    value = {
        "year": f"{year:04d}",
        "month": f"{year:04d}-{month:02d}",
        "day": f"{year:04d}-{month:02d}-{day:02d}",
        "hour": f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}{suffix}",
        "minute": f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}{suffix}",
        "second": f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}{suffix}",
    }[precision]
    return window(value, precision)


def test_property_a_decided_order_has_no_counterexample() -> None:
    """Whatever the comparator decides, sampling cannot break it - even adversarial zones."""

    rng = random.Random(20260918)
    decided = 0
    for _ in range(400):
        left = _random_window(rng)
        right = _random_window(rng)
        result = compare(left, right)
        if not result.decided:
            continue
        decided += 1
        assert left.window is not None and right.window is not None
        for _sample in range(12):
            left_instant = _instant(*left.window, rng)
            right_instant = _instant(*right.window, rng)
            if left.frame is Frame.NAIVE and right.frame is Frame.NAIVE:
                # two naive readings: one reader, therefore one shared offset
                shift = _offset(rng)
                left_utc, right_utc = left_instant + shift, right_instant + shift
            else:
                # zoned against naive: the naive side may be in *any* legal zone
                left_shift = timedelta(0) if left.frame is Frame.ZONED else _offset(rng)
                right_shift = timedelta(0) if right.frame is Frame.ZONED else _offset(rng)
                left_utc, right_utc = left_instant + left_shift, right_instant + right_shift
            if result.order is Order.BEFORE:
                assert left_utc < right_utc, (left.label(), right.label(), result)
            else:
                assert right_utc < left_utc, (left.label(), right.label(), result)
    assert decided > 20, decided


def test_property_a_refusal_has_a_witness() -> None:
    """Every refusal is justified: the two possible-instant sets really do overlap, and for a
    mixed pair that overlap is reachable by legal zone interpretations."""

    rng = random.Random(7)
    refusals = 0
    for _ in range(400):
        left = _random_window(rng)
        right = _random_window(rng)
        result = compare(left, right)
        if result.order is not Order.NOT_COMPARABLE:
            continue
        refusals += 1
        left_span, right_span = left.utc_span(), right.utc_span()
        assert left_span is not None and right_span is not None
        overlap = left_span[0] < right_span[1] and right_span[0] < left_span[1]
        assert overlap, (left.label(), right.label(), result)
        if left.frame is Frame.NAIVE and right.frame is Frame.NAIVE:
            continue  # same frame: a shared instant is the witness
        naive = left if left.frame is Frame.NAIVE else right
        zoned = right if naive is left else left
        assert naive.window is not None and zoned.window is not None
        early_naive_utc = naive.window[0] - MAX_OFFSET_EAST
        late_naive_utc = naive.window[1] + MAX_OFFSET_WEST - timedelta(seconds=1)
        zoned_first = zoned.window[0]
        zoned_last = zoned.window[1] - timedelta(seconds=1)
        assert late_naive_utc > zoned_first or early_naive_utc < zoned_last, (
            naive.label(),
            zoned.label(),
        )
    assert refusals > 20, refusals


def test_the_comparator_is_the_only_opinion_about_later() -> None:
    assert "safely_later" not in LONGITUDINAL_SOURCE
    assert "COMPARABLE_PRECISIONS" not in LONGITUDINAL_SOURCE
    assert ".occurred_at >" not in LONGITUDINAL_SOURCE
    assert ".occurred_at <" not in LONGITUDINAL_SOURCE
    assert "strictly_before(" in LONGITUDINAL_SOURCE
    assert "undecidable(" in LONGITUDINAL_SOURCE


def test_the_comparator_cannot_read_saved_at() -> None:
    """Filing time is not an input: the window type has no such field, and nothing reads it."""

    names = {field.name for field in dataclasses.fields(TemporalWindow)}
    assert names == {"value", "precision", "source", "frame", "window"}
    # no attribute access anywhere, and no field that could carry it
    assert ".saved_at" not in TEMPORAL_SOURCE
    assert ".saved_at" not in LONGITUDINAL_SOURCE
    assert "saved_at" not in {
        field.name
        for field in dataclasses.fields(
            __import__("ned.app.review", fromlist=["ReviewRecord"]).ReviewRecord
        )
    }
    # the docstrings may *say* filing time is not an input; the comparators never receive it
    assert "saved_at" in TEMPORAL_SOURCE  # ... in prose, which is the honest place for it


# ------------------------------------------------- governing / superseded integration ---
def _material_facts(result) -> list[MaterialFacts]:
    return [
        MaterialFacts(
            material_kind=material.material_kind,
            origin_rule_id=material.origin_rule_id,
            polarity=str(material.polarity),
            proposition_owner=material.proposition_owner,
            target=material.target,
        )
        for material in result.materials
    ]


def _records(analyzer: NedAnalyzer, rows) -> list:
    from ned.app.review import ReviewRecord

    built = []
    for item_id, text, occurred, precision in rows:
        result = analyzer.analyze_text(text)
        material = result.materials[0]
        built.append(
            ReviewRecord(
                item_kind="entry",
                item_id=item_id,
                case_file_id="cf_" + item_id,
                entry_kind="event",
                material_kind=material.material_kind,
                reported_content=material.reported_content,
                occurred_at=occurred,
                occurred_precision=precision,
                occurred_source="user" if occurred else "unknown",
                recorded_verdict_code=result.verdict.code,
                recorded_signal_type=str(result.signal_type),
                material=MaterialFacts(
                    material_kind=material.material_kind,
                    origin_rule_id=material.origin_rule_id,
                    polarity=str(material.polarity),
                    proposition_owner=material.proposition_owner,
                    target=material.target,
                ),
            )
        )
    return built


def _review(analyzer: NedAnalyzer, current_text: str, rows):
    result = analyzer.analyze_text(current_text)
    current = current_case_facts(
        materials=_material_facts(result),
        signal_type=str(result.signal_type),
        verdict_code=result.verdict.code,
    )
    return build_casebook_review(
        casebook_id="cb_x",
        casebook_label="小 X",
        current=current,
        records=_records(analyzer, rows),
        case_files_read=len(rows),
        entries_read=len(rows),
    )


def test_an_early_positive_is_superseded_only_because_the_boundary_is_provably_later() -> None:
    analyzer = NedAnalyzer()
    review = _review(
        analyzer,
        "她给我带了早餐",
        [
            ("en1", "她记得我生日", "2026-07-12", "day"),
            ("en2", "她说我们只是朋友", "2026-08-03", "day"),
        ],
    )
    assert strictly_before(window("2026-07-12", "day"), window("2026-08-03", "day"))
    row = next(item for item in review.items if item.item_id == "en1")
    assert row.relation is Relation.SUPERSEDED
    assert row.superseded_by == "en2"
    assert review.governing is not None and review.governing.item_id == "en2"


def test_an_early_positive_is_not_superseded_when_the_order_is_unprovable() -> None:
    """A month boundary against a day inside it: the pair cannot be ordered, so nothing is folded."""

    analyzer = NedAnalyzer()
    review = _review(
        analyzer,
        "她给我带了早餐",
        [
            ("en1", "她记得我生日", "2026-03-15", "day"),
            ("en2", "她说我们只是朋友", "2026-03", "month"),
        ],
    )
    assert compare(window("2026-03-15", "day"), window("2026-03", "month")).order is (
        Order.NOT_COMPARABLE
    )
    assert review.counts.superseded == 0
    # the order is unknown, so no boundary is called the file's state either
    assert review.governing is None
    assert review.governing_reason == "order_not_determinable"
    assert next(item for item in review.items if item.item_id == "en1").relation is (
        Relation.NOT_COMPARABLE
    )


def test_a_boundary_is_not_eternal_when_the_later_fact_is_provably_later() -> None:
    analyzer = NedAnalyzer()
    review = _review(
        analyzer,
        "她给我带了早餐",
        [
            ("en1", "她说我们只是朋友", "2026-01-05", "day"),
            ("en2", "她记得我生日", "2026-08-03", "day"),
        ],
    )
    assert strictly_before(window("2026-01-05", "day"), window("2026-08-03", "day"))
    assert review.governing is None
    assert review.counts.superseded == 0
    assert next(item for item in review.items if item.item_id == "en2").relation is (
        Relation.SUPPORTS
    )
    assert review.governing_reason == "later_record_after_boundary"


def test_the_m3_unsafe_pair_no_longer_produces_a_later_fact() -> None:
    """At review level: the boundary is not displaced by a record it cannot be compared with."""

    analyzer = NedAnalyzer()
    review = _review(
        analyzer,
        "她给她带了早餐".replace("她给", "她给"),
        [
            ("en1", "她说我们只是朋友", "2026-02-06T18Z", "hour"),
            ("en2", "她记得我生日", "2026-02-07T07", "hour"),
        ],
    )
    assert (
        compare(window("2026-02-06T18Z", "hour"), window("2026-02-07T07", "hour")).order
        is Order.NOT_COMPARABLE
    )
    assert review.counts.superseded == 0
    # an unknown order names no governing entry - the boundary is not displaced, it is simply not
    # claimed, and the row that cannot be ordered says so
    assert review.governing is None
    assert review.governing_reason == "order_not_determinable"
    assert next(item for item in review.items if item.item_id == "en2").relation is (
        Relation.NOT_COMPARABLE
    )


def test_the_review_module_still_cannot_reach_the_store_or_the_engine() -> None:
    assert "ned.app.store" not in LONGITUDINAL_SOURCE
    assert "analyzer" not in LONGITUDINAL_SOURCE
    assert "analyze_text" not in LONGITUDINAL_SOURCE
    assert longitudinal_module.__name__ == "ned.app.review.longitudinal"
