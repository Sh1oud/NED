"""PR-6M4C: reread one archived case with today's rules, side by side with what was recorded.

Read-only by construction:

* the unit is the **whole stored ``input_text`` of a case file** - one analysis call. Entry slices
  are never re-run on their own (they lose their clause context, their offsets and the case-level
  reading), and ``material_id`` is never used as an identity across rule versions (its seed
  contains the rule id, so it changes when a rule is renamed);
* the module computes and returns: it cannot write, it opens nothing, and the API opens the
  casebook **read-only** for this path so the store itself refuses any attempted write;
* nothing here touches the current case's verdict, evidence, materials, breakdown, recognition or
  capacity. A reread is a fact about an *archived* case file.

Alignment, and why it is by hand and not by id
---------------------------------------------
A recorded entry and a reread material are the same thing when the kind matches **and** their
spans overlap by at least half of the shorter span. One candidate is an alignment; two or more is
``ambiguous`` and is reported as such, never guessed; none is ``missing``; a reread material that
no recorded entry claims is ``new``.

A difference is called ``changed`` only when a *structural* field moved (polarity, epistemic
status, ownership, the quoted span). A rule-id-only difference is reported separately
(``rule_id_changed``), because renaming a rule inside the pack is not the same as the archive
having been wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

#: The fields an aligned pair must agree on to be called ``same``. ``origin_rule_id`` is compared
#: too, but a difference in it alone is reported as a rename rather than as a change.
STRUCTURAL_FIELDS: tuple[str, ...] = (
    "polarity",
    "epistemic_status",
    "proposition_owner",
    "reporter_role",
    "target",
    "reported_content",
)

#: How much of the shorter span two spans must share to be the same span.
OVERLAP_THRESHOLD = 0.5


class Difference(StrEnum):
    """The five classes a recorded case can be read into."""

    SAME = "same"
    CHANGED = "changed"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    NEW = "new"


@dataclass(frozen=True)
class RecordedEntry:
    """One archived entry, exactly as the store holds it."""

    entry_id: str
    entry_kind: str
    material_index: int | None
    material_kind: str
    reported_content: str
    start_offset: int
    end_offset: int
    polarity: str
    epistemic_status: str
    proposition_owner: str
    reporter_role: str
    target: str
    origin_rule_id: str


@dataclass(frozen=True)
class RecordedCaseFile:
    """The archived case file: its input, and the reading NED signed off at the time."""

    case_file_id: str
    input_text: str
    generated_at: str
    engine_name: str
    engine_version: str
    rules_version: str
    rules_fingerprint: str
    recognition: str
    verdict_code: str
    verdict_text: str
    signal_type: str


class Analyzer(Protocol):
    """The one thing this module needs: something that can analyse a stored input."""

    def analyze_text(self, text: str) -> Any: ...


class RecordedEntryView(BaseModel):
    """The archived side of one entry, as shown to the reader."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str
    entry_kind: str = ""
    material_index: int | None = None
    material_kind: str = ""
    reported_content: str = ""
    start_offset: int = -1
    end_offset: int = -1
    polarity: str = ""
    epistemic_status: str = ""
    proposition_owner: str = ""
    reporter_role: str = ""
    target: str = ""
    origin_rule_id: str = ""


class RereadMaterialView(BaseModel):
    """Today's side of one material, as shown to the reader."""

    model_config = ConfigDict(extra="forbid")

    material_kind: str = ""
    reported_content: str = ""
    start: int = -1
    end: int = -1
    polarity: str = ""
    epistemic_status: str = ""
    proposition_owner: str = ""
    reporter_role: str = ""
    target: str = ""
    origin_rule_id: str = ""


class RecordedCaseView(BaseModel):
    """What the archive says about this case file."""

    model_config = ConfigDict(extra="forbid")

    engine: str = ""
    engine_version: str = ""
    rules_version: str = ""
    rules_fingerprint: str = ""
    generated_at: str = ""
    recognition: str = ""
    verdict_code: str = ""
    verdict_text: str = ""
    signal_type: str = ""
    entries: list[RecordedEntryView] = Field(default_factory=list)


class RereadCaseView(BaseModel):
    """What today's engine says about the same stored input."""

    model_config = ConfigDict(extra="forbid")

    engine: str = ""
    engine_version: str = ""
    rules_version: str = ""
    rules_fingerprint: str = ""
    recognition: str = ""
    verdict_code: str = ""
    verdict_text: str = ""
    signal_type: str = ""
    language: str = ""
    materials: list[RereadMaterialView] = Field(default_factory=list)


class AlignmentRow(BaseModel):
    """One line of the comparison: a recorded entry, its reread partner, and the verdict."""

    model_config = ConfigDict(extra="forbid")

    difference: Difference
    entry_id: str | None = None
    material_index: int | None = None
    recorded_kind: str = ""
    reread_kind: str = ""
    recorded_slice: str = ""
    reread_slice: str = ""
    recorded_rule_id: str = ""
    reread_rule_id: str = ""
    changed_fields: list[str] = Field(default_factory=list)
    rule_id_changed: bool = False
    candidate_count: int = 0
    recorded_span: tuple[int, int] | None = None
    reread_span: tuple[int, int] | None = None


class RereadCounts(BaseModel):
    """How many lines of each class. Counts, never a score."""

    model_config = ConfigDict(extra="forbid")

    same: int = 0
    changed: int = 0
    missing: int = 0
    ambiguous: int = 0
    new: int = 0
    #: A refinement, not a sixth class: rows that differ *only* by an internal rule id.
    rule_id_only: int = 0


class RereadResult(BaseModel):
    """The whole answer: what was recorded, what is read today, and how they line up."""

    model_config = ConfigDict(extra="forbid")

    casebook_id: str
    casebook_label: str
    case_file_id: str
    input_text: str
    as_recorded: RecordedCaseView = Field(default_factory=RecordedCaseView)
    as_reread: RereadCaseView = Field(default_factory=RereadCaseView)
    alignment: list[AlignmentRow] = Field(default_factory=list)
    counts: RereadCounts = Field(default_factory=RereadCounts)
    #: Case-level fields that moved (recognition / verdict_code / verdict_text / signal_type).
    case_level_changed: list[str] = Field(default_factory=list)
    rules_differ_from_archive: bool = False
    #: True when nothing at all moved: same rule pack, same reading, same material set.
    identical: bool = False
    note_code: str = "reread_of_recorded"


@dataclass(frozen=True)
class _Material:
    """Internal: what the engine handed back, before it becomes a view."""

    material_kind: str
    reported_content: str
    start: int
    end: int
    polarity: str
    epistemic_status: str
    proposition_owner: str
    reporter_role: str
    target: str
    origin_rule_id: str


@dataclass(frozen=True)
class _Reading:
    recognition: str
    verdict_code: str
    verdict_text: str
    signal_type: str
    language: str
    engine_version: str
    materials: tuple[_Material, ...] = field(default_factory=tuple)


def _overlap_ratio(recorded: tuple[int, int], reread: tuple[int, int]) -> float:
    """How much of the shorter span the two share. ``0.0`` when they do not touch."""

    start = max(recorded[0], reread[0])
    end = min(recorded[1], reread[1])
    shared = max(0, end - start)
    shorter = min(recorded[1] - recorded[0], reread[1] - reread[0])
    if shorter <= 0:
        # A zero-length span is the same span only at the same position.
        return 1.0 if recorded[0] == reread[0] else 0.0
    return shared / shorter


def candidates_for(entry: RecordedEntry, materials: tuple[_Material, ...]) -> list[_Material]:
    """Every reread material that could be the same thing as ``entry``: kind and span."""

    return [
        material
        for material in materials
        if material.material_kind == entry.material_kind
        and _overlap_ratio((entry.start_offset, entry.end_offset), (material.start, material.end))
        >= OVERLAP_THRESHOLD
    ]


def _structural_changes(entry: RecordedEntry, material: _Material) -> list[str]:
    """Which compared fields really moved."""

    return [
        name
        for name in STRUCTURAL_FIELDS
        if str(getattr(entry, name)) != str(getattr(material, name))
    ]


def align(
    entries: tuple[RecordedEntry, ...], materials: tuple[_Material, ...]
) -> list[AlignmentRow]:
    """Line the archive up with today's reading. Never guesses, never joins on ``material_id``."""

    rows: list[AlignmentRow] = []
    claimed: set[int] = set()
    # A material may be the only candidate for more than one recorded entry. It cannot be both, so
    # those rows are ambiguous rather than aligned.
    matches = [(entry, candidates_for(entry, materials)) for entry in entries]
    single_claims: dict[int, int] = {}
    for _entry, found in matches:
        if len(found) == 1:
            index = materials.index(found[0])
            single_claims[index] = single_claims.get(index, 0) + 1
    for entry, found in matches:
        if not found:
            rows.append(
                AlignmentRow(
                    difference=Difference.MISSING,
                    entry_id=entry.entry_id,
                    material_index=entry.material_index,
                    recorded_kind=entry.material_kind,
                    recorded_slice=entry.reported_content,
                    recorded_rule_id=entry.origin_rule_id,
                    recorded_span=(entry.start_offset, entry.end_offset),
                )
            )
            continue
        indices = [materials.index(item) for item in found]
        shared = len(found) > 1 or any(single_claims.get(index, 0) > 1 for index in indices)
        if shared:
            # Every candidate counts as claimed: it is part of an answer that could not be given,
            # not a material today invented.
            claimed.update(indices)
            rows.append(
                AlignmentRow(
                    difference=Difference.AMBIGUOUS,
                    entry_id=entry.entry_id,
                    material_index=entry.material_index,
                    recorded_kind=entry.material_kind,
                    recorded_slice=entry.reported_content,
                    recorded_rule_id=entry.origin_rule_id,
                    candidate_count=len(found),
                    reread_kind=", ".join(sorted({item.material_kind for item in found})),
                    reread_slice=" | ".join(item.reported_content for item in found),
                    recorded_span=(entry.start_offset, entry.end_offset),
                )
            )
            continue
        material = found[0]
        claimed.add(materials.index(material))
        changes = _structural_changes(entry, material)
        rows.append(
            AlignmentRow(
                difference=Difference.CHANGED if changes else Difference.SAME,
                entry_id=entry.entry_id,
                material_index=entry.material_index,
                recorded_kind=entry.material_kind,
                reread_kind=material.material_kind,
                recorded_slice=entry.reported_content,
                reread_slice=material.reported_content,
                recorded_rule_id=entry.origin_rule_id,
                reread_rule_id=material.origin_rule_id,
                changed_fields=changes,
                rule_id_changed=entry.origin_rule_id != material.origin_rule_id,
                candidate_count=1,
                recorded_span=(entry.start_offset, entry.end_offset),
                reread_span=(material.start, material.end),
            )
        )
    for index, material in enumerate(materials):
        if index in claimed:
            continue
        rows.append(
            AlignmentRow(
                difference=Difference.NEW,
                reread_kind=material.material_kind,
                reread_slice=material.reported_content,
                reread_rule_id=material.origin_rule_id,
                reread_span=(material.start, material.end),
            )
        )
    return rows


def _read(engine: Analyzer, text: str) -> _Reading:
    result = engine.analyze_text(text)
    return _Reading(
        recognition=str(result.recognition),
        verdict_code=result.verdict.code,
        verdict_text=result.verdict.text,
        signal_type=str(result.signal_type),
        language=str(result.language),
        engine_version=str(getattr(getattr(result, "engine", None), "version", "") or ""),
        materials=tuple(
            _Material(
                material_kind=str(material.material_kind),
                reported_content=material.reported_content,
                start=int(material.start),
                end=int(material.end),
                polarity=str(material.polarity),
                epistemic_status=str(material.epistemic_status),
                proposition_owner=material.proposition_owner,
                reporter_role=material.reporter_role,
                target=material.target,
                origin_rule_id=material.origin_rule_id,
            )
            for material in result.materials
        ),
    )


def reread_case_file(
    *,
    casebook_id: str,
    casebook_label: str,
    case_file: RecordedCaseFile,
    entries: tuple[RecordedEntry, ...],
    engine: Analyzer,
    rules_version: str = "",
    rules_fingerprint: str = "",
) -> RereadResult:
    """Re-run today's engine on the archived input and line the result up with the archive.

    ``engine`` is passed in rather than imported: the review package must not depend on the
    analysis facade, and this keeps the reread testable against a fixture rule pack. The rule
    provenance comes from the caller for the same reason.
    """

    reading = _read(engine, case_file.input_text)
    alignment = align(entries, reading.materials)
    counts = RereadCounts()
    for row in alignment:
        if row.difference is Difference.SAME:
            counts.same += 1
        elif row.difference is Difference.CHANGED:
            counts.changed += 1
        elif row.difference is Difference.MISSING:
            counts.missing += 1
        elif row.difference is Difference.AMBIGUOUS:
            counts.ambiguous += 1
        else:
            counts.new += 1
        if row.rule_id_changed and not row.changed_fields:
            counts.rule_id_only += 1

    case_level = [
        name
        for name, recorded, reread in (
            ("recognition", case_file.recognition, reading.recognition),
            ("verdict_code", case_file.verdict_code, reading.verdict_code),
            ("verdict_text", case_file.verdict_text, reading.verdict_text),
            ("signal_type", case_file.signal_type, reading.signal_type),
        )
        if recorded != reread
    ]
    rules_differ = bool(
        rules_fingerprint
        and case_file.rules_fingerprint
        and rules_fingerprint != case_file.rules_fingerprint
    )
    identical = (
        not case_level
        and counts.changed == 0
        and counts.missing == 0
        and counts.ambiguous == 0
        and counts.new == 0
        and counts.rule_id_only == 0
    )
    return RereadResult(
        casebook_id=casebook_id,
        casebook_label=casebook_label,
        case_file_id=case_file.case_file_id,
        input_text=case_file.input_text,
        as_recorded=RecordedCaseView(
            engine=case_file.engine_name,
            engine_version=case_file.engine_version,
            rules_version=case_file.rules_version,
            rules_fingerprint=case_file.rules_fingerprint,
            generated_at=case_file.generated_at,
            recognition=case_file.recognition,
            verdict_code=case_file.verdict_code,
            verdict_text=case_file.verdict_text,
            signal_type=case_file.signal_type,
            entries=[
                RecordedEntryView(
                    entry_id=entry.entry_id,
                    entry_kind=entry.entry_kind,
                    material_index=entry.material_index,
                    material_kind=entry.material_kind,
                    reported_content=entry.reported_content,
                    start_offset=entry.start_offset,
                    end_offset=entry.end_offset,
                    polarity=entry.polarity,
                    epistemic_status=entry.epistemic_status,
                    proposition_owner=entry.proposition_owner,
                    reporter_role=entry.reporter_role,
                    target=entry.target,
                    origin_rule_id=entry.origin_rule_id,
                )
                for entry in entries
            ],
        ),
        as_reread=RereadCaseView(
            engine="ned-local-rules",
            engine_version=reading.engine_version,
            rules_version=rules_version,
            rules_fingerprint=rules_fingerprint,
            recognition=reading.recognition,
            verdict_code=reading.verdict_code,
            verdict_text=reading.verdict_text,
            signal_type=reading.signal_type,
            language=reading.language,
            materials=[
                RereadMaterialView(
                    material_kind=material.material_kind,
                    reported_content=material.reported_content,
                    start=material.start,
                    end=material.end,
                    polarity=material.polarity,
                    epistemic_status=material.epistemic_status,
                    proposition_owner=material.proposition_owner,
                    reporter_role=material.reporter_role,
                    target=material.target,
                    origin_rule_id=material.origin_rule_id,
                )
                for material in reading.materials
            ],
        ),
        alignment=alignment,
        counts=counts,
        case_level_changed=case_level,
        rules_differ_from_archive=rules_differ,
        identical=identical,
        note_code=(
            "identical_to_recorded"
            if identical
            else "rules_differ_from_archive"
            if rules_differ
            else "reread_of_recorded"
        ),
    )


__all__ = [
    "OVERLAP_THRESHOLD",
    "STRUCTURAL_FIELDS",
    "AlignmentRow",
    "Analyzer",
    "Difference",
    "RecordedCaseFile",
    "RecordedCaseView",
    "RecordedEntry",
    "RecordedEntryView",
    "RereadCaseView",
    "RereadCounts",
    "RereadMaterialView",
    "RereadResult",
    "align",
    "candidates_for",
    "reread_case_file",
]
