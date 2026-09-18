"""M3: the longitudinal review engine, measured on the pinned scenarios.

These are the product rules of the batch, not the implementation: history never decides the
current case, a third party's stance never becomes her stance, ``saved_at`` never orders anything,
an unknown order is never guessed, and "boundary first" is not "boundary forever".
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ned.app.core.analyzer import NedAnalyzer
from ned.app.review import (
    CurrentCase,
    MaterialFacts,
    Order,
    RecordedDirection,
    Relation,
    RelationReason,
    ReviewRecord,
    TemporalWindow,
    build_casebook_review,
    compare,
    current_case_facts,
)

ANALYZER = NedAnalyzer()


def facts(text: str) -> list[MaterialFacts]:
    result = ANALYZER.analyze_text(text)
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


def current_for(text: str, occurred: str | None = None, precision: str = "unknown") -> CurrentCase:
    result = ANALYZER.analyze_text(text)
    return current_case_facts(
        materials=facts(text),
        signal_type=str(result.signal_type),
        verdict_code=result.verdict.code,
        occurred_at=occurred,
        occurred_precision=precision if occurred else "unknown",
        occurred_source="user" if occurred else "unknown",
    )


def case_file(
    text: str, *, item_id: str, occurred: str | None = None, precision: str = "day"
) -> ReviewRecord:
    """A record for a case whose input registered no comparable material."""

    result = ANALYZER.analyze_text(text)
    return ReviewRecord(
        item_kind="case_file",
        item_id=item_id,
        case_file_id="cf_" + item_id,
        reported_content=text,
        occurred_at=occurred,
        occurred_precision=precision if occurred else "unknown",
        occurred_source="user" if occurred else "unknown",
        recorded_verdict_code=result.verdict.code,
        recorded_verdict_text=result.verdict.text,
        recorded_signal_type=str(result.signal_type),
    )


def entry(
    text: str, *, item_id: str, occurred: str | None = None, precision: str = "day"
) -> ReviewRecord:
    """A record for one filed material."""

    result = ANALYZER.analyze_text(text)
    material = result.materials[0]
    return ReviewRecord(
        item_kind="entry",
        item_id=item_id,
        case_file_id="cf_" + item_id,
        entry_kind="event",
        material_kind=material.material_kind,
        reported_content=material.reported_content,
        occurred_at=occurred,
        occurred_precision=precision if occurred else "unknown",
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


def review(current: CurrentCase, records: list[ReviewRecord]):
    return build_casebook_review(
        casebook_id="cb_x",
        casebook_label="小 X",
        current=current,
        records=records,
        case_files_read=len({record.case_file_id for record in records}),
        entries_read=len([record for record in records if record.item_kind == "entry"]),
    )


def relation_of(result, item_id: str) -> Relation:
    for item in result.items:
        if item.item_id == item_id:
            return item.relation
    raise AssertionError(f"no row for {item_id}")


# ------------------------------------------------------------------ supports ---
def test_repeated_positive_history_supports_the_current_positive_case() -> None:
    """Pinned scenario 1: two positive records, a positive current case, no dates needed."""

    result = review(
        current_for("她今天又主动找我"),
        [
            case_file("她连续两次主动找我", item_id="cf1"),
            case_file("她主动问我周末有没有空", item_id="cf2"),
        ],
    )
    assert [item.relation for item in result.items] == [Relation.SUPPORTS, Relation.SUPPORTS]
    assert all(item.relation_reason is RelationReason.DIRECTION_AGREES for item in result.items)
    assert result.counts.supports == 2
    # ... and none of it proves a romance: the review states relations, not a conclusion.
    assert result.scored is False


def test_positive_material_supports_a_positive_current_case() -> None:
    result = review(
        current_for("她给我带了早餐"),
        [entry("她记得我生日", item_id="en1")],
    )
    assert relation_of(result, "en1") is Relation.SUPPORTS


# ----------------------------------------------------------------- conflicts ---
def test_a_current_boundary_conflicts_with_an_earlier_positive_record() -> None:
    """Pinned scenario 2: the order is unknown, so the boundary conflicts and does not govern."""

    result = review(
        current_for("她明确说只想做朋友"),
        [case_file("她说喜欢我", item_id="cf1")],
    )
    assert result.current_direction is RecordedDirection.BOUNDARY
    assert relation_of(result, "cf1") is Relation.CONFLICTS
    assert result.governing is None
    assert result.order_known is False


def test_a_dated_current_boundary_governs_and_supersedes_the_earlier_record() -> None:
    """The same sentence, now with both event times declared and safely ordered."""

    result = review(
        current_for("她明确说只想做朋友", occurred="2026-08-03", precision="day"),
        [case_file("她说喜欢我", item_id="cf1", occurred="2026-07-12", precision="day")],
    )
    assert relation_of(result, "cf1") is Relation.SUPERSEDED
    assert result.governing is not None
    assert result.governing.item_kind == "current_case"
    assert result.governing.occurred_at == "2026-08-03"
    assert result.items[0].superseded_by == "current_case"


# ---------------------------------------------------------------- superseded ---
def test_an_early_positive_material_is_superseded_by_a_later_boundary() -> None:
    """Pinned scenario 3, entirely inside the casebook's own history."""

    result = review(
        current_for("她给我带了早餐"),
        [
            entry("她记得我生日", item_id="en1", occurred="2026-07-12", precision="day"),
            entry("她说我们只是朋友", item_id="en2", occurred="2026-08-03", precision="day"),
        ],
    )
    assert relation_of(result, "en1") is Relation.SUPERSEDED
    assert relation_of(result, "en2") is Relation.CONFLICTS
    assert result.governing is not None
    assert result.governing.item_id == "en2"
    assert result.counts.superseded == 1


# --------------------------------------------------------------- third party ---
def test_third_party_opposition_is_never_her_stance() -> None:
    """Pinned scenario 4: her mother's objection may not become her rejection."""

    result = review(
        current_for("她今天又主动找我"),
        [entry("她妈妈反对我们在一起", item_id="en1")],
    )
    item = result.items[0]
    assert item.recorded_direction is RecordedDirection.THIRD_PARTY
    assert item.relation is Relation.NOT_COMPARABLE
    assert item.relation_reason is RelationReason.THIRD_PARTY_STANCE
    assert item.relation not in (Relation.SUPPORTS, Relation.CONFLICTS)
    assert result.counts.conflicts == 0


def test_a_third_party_activity_is_unrelated_rather_than_comparable() -> None:
    result = review(
        current_for("她给我带了早餐"),
        [entry("她跟朋友出去玩了", item_id="en1")],
    )
    assert result.items[0].relation is Relation.UNRELATED


# -------------------------------------------------------------- time unknown ---
def test_a_month_and_a_day_are_never_ordered_against_each_other() -> None:
    """Pinned scenario 5: 2026-03 against 2026-03-15 is not a comparison M3 may make."""

    result = review(
        current_for("她今天又主动找我"),
        [
            entry("她记得我生日", item_id="en1", occurred="2026-03", precision="month"),
            entry("她说我们只是朋友", item_id="en2", occurred="2026-03-15", precision="day"),
        ],
    )
    assert relation_of(result, "en1") is Relation.NOT_COMPARABLE
    assert result.items[0].relation_reason is RelationReason.BOUNDARY_ORDER_NOT_DETERMINABLE
    assert result.counts.superseded == 0


def test_two_boundaries_with_incomparable_dates_name_no_governing_entry() -> None:
    result = review(
        current_for("她给我带了早餐"),
        [
            entry("她说我们只是朋友", item_id="en1", occurred="2026-03", precision="month"),
            entry("她说我想多了", item_id="en2", occurred="2026-03-15", precision="day"),
        ],
    )
    assert result.governing is None
    assert result.order_known is False
    assert result.counts.superseded == 0


def test_undated_records_are_never_superseded() -> None:
    """No declared time means no order, and no order means no supersession."""

    result = review(
        current_for("她给我带了早餐"),
        [
            entry("她记得我生日", item_id="en1"),
            entry("她说我们只是朋友", item_id="en2"),
        ],
    )
    assert result.counts.superseded == 0
    assert result.governing is None


def test_saved_at_cannot_order_anything() -> None:
    """Filing time is not an input: the record type cannot carry it, and nothing reads it."""

    import dataclasses

    import ned.app.review.longitudinal as longitudinal

    names = {field.name for field in dataclasses.fields(ReviewRecord)}
    assert "saved_at" not in names
    assert "generated_at" not in names
    # The only clock the algorithm has is a declared event time, on the point it is handed.
    assert {field.name for field in dataclasses.fields(longitudinal.TemporalWindow)} == {
        "value",
        "precision",
        "source",
        "frame",
        "window",
    }
    source = Path(longitudinal.__file__).read_text(encoding="utf-8")
    assert ".saved_at" not in source


# ------------------------------------------------------------ boundary safety ---
def test_a_boundary_is_not_eternal() -> None:
    """A later positive fact is not swallowed by an older boundary."""

    result = review(
        current_for("她给我带了早餐"),
        [
            entry("她说我们只是朋友", item_id="en1", occurred="2026-01-05", precision="day"),
            entry("她记得我生日", item_id="en2", occurred="2026-08-03", precision="day"),
        ],
    )
    assert relation_of(result, "en1") is Relation.CONFLICTS
    assert relation_of(result, "en2") is Relation.SUPPORTS
    assert result.governing is None, "a later fact means the boundary is not the last word"
    assert result.counts.superseded == 0


def test_a_soft_decline_may_oppose_but_never_governs() -> None:
    """A soft fit judgement is a boundary for direction only: it never governs the file."""

    result = review(
        current_for("她给我带了早餐"),
        [entry("她说她喜欢我，但她觉得我们不太合适", item_id="en1", occurred="2026-08-03")],
    )
    assert result.items[0].recorded_direction is RecordedDirection.BOUNDARY
    assert relation_of(result, "en1") is Relation.CONFLICTS
    assert result.governing is None


# ----------------------------------------------------------- honest emptiness ---
def test_an_empty_casebook_says_so() -> None:
    result = review(current_for("她给我带了早餐"), [])
    assert result.summary_code == "no_history"
    assert result.counts.supports == 0 and result.counts.conflicts == 0


def test_a_current_case_without_a_reading_compares_with_nothing() -> None:
    """A case NED recognised nothing in has no direction to compare against."""

    result = review(
        current_for("今天食堂的饭难吃"),
        [entry("她记得我生日", item_id="en1")],
    )
    assert result.current_direction is RecordedDirection.NONE
    assert relation_of(result, "en1") is Relation.NOT_COMPARABLE
    assert result.items[0].relation_reason is RelationReason.CURRENT_CASE_HAS_NO_DIRECTION


def test_an_unknown_record_is_insufficient_rather_than_guessed() -> None:
    result = review(
        current_for("她给我带了早餐"),
        [
            ReviewRecord(
                item_kind="entry",
                item_id="en1",
                case_file_id="cf1",
                entry_kind="user_note",
                material_kind="user_note",
                reported_content="我自己写的一条备注",
                material=MaterialFacts(material_kind="user_note"),
            )
        ],
    )
    assert result.items[0].relation is Relation.INSUFFICIENT


# ------------------------------------------------------------- the safe clock ---
@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        # two declared days a month apart: same frame, disjoint windows
        (("2026-08-03", "day", "user"), ("2026-07-12", "day", "user"), Order.AFTER),
        # the same day twice: a recorded value, not an ordering
        (("2026-08-03", "day", "user"), ("2026-08-03", "day", "user"), Order.SAME),
        # a month contains that day: no order may be invented
        (("2026-03-15", "day", "user"), ("2026-03", "month", "user"), Order.NOT_COMPARABLE),
        # windows that are far apart are ordered even when the precisions differ
        (("2026-08-03", "day", "user"), ("2025-12", "month", "user"), Order.AFTER),
        # a relative clue has no window at all
        (
            ("2026-08-03", "day", "input_relative"),
            ("2026-07-12", "day", "user"),
            Order.NOT_COMPARABLE,
        ),
        # and neither has an unknown one
        ((None, "unknown", "unknown"), ("2026-07-12", "day", "user"), Order.NOT_COMPARABLE),
        # the same hour, same frame
        (("2026-08-03T14", "hour", "user"), ("2026-08-03T09", "hour", "user"), Order.AFTER),
    ],
)
def test_declared_times_are_ordered_by_their_windows(left, right, expected) -> None:
    assert compare(TemporalWindow.of(*left), TemporalWindow.of(*right)).order is expected


# --------------------------------------------------------------- no arithmetic ---
def test_the_review_never_produces_a_score() -> None:
    result = review(
        current_for("她给我带了早餐"),
        [entry("她记得我生日", item_id="en1"), entry("她说我们只是朋友", item_id="en2")],
    )
    payload = result.model_dump(mode="json")
    assert payload["scored"] is False
    assert "score" not in payload
    assert "percentage" not in payload
    assert set(payload["counts"]) == {
        "supports",
        "conflicts",
        "superseded",
        "unrelated",
        "not_comparable",
        "insufficient",
    }
