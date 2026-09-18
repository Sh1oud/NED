"""PR-6M3: the explicit, opt-in casebook review on the analyse path.

Three rules live here, and all three are the point of the batch:

* **explicit**: nothing happens unless the request carries a ``casebook`` selection. The default
  analysis does not read a database, does not open one, and its payload does not gain a key;
* **parallel**: when a review is produced it is attached to the response as ``casebook_review``.
  The current case's verdict, evidence, materials, breakdown, recognition and reaching are the
  engine's own output, untouched - the review is built from a *copy* of the recorded fields and
  handed back beside the report;
* **narrow**: the review reads the casebook's recorded entries and each case file's recorded
  reading. It never re-runs the engine on an old input (that is M4's reread), and it never turns a
  count into a score.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ned.app.core.models import AnalysisResult, AnalyzeRequest
from ned.app.review import (
    CasebookReview,
    MaterialFacts,
    ReviewRecord,
    build_casebook_review,
    current_case_facts,
)
from ned.app.store import CasebookStore, OccurredTime
from ned.app.store.models import CaseFileRecord, EntryRecord


class CasebookSelection(BaseModel):
    """The reader's explicit request to review against one casebook.

    ``occurred`` is the reader's own event time for *this* input. It is optional, and it is the
    only thing that can ever let the review order the current case against the file: without it
    the current case has no event time at all, and nothing is assumed.
    """

    model_config = ConfigDict(extra="forbid")

    casebook_id: str = Field(min_length=1, max_length=64)
    occurred: OccurredTime | None = None


class AnalyzeRequestWithCasebook(AnalyzeRequest):
    """``/api/analyze``'s request, plus one optional field. Old clients are unaffected."""

    model_config = ConfigDict(extra="forbid")

    casebook: CasebookSelection | None = None


class AnalyzeResponse(AnalysisResult):
    """``/api/analyze``'s response, plus the review - and only when one was asked for.

    ``exclude_if`` keeps the key out of the JSON entirely when no review was requested, so the
    default payload stays byte-identical rather than gaining a ``"casebook_review": null``.
    """

    model_config = ConfigDict(extra="forbid")

    casebook_review: CasebookReview | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


def material_facts_of(result: AnalysisResult) -> list[MaterialFacts]:
    """The current case's recorded materials, reduced to the five facts a review may read."""

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


def review_records(store: CasebookStore, casebook_id: str) -> tuple[list[ReviewRecord], int, int]:
    """Read one casebook's history as review records: entries, plus material-less case files.

    A case file whose input registered no comparable material is still a recorded reading of that
    input (its signal and its verdict), so it takes part as one ``case_file`` record. A case file
    that did register materials takes part through those materials, and not twice.

    The order is the archive's own order, for display only. It is never used as evidence about
    when anything happened: :class:`ReviewRecord` does not even carry ``saved_at``.
    """

    case_files = store.list_case_files(casebook_id)
    records: list[ReviewRecord] = []
    entries_read = 0
    for case_file in case_files:
        entries = store.list_entries(case_file_id=case_file.case_file_id)
        if not entries:
            records.append(_case_file_record(case_file))
            continue
        entries_read += len(entries)
        records.extend(_entry_record(case_file, entry) for entry in entries)
    return records, len(case_files), entries_read


def build_review(
    store: CasebookStore,
    *,
    casebook_id: str,
    result: AnalysisResult,
    occurred: OccurredTime | None = None,
) -> CasebookReview:
    """Build the review for one analysis against one casebook. Read-only, and cheap to test."""

    casebook = store.get_casebook(casebook_id)
    records, case_files_read, entries_read = review_records(store, casebook_id)
    current = current_case_facts(
        materials=material_facts_of(result),
        signal_type=str(result.signal_type),
        verdict_code=result.verdict.code,
        occurred_at=occurred.occurred_at if occurred is not None else None,
        occurred_precision=str(occurred.occurred_precision) if occurred is not None else "unknown",
        occurred_source=str(occurred.occurred_source) if occurred is not None else "unknown",
    )
    return build_casebook_review(
        casebook_id=casebook_id,
        casebook_label=casebook.label,
        current=current,
        records=records,
        case_files_read=case_files_read,
        entries_read=entries_read,
    )


def _entry_record(case_file: CaseFileRecord, entry: EntryRecord) -> ReviewRecord:
    return ReviewRecord(
        item_kind="entry",
        item_id=entry.entry_id,
        case_file_id=case_file.case_file_id,
        entry_kind=entry.entry_kind,
        material_kind=entry.material_kind,
        reported_content=entry.reported_content,
        occurred_at=entry.occurred_at,
        occurred_precision=entry.occurred_precision,
        occurred_source=entry.occurred_source,
        recorded_verdict_code=case_file.verdict_code,
        recorded_verdict_text=case_file.verdict_text,
        recorded_signal_type=case_file.signal_type,
        material=MaterialFacts(
            material_kind=entry.material_kind,
            origin_rule_id=entry.origin_rule_id,
            polarity=entry.polarity,
            proposition_owner=entry.proposition_owner,
            target=entry.target,
        ),
    )


def _case_file_record(case_file: CaseFileRecord) -> ReviewRecord:
    return ReviewRecord(
        item_kind="case_file",
        item_id=case_file.case_file_id,
        case_file_id=case_file.case_file_id,
        reported_content=case_file.input_text,
        occurred_at=case_file.occurred_at,
        occurred_precision=case_file.occurred_precision,
        occurred_source=case_file.occurred_source,
        recorded_verdict_code=case_file.verdict_code,
        recorded_verdict_text=case_file.verdict_text,
        recorded_signal_type=case_file.signal_type,
    )


__all__ = [
    "AnalyzeRequestWithCasebook",
    "AnalyzeResponse",
    "CasebookSelection",
    "build_review",
    "material_facts_of",
    "review_records",
]
