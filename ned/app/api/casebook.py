"""REST routes for the casebook: create, choose, archive, view, delete.

Three product rules are enforced here rather than trusted to a front end:

* ``POST /api/analyze`` is untouched and still writes nothing. Filing something into the
  casebook is a separate, explicit request.
* the archive request may carry the reader's input, a mode, an action id and the reader's own
  event-time metadata - **and nothing else** (``extra="forbid"``). The verdict, the material
  snapshot and the timestamps are all produced by this process running the engine, so a client
  cannot file "what NED said" as anything but what NED said.
* every read and write is scoped by ``casebook_id``, including the lookups a delete uses, so a
  request addressed at one casebook can never reach another casebook's rows.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ned.app.api.routes import get_analyzer
from ned.app.api.store_access import open_store, open_store_read_only_for_casebook
from ned.app.config import MAX_INPUT_CHARS
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import Mode
from ned.app.core.relative_time import relative_time_cues
from ned.app.review import (
    RecordedCaseFile,
    RecordedEntry,
    RereadResult,
    reread_case_file,
)
from ned.app.store import (
    CasebookConfigError,
    CasebookCorruptError,
    CasebookNotFoundError,
    CasebookRecord,
    CasebookStore,
    CaseFileRecord,
    EntryRecord,
    IdempotencyConflictError,
    OccurredTime,
    SchemaTooNewError,
    casebook_enabled,
    casebook_path,
    rules_fingerprint,
)
from ned.app.store.snapshot import build_case_file_snapshot, occurred_for_archive

router = APIRouter(prefix="/api/casebook", tags=["casebook"])


# --------------------------------------------------------------------------- models ---
class CasebookStatus(BaseModel):
    """Whether this machine has the casebook switched on, and what is on file."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    path: str | None = None
    casebooks: int = 0
    case_files: int = 0
    entries: int = 0
    #: A short, honest explanation when the file exists but this build cannot use it.
    note: str = ""


class RelativeTimeHintRequest(BaseModel):
    """The text to look at. Nothing else: this endpoint knows no dates."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)


class CasebookCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=80)
    subject_note: str = Field(default="", max_length=200)


class CasebookEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=80)
    subject_note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _something_to_change(self) -> CasebookEdit:
        if self.label is None and self.subject_note is None:
            raise ValueError("supply label or subject_note")
        return self


class ArchiveRequest(BaseModel):
    """What a client is allowed to say when filing something.

    There is deliberately no verdict, no material list, no recognition state and no timestamp
    here: those are NED's own record of the analysis it runs for this request.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    mode: Mode = "normal"
    #: The client's name for this user action. Reused on a retry, so a double-click is a no-op.
    action_id: str = Field(min_length=8, max_length=64)
    #: The reader's own event time, validated by the store's own model at request time.
    occurred: OccurredTime = Field(default_factory=OccurredTime)


class CasebookView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    casebook_id: str
    label: str
    subject_note: str = ""
    created_at: str
    archived_at: str | None = None
    case_files: int = 0
    entries: int = 0


class EntryView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str
    entry_kind: str
    material_index: int | None = None
    material_id: str | None = None
    material_kind: str = ""
    reported_content: str = ""
    start_offset: int | None = None
    end_offset: int | None = None
    source_kind: str = ""
    reporter_role: str = ""
    proposition_owner: str = ""
    target: str = ""
    origin_rule_id: str = ""
    subject_label: str | None = None
    occurred_at: str | None = None
    occurred_precision: str
    occurred_source: str
    saved_at: str
    generated_at: str


class CaseFileView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_file_id: str
    input_text: str
    mode: str
    language: str
    recognition: str
    verdict_code: str
    verdict_text: str
    verdict_severity: str
    signal_type: str
    signal_label: str
    engine_name: str
    engine_version: str
    rules_version: str
    rules_fingerprint: str
    generated_at: str
    saved_at: str
    occurred_at: str | None = None
    occurred_precision: str
    occurred_source: str
    entries: list[EntryView] = Field(default_factory=list)


class CasebookDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    casebook: CasebookView
    case_files: list[CaseFileView] = Field(default_factory=list)


class ArchiveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created: bool
    casebook_id: str
    case_file_id: str
    archive_token: str
    entry_count: int
    recognition: str
    verdict_code: str
    #: How the event time was recorded: ``user`` for the reader's own date, ``input_relative``
    #: when the text mentioned time but no date was given, ``unknown`` otherwise.
    occurred_source: str = "unknown"
    occurred_at: str | None = None
    occurred_precision: str = "unknown"
    #: The relative-time wordings the input used. A hint about the text, never a date.
    relative_time_cues: list[str] = Field(default_factory=list)


class RelativeTimeHint(BaseModel):
    """Whether an input mentions a relative time, and which wording it used."""

    model_config = ConfigDict(extra="forbid")

    cues: list[str] = Field(default_factory=list)
    has_relative_time: bool = False
    note_code: str = "no_relative_time"


class DeleteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool
    kind: str
    identifier: str
    detail: str = ""


def _not_found(error: CasebookNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


# ------------------------------------------------------------------------- routes ---
@router.get("/status", response_model=CasebookStatus, summary="Is the casebook available?")
def status() -> CasebookStatus:
    """Always answerable, so a page can be honest about the feature being off.

    A status probe is a *read*: it never creates the database, so asking whether the casebook is
    available cannot bring it into existence. When the switch is off this reports
    ``enabled=false``; when the file exists but this build cannot read it, that is said in
    ``note`` instead of pretending the feature works.
    """

    if not casebook_enabled():
        return CasebookStatus(enabled=False)
    path = casebook_path()
    if not path.exists():
        return CasebookStatus(enabled=True, path=str(path))
    try:
        store = CasebookStore.open_read_only(path)
    except (SchemaTooNewError, CasebookCorruptError, CasebookConfigError) as error:
        return CasebookStatus(enabled=False, path=str(path), note=str(error))
    with store:
        counts = store.stats()
    return CasebookStatus(
        enabled=True,
        path=str(path),
        casebooks=counts["casebooks"],
        case_files=counts["case_files"],
        entries=counts["entries"],
    )


@router.post("", response_model=CasebookView, status_code=201, summary="Create a casebook")
def create_casebook(payload: CasebookCreate) -> CasebookView:
    with open_store() as store:
        record = store.create_casebook(payload.label, payload.subject_note)
        return _casebook_view(store, record)


@router.get("", response_model=list[CasebookView], summary="List casebooks")
def list_casebooks() -> list[CasebookView]:
    with open_store() as store:
        return [_casebook_view(store, record) for record in store.list_casebooks()]


@router.get("/{casebook_id}", response_model=CasebookDetail, summary="One casebook and its cases")
def get_casebook(casebook_id: str) -> CasebookDetail:
    with open_store() as store:
        try:
            record = store.get_casebook(casebook_id)
        except CasebookNotFoundError as error:
            raise _not_found(error) from error
        return CasebookDetail(
            casebook=_casebook_view(store, record),
            case_files=[
                _case_file_view(store, case_file)
                for case_file in store.list_case_files(casebook_id)
            ],
        )


@router.patch("/{casebook_id}", response_model=CasebookView, summary="Rename a casebook")
def edit_casebook(casebook_id: str, payload: CasebookEdit) -> CasebookView:
    with open_store() as store:
        changes = payload.model_dump(exclude_none=True)
        try:
            record = store.update_casebook(casebook_id, **changes)
        except CasebookNotFoundError as error:
            raise _not_found(error) from error
        return _casebook_view(store, record)


@router.post(
    "/relative-time",
    response_model=RelativeTimeHint,
    summary="Does this input mention a relative time? (a hint, not a date)",
)
def relative_time(payload: RelativeTimeHintRequest) -> RelativeTimeHint:
    """Say whether the text uses wording like 昨天, so the interface can offer a date.

    This is a pure function of the text: no clock, no conversion, and nothing is stored. The
    answer only ever feeds the archive hint - it cannot reach the verdict, the evidence or the
    material registration.
    """

    cues = relative_time_cues(payload.text)
    return RelativeTimeHint(
        cues=list(cues),
        has_relative_time=bool(cues),
        note_code="relative_time_cue" if cues else "no_relative_time",
    )


@router.post(
    "/{casebook_id}/archive",
    response_model=ArchiveResult,
    summary="Analyse an input now and file the result",
)
def archive(casebook_id: str, payload: ArchiveRequest, request: Request) -> ArchiveResult:
    """Run NED on the reader's input and file *that* analysis.

    The client sends the input, the mode, an action id and its own event-time metadata. It never
    sends a verdict, a material list or a timestamp: the snapshot is built from the analysis this
    request just produced.
    """

    analyzer: NedAnalyzer = get_analyzer(request)
    result = analyzer.analyze_text(payload.text, mode=payload.mode)
    # The reader's date wins; with none, a relative-time wording is recorded as a hint that the
    # text mentioned time - never converted into a day NED guessed.
    occurred = occurred_for_archive(payload.text, payload.occurred)
    snapshot = build_case_file_snapshot(result, occurred=occurred, book=analyzer.book)
    with open_store() as store:
        try:
            store.get_casebook(casebook_id)
        except CasebookNotFoundError as error:
            raise _not_found(error) from error
        try:
            outcome = store.archive(casebook_id, snapshot, idempotency_key=payload.action_id)
        except IdempotencyConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return ArchiveResult(
            created=outcome.created,
            casebook_id=outcome.casebook_id,
            case_file_id=outcome.case_file_id,
            archive_token=outcome.archive_token,
            entry_count=outcome.entry_count,
            recognition=str(result.recognition),
            verdict_code=result.verdict.code,
            occurred_source=str(occurred.occurred_source),
            occurred_at=occurred.occurred_at,
            occurred_precision=str(occurred.occurred_precision),
            relative_time_cues=list(relative_time_cues(payload.text)),
        )


@router.delete("/{casebook_id}", response_model=DeleteResult, summary="Delete a whole casebook")
def delete_casebook(casebook_id: str) -> DeleteResult:
    with open_store() as store:
        outcome = store.delete_casebook(casebook_id)
        return DeleteResult(
            deleted=outcome.deleted,
            kind=outcome.kind,
            identifier=outcome.identifier,
            detail=outcome.detail,
        )


@router.delete(
    "/{casebook_id}/files/{case_file_id}",
    response_model=DeleteResult,
    summary="Delete one case file and its entries",
)
def delete_case_file(casebook_id: str, case_file_id: str) -> DeleteResult:
    with open_store() as store:
        try:
            store.find_case_file(casebook_id, case_file_id)
        except CasebookNotFoundError as error:
            raise _not_found(error) from error
        outcome = store.delete_case_file(case_file_id)
        return DeleteResult(
            deleted=outcome.deleted,
            kind=outcome.kind,
            identifier=outcome.identifier,
            detail=outcome.detail,
        )


@router.post(
    "/{casebook_id}/files/{case_file_id}/reread",
    response_model=RereadResult,
    summary="Re-read one archived case with today's rules (read-only)",
)
def reread(casebook_id: str, case_file_id: str, request: Request) -> RereadResult:
    """Re-run today's engine on the *stored* input of one archived case file.

    Three rules are structural rather than promises:

    * the request carries no text. The server reads the archived ``input_text`` itself, so a
      client cannot pass today's words off as history;
    * the store is opened **read-only**, so even a bug in this function cannot write;
    * nothing is stored. The reread is ephemeral: it is computed, returned, and forgotten.
    """

    analyzer: NedAnalyzer = get_analyzer(request)
    with open_store_read_only_for_casebook(casebook_id) as store:
        try:
            casebook = store.get_casebook(casebook_id)
            case_file = store.find_case_file(casebook_id, case_file_id)
        except CasebookNotFoundError as error:
            raise _not_found(error) from error
        entries = tuple(
            RecordedEntry(
                entry_id=entry.entry_id,
                entry_kind=entry.entry_kind,
                material_index=entry.material_index,
                material_kind=entry.material_kind,
                reported_content=entry.reported_content,
                start_offset=int(entry.start_offset if entry.start_offset is not None else -1),
                end_offset=int(entry.end_offset if entry.end_offset is not None else -1),
                polarity=entry.polarity,
                epistemic_status=entry.epistemic_status,
                proposition_owner=entry.proposition_owner,
                reporter_role=entry.reporter_role,
                target=entry.target,
                origin_rule_id=entry.origin_rule_id,
            )
            for entry in store.list_entries(case_file_id=case_file_id)
        )
        label = casebook.label
        recorded = RecordedCaseFile(
            case_file_id=case_file.case_file_id,
            input_text=case_file.input_text,
            generated_at=case_file.generated_at,
            engine_name=case_file.engine_name,
            engine_version=case_file.engine_version,
            rules_version=case_file.rules_version,
            rules_fingerprint=case_file.rules_fingerprint,
            recognition=case_file.recognition,
            verdict_code=case_file.verdict_code,
            verdict_text=case_file.verdict_text,
            signal_type=case_file.signal_type,
        )
    return reread_case_file(
        casebook_id=casebook_id,
        casebook_label=label,
        case_file=recorded,
        entries=entries,
        engine=analyzer,
        rules_version=str(getattr(analyzer.book, "version", "") or ""),
        rules_fingerprint=rules_fingerprint(getattr(analyzer.book, "source_dir", None)),
    )


@router.delete(
    "/{casebook_id}/entries/{entry_id}",
    response_model=DeleteResult,
    summary="Delete one entry",
)
def delete_entry(casebook_id: str, entry_id: str) -> DeleteResult:
    with open_store() as store:
        try:
            store.find_entry(casebook_id, entry_id)
        except CasebookNotFoundError as error:
            raise _not_found(error) from error
        outcome = store.delete_entry(entry_id)
        return DeleteResult(
            deleted=outcome.deleted,
            kind=outcome.kind,
            identifier=outcome.identifier,
            detail=outcome.detail,
        )


# ------------------------------------------------------------------------ helpers ---
def _casebook_view(store: CasebookStore, record: CasebookRecord) -> CasebookView:
    case_files = store.list_case_files(record.casebook_id)
    return CasebookView(
        casebook_id=record.casebook_id,
        label=record.label,
        subject_note=record.subject_note,
        created_at=record.created_at,
        archived_at=record.archived_at,
        case_files=len(case_files),
        entries=len(store.list_entries(casebook_id=record.casebook_id)),
    )


def _case_file_view(store: CasebookStore, record: CaseFileRecord) -> CaseFileView:
    entries = store.list_entries(case_file_id=record.case_file_id)
    return CaseFileView(
        case_file_id=record.case_file_id,
        input_text=record.input_text,
        mode=record.mode,
        language=record.language,
        recognition=record.recognition,
        verdict_code=record.verdict_code,
        verdict_text=record.verdict_text,
        verdict_severity=record.verdict_severity,
        signal_type=record.signal_type,
        signal_label=record.signal_label,
        engine_name=record.engine_name,
        engine_version=record.engine_version,
        rules_version=record.rules_version,
        rules_fingerprint=record.rules_fingerprint,
        generated_at=record.generated_at,
        saved_at=record.saved_at,
        occurred_at=record.occurred_at,
        occurred_precision=record.occurred_precision,
        occurred_source=record.occurred_source,
        entries=[_entry_view(entry) for entry in entries],
    )


def _entry_view(record: EntryRecord) -> EntryView:
    return EntryView(
        entry_id=record.entry_id,
        entry_kind=record.entry_kind,
        material_index=record.material_index,
        material_id=record.material_id,
        material_kind=record.material_kind,
        reported_content=record.reported_content,
        start_offset=record.start_offset,
        end_offset=record.end_offset,
        source_kind=record.source_kind,
        reporter_role=record.reporter_role,
        proposition_owner=record.proposition_owner,
        target=record.target,
        origin_rule_id=record.origin_rule_id,
        subject_label=record.subject_label,
        occurred_at=record.occurred_at,
        occurred_precision=record.occurred_precision,
        occurred_source=record.occurred_source,
        saved_at=record.saved_at,
        generated_at=record.generated_at,
    )


__all__ = ["router"]
