"""The longitudinal review algorithm: recorded facts in, relations and one sentence out.

Deterministic, pure, and narrow on purpose. It reads only what an archive recorded - the entry as
it was filed, and the case file's own recorded reading - and it never touches the current case's
verdict, evidence, materials, breakdown, recognition or capacity. Nothing here can change them:
the review is built *beside* the report.

Time discipline (the part that is easy to get wrong):

* ``saved_at`` is not an input. :class:`ReviewRecord` has no such field, so the algorithm cannot
  order anything by when it was filed. Only a declared event time can order two records;
* a declared time is a **window in a frame**, never a padded timestamp
  (:mod:`ned.app.review.temporal`). ``2026-03`` is the whole of March; a month that contains a day
  cannot be ordered against it;
* every ordering question in this module - which boundary is latest, whether a record is really
  later than a boundary - is answered by that one comparator. There is no second opinion about
  "later" anywhere in the review;
* a boundary governs only when its ordering against every other candidate is safe. Otherwise the
  review says so and names no governing entry;
* "boundary first" is not "boundary forever": a record that is provably later than a boundary is
  not superseded by it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ned.app.review.models import (
    CasebookReview,
    GoverningReason,
    RecordedDirection,
    Relation,
    RelationReason,
    ReviewCounts,
    ReviewFamily,
    ReviewGoverning,
    ReviewItem,
    SummaryCode,
)
from ned.app.review.relations import (
    CaseFileClass,
    MaterialFacts,
    classify_case_file,
    classify_material,
    directions_agree,
)
from ned.app.review.temporal import (
    TemporalWindow,
    strictly_before,
    undecidable,
)


@dataclass(frozen=True)
class ReviewRecord:
    """One archived thing, exactly as it was recorded.

    An ``entry`` record carries the material it was filed with; a ``case_file`` record stands for a
    case whose input registered no comparable material, and carries only that case's own recorded
    reading. There is no ``saved_at`` here, by design.
    """

    item_kind: Literal["entry", "case_file"]
    item_id: str
    case_file_id: str
    entry_kind: str = ""
    material_kind: str = ""
    reported_content: str = ""
    occurred_at: str | None = None
    occurred_precision: str = "unknown"
    occurred_source: str = "unknown"
    recorded_verdict_code: str = ""
    recorded_verdict_text: str = ""
    recorded_signal_type: str = ""
    material: MaterialFacts | None = None


@dataclass(frozen=True)
class CurrentCase:
    """The current case, as recorded by this very analysis. Only these facts are used."""

    direction: RecordedDirection = RecordedDirection.NONE
    is_boundary: bool = False
    boundary_content: str = ""
    verdict_code: str = ""
    occurred_at: str | None = None
    occurred_precision: str = "unknown"
    occurred_source: str = "unknown"


@dataclass
class _Row:
    record: ReviewRecord
    family: ReviewFamily
    direction: RecordedDirection
    explicit_boundary: bool
    window: TemporalWindow
    relation: Relation = Relation.NOT_COMPARABLE
    reason: RelationReason = RelationReason.RECORDED_TOO_THINLY
    superseded_by: str | None = None
    governing: bool = False


def _window(record: ReviewRecord) -> TemporalWindow:
    """The record's declared event time, as a window in its frame. Never read from ``saved_at``."""

    return TemporalWindow.of(record.occurred_at, record.occurred_precision, record.occurred_source)


def _current_window(current: CurrentCase) -> TemporalWindow:
    return TemporalWindow.of(
        current.occurred_at, current.occurred_precision, current.occurred_source
    )


def current_case_facts(
    *,
    materials: list[MaterialFacts],
    signal_type: str,
    verdict_code: str,
    occurred_at: str | None = None,
    occurred_precision: str = "unknown",
    occurred_source: str = "unknown",
) -> CurrentCase:
    """Read the current case's direction from its own recorded output.

    Materials decide when the input registered any; otherwise the recorded signal and verdict do.
    This never runs the engine on anything.
    """

    direction = RecordedDirection.NONE
    is_boundary = False
    content = ""
    for facts in materials:
        classified = classify_material(facts)
        if classified.explicit_boundary and not is_boundary:
            is_boundary = True
            direction = RecordedDirection.BOUNDARY
            content = facts.material_kind
            continue
        if direction is RecordedDirection.NONE and classified.direction in (
            RecordedDirection.POSITIVE,
            RecordedDirection.NEGATIVE,
            RecordedDirection.BOUNDARY,
        ):
            direction = classified.direction
            if classified.direction is RecordedDirection.BOUNDARY:
                is_boundary = True
                content = facts.material_kind
    if direction is RecordedDirection.NONE:
        reading = classify_case_file(signal_type=signal_type, verdict_code=verdict_code)
        if reading.direction is not RecordedDirection.NONE:
            direction = reading.direction
            is_boundary = reading.explicit_boundary
            content = ""
    return CurrentCase(
        direction=direction,
        is_boundary=is_boundary,
        boundary_content=content,
        verdict_code=verdict_code,
        occurred_at=occurred_at,
        occurred_precision=occurred_precision,
        occurred_source=occurred_source,
    )


def build_casebook_review(
    *,
    casebook_id: str,
    casebook_label: str,
    current: CurrentCase,
    records: list[ReviewRecord],
    case_files_read: int,
    entries_read: int,
) -> CasebookReview:
    """Compare a casebook's recorded history with the current case. Returns relations only."""

    rows = [_row_for(record) for record in records]
    governing_row, governing_current, governing_reason, order_known = _find_governing(rows, current)
    governing_window = (
        governing_row.window if governing_row is not None else _current_window(current)
    )
    has_governing = governing_row is not None or governing_current

    historical_boundaries = [row for row in rows if row.explicit_boundary]
    #: Directions a later boundary is allowed to override. A third party's stance and a record
    #: with no reading at all are never "superseded": they were never a current state.
    supersedable = (
        RecordedDirection.POSITIVE,
        RecordedDirection.NEGATIVE,
        RecordedDirection.BOUNDARY,
    )
    # An unknown order names no governing entry: if the boundary cannot be ordered against a
    # record it could govern, calling it the file's state would claim more than the archive proves.
    if has_governing and _governs_an_unordered_record(
        rows, governing_row, governing_window, supersedable
    ):
        governing_row, governing_current = None, False
        has_governing = False
        governing_reason = GoverningReason.ORDER_NOT_DETERMINABLE
    # "Boundary first" is not "boundary forever": if a later record is *provably* later than the
    # boundary, the boundary is no longer the file's last word and is not named governing.
    elif has_governing and _later_record_exists(
        rows, governing_row, governing_window, supersedable
    ):
        governing_row, governing_current = None, False
        has_governing = False
        governing_reason = GoverningReason.LATER_RECORD_AFTER_BOUNDARY
    for row in rows:
        if governing_row is not None and row is governing_row:
            row.relation, row.reason = _relation_by_direction(row, current)
            row.governing = True
            continue
        if (
            has_governing
            and row.direction in supersedable
            and strictly_before(row.window, governing_window)
        ):
            row.relation = Relation.SUPERSEDED
            row.reason = RelationReason.SUPERSEDED_BY_LATER_BOUNDARY
            row.superseded_by = (
                governing_row.record.item_id if governing_row is not None else "current_case"
            )
            continue
        if not row.explicit_boundary and historical_boundaries:
            unclear = any(undecidable(other.window, row.window) for other in historical_boundaries)
            if unclear and row.direction in (
                RecordedDirection.POSITIVE,
                RecordedDirection.NEGATIVE,
            ):
                row.relation = Relation.NOT_COMPARABLE
                row.reason = RelationReason.BOUNDARY_ORDER_NOT_DETERMINABLE
                continue
        row.relation, row.reason = _plain_relation(row, current)

    counts = _counts(rows)
    summary_code = _summary_code(rows, counts, current, governing_row, governing_current)
    return CasebookReview(
        casebook_id=casebook_id,
        casebook_label=casebook_label,
        case_files_read=case_files_read,
        entries_read=entries_read,
        items_compared=len(rows),
        current_direction=current.direction,
        items=[
            ReviewItem(
                item_kind=row.record.item_kind,
                item_id=row.record.item_id,
                case_file_id=row.record.case_file_id,
                entry_kind=row.record.entry_kind,
                material_kind=row.record.material_kind,
                family=row.family,
                recorded_direction=row.direction,
                relation=row.relation,
                relation_reason=row.reason,
                reported_content=row.record.reported_content,
                recorded_verdict_code=row.record.recorded_verdict_code,
                recorded_verdict_text=row.record.recorded_verdict_text,
                recorded_signal_type=row.record.recorded_signal_type,
                occurred_at=row.record.occurred_at,
                occurred_precision=row.record.occurred_precision,
                occurred_source=row.record.occurred_source,
                governing=row.governing,
                superseded_by=row.superseded_by,
            )
            for row in rows
        ],
        counts=counts,
        governing=_governing_payload(governing_row, governing_current, current),
        governing_reason=governing_reason,
        order_known=order_known,
        summary_code=summary_code,
        summary_args=_summary_args(counts, governing_row, governing_current, current),
    )


def _row_for(record: ReviewRecord) -> _Row:
    if record.material is not None:
        classified = classify_material(record.material)
        return _Row(
            record=record,
            family=classified.family,
            direction=classified.direction,
            explicit_boundary=classified.explicit_boundary,
            window=_window(record),
        )
    reading: CaseFileClass = classify_case_file(
        signal_type=record.recorded_signal_type,
        verdict_code=record.recorded_verdict_code,
    )
    return _Row(
        record=record,
        family=reading.family,
        direction=reading.direction,
        explicit_boundary=reading.explicit_boundary,
        window=_window(record),
    )


def _find_governing(
    rows: list[_Row], current: CurrentCase
) -> tuple[_Row | None, bool, GoverningReason, bool]:
    """The latest explicit boundary, or an honest reason for not naming one."""

    candidates: list[tuple[str, _Row | None, TemporalWindow]] = [
        (row.record.item_id, row, row.window) for row in rows if row.explicit_boundary
    ]
    if current.is_boundary:
        candidates.append(("__current__", None, _current_window(current)))
    if not candidates:
        return None, False, GoverningReason.NO_EXPLICIT_BOUNDARY, False
    if len(candidates) == 1:
        item_id, row, window = candidates[0]
        if not window.comparable:
            return None, False, GoverningReason.BOUNDARY_HAS_NO_EVENT_TIME, False
        return row, row is None, GoverningReason.LATEST_EXPLICIT_BOUNDARY, True
    for item_id, row, window in candidates:
        wins = True
        for other_id, _other_row, other_window in candidates:
            if other_id == item_id:
                continue
            if not strictly_before(other_window, window):
                # Nothing that is not *provably* later may be called the latest boundary: equal
                # windows, containing windows and mixed frames all land here.
                wins = False
                break
        if wins:
            return row, row is None, GoverningReason.LATEST_EXPLICIT_BOUNDARY, True
    declared = [window for _id, _row, window in candidates if window.comparable]
    if not declared:
        return None, False, GoverningReason.BOUNDARY_HAS_NO_EVENT_TIME, False
    return None, False, GoverningReason.ORDER_NOT_DETERMINABLE, False


def _governs_an_unordered_record(
    rows: list[_Row],
    governing_row: _Row | None,
    governing_window: TemporalWindow,
    supersedable: tuple[RecordedDirection, ...],
) -> bool:
    """Is there a record this boundary would govern, whose order against it is unknown?

    Only records with a direction of their own count: a third party's stance or a record with no
    reading at all was never the boundary's to govern.
    """

    for row in rows:
        if row is governing_row or row.direction not in supersedable:
            continue
        if undecidable(governing_window, row.window):
            return True
    return False


def _later_record_exists(
    rows: list[_Row],
    governing_row: _Row | None,
    governing_window: TemporalWindow,
    supersedable: tuple[RecordedDirection, ...],
) -> bool:
    """Is there a record that is *provably* later than the boundary it would otherwise govern?"""

    for row in rows:
        if row is governing_row or row.direction not in supersedable:
            continue
        if strictly_before(governing_window, row.window):
            return True
    return False


def _relation_by_direction(row: _Row, current: CurrentCase) -> tuple[Relation, RelationReason]:
    if row.family is ReviewFamily.THIRD_PARTY_ACTIVITY:
        return Relation.UNRELATED, RelationReason.THIRD_PARTY_ACTIVITY
    if row.direction is RecordedDirection.THIRD_PARTY:
        return Relation.NOT_COMPARABLE, RelationReason.THIRD_PARTY_STANCE
    if row.family is ReviewFamily.UNKNOWN or row.direction is RecordedDirection.NONE:
        return Relation.INSUFFICIENT, RelationReason.RECORDED_TOO_THINLY
    if row.family is ReviewFamily.DEFERRAL:
        return Relation.NOT_COMPARABLE, RelationReason.DEFERRAL_DOES_NOT_SETTLE_DIRECTION
    agrees = directions_agree(current.direction, row.direction)
    if agrees is None:
        return Relation.NOT_COMPARABLE, RelationReason.CURRENT_CASE_HAS_NO_DIRECTION
    if agrees:
        return Relation.SUPPORTS, RelationReason.DIRECTION_AGREES
    return Relation.CONFLICTS, RelationReason.DIRECTION_OPPOSES


def _plain_relation(row: _Row, current: CurrentCase) -> tuple[Relation, RelationReason]:
    """Everything except the governing row goes through here; it already encodes the order rules."""

    if row.direction is RecordedDirection.NONE:
        if row.record.item_kind == "case_file":
            return Relation.INSUFFICIENT, RelationReason.NO_RECORDED_READING
        return Relation.INSUFFICIENT, RelationReason.RECORDED_TOO_THINLY
    return _relation_by_direction(row, current)


def _counts(rows: list[_Row]) -> ReviewCounts:
    counts = ReviewCounts()
    for row in rows:
        if row.relation is Relation.SUPPORTS:
            counts.supports += 1
        elif row.relation is Relation.CONFLICTS:
            counts.conflicts += 1
        elif row.relation is Relation.SUPERSEDED:
            counts.superseded += 1
        elif row.relation is Relation.UNRELATED:
            counts.unrelated += 1
        elif row.relation is Relation.NOT_COMPARABLE:
            counts.not_comparable += 1
        else:
            counts.insufficient += 1
    return counts


def _summary_code(
    rows: list[_Row],
    counts: ReviewCounts,
    current: CurrentCase,
    governing_row: _Row | None,
    governing_current: bool,
) -> SummaryCode:
    if not rows:
        return SummaryCode.NO_HISTORY
    comparable = counts.supports + counts.conflicts + counts.superseded
    if comparable == 0:
        if current.direction is RecordedDirection.NONE:
            return SummaryCode.CURRENT_CASE_HAS_NO_DIRECTION
        return SummaryCode.NOTHING_COMPARABLE
    if counts.superseded > 0 and (governing_row is not None or governing_current):
        return SummaryCode.BOUNDARY_GOVERNS
    if counts.supports > 0 and counts.conflicts > 0:
        return SummaryCode.MIXED_DIRECTIONS
    if counts.conflicts > 0:
        return SummaryCode.ONLY_CONFLICTS
    if counts.superseded > 0:
        return SummaryCode.ORDER_UNKNOWN
    return SummaryCode.ONLY_SUPPORTS


def _governing_payload(
    governing_row: _Row | None, governing_current: bool, current: CurrentCase
) -> ReviewGoverning | None:
    if governing_row is not None:
        record = governing_row.record
        return ReviewGoverning(
            item_kind=record.item_kind,
            item_id=record.item_id,
            occurred_at=record.occurred_at,
            occurred_precision=record.occurred_precision,
            reported_content=record.reported_content,
            verdict_code=record.recorded_verdict_code,
        )
    if governing_current:
        return ReviewGoverning(
            item_kind="current_case",
            item_id="current_case",
            occurred_at=current.occurred_at,
            occurred_precision=current.occurred_precision,
            reported_content=current.boundary_content,
            verdict_code=current.verdict_code,
        )
    return None


def _summary_args(
    counts: ReviewCounts,
    governing_row: _Row | None,
    governing_current: bool,
    current: CurrentCase,
) -> dict[str, str]:
    args = {
        "supports": str(counts.supports),
        "conflicts": str(counts.conflicts),
        "superseded": str(counts.superseded),
        "not_comparable": str(counts.not_comparable),
        "unrelated": str(counts.unrelated),
        "insufficient": str(counts.insufficient),
    }
    if governing_row is not None:
        args["governing_date"] = governing_row.record.occurred_at or ""
        args["governing_item"] = governing_row.record.item_id
    elif governing_current:
        args["governing_date"] = current.occurred_at or ""
        args["governing_item"] = "current_case"
    return args


__all__ = [
    "CurrentCase",
    "ReviewRecord",
    "build_casebook_review",
    "current_case_facts",
]
