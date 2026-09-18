"""The casebook's data contracts: what gets archived, and what comes back.

Nothing here touches SQLite. The semantic core must never import this module's storage half, and
this half must never reach into the engine: these are plain frozen records that a caller builds
from an ``AnalysisResult`` and that the repository stores verbatim.

The three time fields follow the PR-6M0 ruling exactly, because they decide whether a later
review may say "this happened after that":

``occurred_at`` + ``occurred_precision`` + ``occurred_source``
    The **event** time. Only ever as precise as it is actually known, and never padded: a date
    known to the day is stored as ``2026-03-01`` and never as ``2026-03-01T00:00:00Z``, which
    would invent a midnight. ``occurred_source`` says where it came from - ``user`` (a real,
    normalisable time the reader supplied), ``input_relative`` (the text said 昨天/去年 but this
    release does not resolve relative time), or ``unknown``.

``saved_at``
    When the row was **written**. It is provenance, never an event time, and it is never copied
    into ``occurred_at``.

``generated_at``
    The engine's own timestamp from the analysed payload, stored per row verbatim.

Time zones: a time-of-day is normalised to UTC only when the zone is actually known, and then it
carries a ``Z``. When the zone is not known the value keeps its bare local form (``2026-03-01T14``)
and that absence **is** the record that the zone is unknown. Offsets such as ``+08:00`` are
refused at the boundary: a caller holding a known zone must convert to UTC first, and a caller
that does not know the zone must not pretend to.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ned.app.core.models import (
    EpistemicStatus,
    Language,
    Mode,
    Polarity,
    RecognitionState,
    Severity,
    SignalType,
    SourceKind,
)
from ned.app.store.paths import SCHEMA_VERSION

#: Granularity actually known, finest last. ``unknown`` means no event time is known at all.
OccurredPrecision = Literal["year", "month", "day", "hour", "minute", "second", "unknown"]

#: Where the event time came from. There is deliberately no ``saved``: ``saved_at`` is not an
#: event time and must never be promoted into one.
OccurredSource = Literal["user", "input_relative", "unknown"]

EntryKind = Literal["material", "event", "user_note"]

_YEAR = re.compile(r"^\d{4}$")
_MONTH = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")
_DAY = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$")
_HOUR = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3])Z?$")
_MINUTE = re.compile(
    r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\dZ?$"
)
_SECOND = re.compile(
    r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"
    r"T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\dZ?$"
)

#: The one accepted shape for each precision. Padding a coarser value into a finer shape is a
#: validation failure, not a normalisation.
_SHAPES: dict[str, re.Pattern[str]] = {
    "year": _YEAR,
    "month": _MONTH,
    "day": _DAY,
    "hour": _HOUR,
    "minute": _MINUTE,
    "second": _SECOND,
}

_TIME_BEARING = frozenset({"hour", "minute", "second"})


class OccurredTime(BaseModel):
    """An event time as precisely as it is known, and no more precisely than that."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    occurred_at: str | None = None
    occurred_precision: OccurredPrecision = "unknown"
    occurred_source: OccurredSource = "unknown"

    @model_validator(mode="after")
    def _matches_the_ruling(self) -> OccurredTime:
        at, precision, source = self.occurred_at, self.occurred_precision, self.occurred_source
        if source == "user":
            if at is None:
                raise ValueError("occurred_source='user' requires an event time")
            if precision == "unknown":
                raise ValueError("occurred_source='user' requires a known precision")
            shape = _SHAPES[precision]
            if not shape.match(at):
                raise ValueError(
                    f"occurred_at {at!r} is not the shape of precision "
                    f"{precision!r}; a coarser time is "
                    "never padded into a finer one"
                )
            if "+" in at:
                raise ValueError(
                    "offsets are refused: convert a known-zone time to UTC and use a trailing Z"
                )
            if len(at) >= 10:
                try:
                    date.fromisoformat(at[:10])
                except ValueError as error:
                    raise ValueError(f"occurred_at {at!r} is not a real date") from error
            return self
        if at is not None:
            raise ValueError(
                f"occurred_source={source!r} means no event time is recorded; got {at!r}"
            )
        if precision != "unknown":
            raise ValueError(
                f"occurred_source={source!r} means the precision is unknown; got {precision!r}"
            )
        return self

    @property
    def time_zone_known(self) -> bool | None:
        """Whether the stored time carries a known zone.

        ``None`` for a date-only value, where a zone is not applicable. ``False`` records that
        the wall-clock time is known but the zone is not - a fact this release must preserve
        rather than paper over with a guessed UTC.
        """

        if self.occurred_at is None or self.occurred_precision not in _TIME_BEARING:
            return None
        return self.occurred_at.endswith("Z")

    @property
    def is_unknown(self) -> bool:
        return self.occurred_at is None


class MaterialSnapshot(BaseModel):
    """One material as it was reported, verbatim enough to be re-read later.

    The fields mirror ``ned.app.core.models.ObservedMaterial``; ``material_index`` remembers
    where it sat in that result, and ``reported_content`` plus the offsets keep the quote
    verifiable against the archived input text.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    material_index: int = Field(ge=0)
    entry_kind: EntryKind = "material"
    material_id: str | None = None
    material_kind: str = ""
    reported_content: str = ""
    start_offset: int = -1
    end_offset: int = -1
    source_kind: SourceKind = "direct_user_statement"
    reporter_role: str = ""
    proposition_owner: str = ""
    target: str = ""
    polarity: Polarity = "neutral"
    epistemic_status: EpistemicStatus = "reported"
    origin_rule_id: str = ""
    subject_label: str | None = None
    note: str = ""
    #: ``None`` means "inherit the case file's event time when this is archived".
    occurred: OccurredTime | None = None


class CaseFileSnapshot(BaseModel):
    """One analysis, archived: the input, the snapshot of what NED said, and its provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_text: str = Field(min_length=1)
    title: str = ""
    mode: Mode = "normal"
    language: Language = "unknown"
    recognition: RecognitionState
    verdict_code: str
    verdict_text: str
    verdict_severity: Severity
    signal_type: SignalType = SignalType.NONE
    signal_label: str = ""
    engine_name: str
    engine_version: str
    rules_version: str
    #: Empty means "fingerprint the rule pack in force when this is archived".
    rules_fingerprint: str = ""
    generated_at: datetime
    occurred: OccurredTime = OccurredTime()
    user_note: str = ""
    materials: tuple[MaterialSnapshot, ...] = ()

    @model_validator(mode="after")
    def _stamps_are_utc(self) -> CaseFileSnapshot:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must carry a time zone")
        return self

    @property
    def generated_at_utc(self) -> str:
        return self.generated_at.astimezone(UTC).isoformat()


class CasebookRecord(BaseModel):
    """A casebook row. Its display name may change; nothing else about it may."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    casebook_id: str
    label: str
    subject_note: str = ""
    created_at: str
    archived_at: str | None = None
    schema_version: int = SCHEMA_VERSION


class CaseFileRecord(BaseModel):
    """An archived case file, exactly as stored."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_file_id: str
    casebook_id: str
    archive_token: str
    input_text: str
    input_sha256: str
    title: str
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
    occurred_at: str | None
    occurred_precision: str
    occurred_source: str
    user_note: str
    schema_version: int


class EntryRecord(BaseModel):
    """An archived entry, exactly as stored - including its own materialised time snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_id: str
    case_file_id: str
    casebook_id: str
    entry_kind: str
    material_index: int | None
    material_id: str | None
    material_kind: str
    reported_content: str
    start_offset: int | None
    end_offset: int | None
    source_kind: str
    reporter_role: str
    proposition_owner: str
    target: str
    polarity: str
    epistemic_status: str
    origin_rule_id: str
    subject_label: str | None
    note: str
    generated_at: str
    saved_at: str
    occurred_at: str | None
    occurred_precision: str
    occurred_source: str
    schema_version: int


class ArchiveOutcome(BaseModel):
    """What one archive call did. ``created=False`` is the idempotent replay, not a failure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    created: bool
    case_file_id: str
    casebook_id: str
    archive_token: str
    entry_count: int


class DeleteOutcome(BaseModel):
    """What one delete call removed, so a caller can tell the user honestly."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    deleted: bool
    kind: Literal["entry", "case_file", "casebook"]
    identifier: str
    detail: str = ""


__all__ = [
    "ArchiveOutcome",
    "CaseFileRecord",
    "CaseFileSnapshot",
    "CasebookRecord",
    "DeleteOutcome",
    "EntryKind",
    "EntryRecord",
    "MaterialSnapshot",
    "OccurredPrecision",
    "OccurredSource",
    "OccurredTime",
]
