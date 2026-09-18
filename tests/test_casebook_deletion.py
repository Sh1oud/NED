"""M1: deletion is a storage behaviour that can be checked by reading the bytes.

A promise that a row is "gone" is worth nothing. Each test here deletes something, then scans the
database file and its sidecars for the text that was filed, and asks the same question after the
store is closed: the target must not appear in any file NED manages.

Nothing in this module claims anything beyond those files - "unrecoverable on the physical medium"
is not a claim this product makes.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ned.app.store import (
    CasebookStore,
    CaseFileSnapshot,
    MaterialSnapshot,
    sidecar_paths,
)

GENERATED_AT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)

#: Distinctive enough that a byte scan cannot match it by accident, and reversible if it ever
#: needs to be typed by hand.
INPUT_MARKER = "归档扫描输入标记-K7Q"
MATERIAL_MARKER = "归档扫描材料标记-M3Z"


def snapshot(text: str = INPUT_MARKER, material_text: str = MATERIAL_MARKER) -> CaseFileSnapshot:
    material = MaterialSnapshot(
        material_index=0,
        entry_kind="event",
        material_id="mat_" + uuid.uuid4().hex[:12],
        material_kind="memory_care_act",
        reported_content=material_text,
        start_offset=0,
        end_offset=len(material_text),
        origin_rule_id="zh.event.memory_act",
    )
    return CaseFileSnapshot(
        input_text=text,
        title="scan",
        mode="normal",
        language="zh",
        recognition="material_registered",
        verdict_code="ped.ren_hao",
        verdict_text="可能只是人好。",
        verdict_severity="warning",
        signal_type="explicit_affection",
        signal_label="明确好感",
        engine_name="ned-local-rules",
        engine_version="0.1.10",
        rules_version="0.1.0",
        generated_at=GENERATED_AT,
        materials=(material,),
    )


@pytest.fixture
def path(workdir: Path) -> Path:
    return workdir / "data" / "casebook.sqlite3"


@pytest.fixture
def store(path: Path) -> Iterator[CasebookStore]:
    opened = CasebookStore.open(path)
    yield opened
    opened.close()


def managed_files(path: Path) -> tuple[Path, ...]:
    """The database and every sidecar NED manages next to it."""

    return (path, *sidecar_paths(path))


def contains(path: Path, needle: str) -> list[str]:
    """Which managed files still hold ``needle``, as raw bytes."""

    blob = needle.encode("utf-8")
    hits = []
    for candidate in managed_files(path):
        if candidate.is_file() and blob in candidate.read_bytes():
            hits.append(candidate.name)
    return hits


def is_stored(path: Path, needle: str) -> bool:
    """Whether ``needle`` is on file at all.

    A live write sits in the write-ahead log until something checkpoints it, so "stored" means
    "in the database or in its sidecars", never "in one particular file".
    """

    return contains(path, needle) != []


def test_the_marker_really_is_stored_first(store: CasebookStore, path: Path) -> None:
    """A negative byte scan only means something once the positive one has been seen."""

    casebook = store.create_casebook("小 A")
    store.archive(casebook.casebook_id, snapshot())

    assert is_stored(path, INPUT_MARKER)
    assert is_stored(path, MATERIAL_MARKER)


def test_deleting_an_entry_removes_the_material_it_quoted(store: CasebookStore, path: Path) -> None:
    casebook = store.create_casebook("小 A")
    outcome = store.archive(casebook.casebook_id, snapshot())
    entry = store.list_entries(outcome.case_file_id)[0]

    deleted = store.delete_entry(entry.entry_id)

    assert deleted.deleted is True
    assert deleted.kind == "entry"
    assert deleted.identifier == entry.entry_id
    assert contains(path, MATERIAL_MARKER) == []
    assert store.list_entries() == []
    # the input itself was not part of that delete and is still on file
    assert is_stored(path, INPUT_MARKER)


def test_deleting_a_case_file_removes_its_input_and_entries(
    store: CasebookStore, path: Path
) -> None:
    casebook = store.create_casebook("小 A")
    outcome = store.archive(casebook.casebook_id, snapshot())

    deleted = store.delete_case_file(outcome.case_file_id)

    assert deleted.deleted is True
    assert deleted.kind == "case_file"
    assert contains(path, INPUT_MARKER) == []
    assert contains(path, MATERIAL_MARKER) == []
    assert store.list_case_files() == []
    assert store.list_entries() == []


def test_deleting_a_casebook_leaves_no_trace_of_its_contents(
    store: CasebookStore, path: Path
) -> None:
    casebook = store.create_casebook("小 A", subject_note="唯一标记-Z8")
    store.archive(casebook.casebook_id, snapshot())

    deleted = store.delete_casebook(casebook.casebook_id)

    assert deleted.deleted is True
    assert contains(path, INPUT_MARKER) == []
    assert contains(path, MATERIAL_MARKER) == []
    assert contains(path, "唯一标记-Z8") == []
    assert store.list_casebooks() == []


def test_the_scan_holds_after_the_store_is_closed(store: CasebookStore, path: Path) -> None:
    casebook = store.create_casebook("小 A")
    outcome = store.archive(casebook.casebook_id, snapshot())
    store.delete_case_file(outcome.case_file_id)
    store.close()

    assert contains(path, INPUT_MARKER) == []
    assert contains(path, MATERIAL_MARKER) == []


def test_a_delete_followed_by_more_work_still_holds(store: CasebookStore, path: Path) -> None:
    """The vacuum, then another archive: the deleted text must not come back with it."""

    casebook = store.create_casebook("小 A")
    outcome = store.archive(casebook.casebook_id, snapshot())
    store.delete_case_file(outcome.case_file_id)
    assert contains(path, INPUT_MARKER) == []

    store.archive(
        casebook.casebook_id,
        snapshot(text="另一条完全不同的输入-Q4", material_text="另一种材料-R5").model_copy(
            update={"generated_at": GENERATED_AT.replace(hour=13)}
        ),
    )
    assert contains(path, INPUT_MARKER) == []
    assert contains(path, MATERIAL_MARKER) == []
    assert is_stored(path, "另一条完全不同的输入-Q4")
    assert is_stored(path, "另一种材料-R5")


def test_the_database_stays_healthy_after_deleting(store: CasebookStore) -> None:
    casebook = store.create_casebook("小 A")
    outcome = store.archive(casebook.casebook_id, snapshot())
    store.delete_entry(store.list_entries(outcome.case_file_id)[0].entry_id)
    store.delete_case_file(outcome.case_file_id)
    store.delete_casebook(casebook.casebook_id)

    store._check_integrity()
    assert store.foreign_key_violations() == []


def test_destroy_deletes_the_file_and_its_sidecars(path: Path) -> None:
    store = CasebookStore.open(path)
    casebook = store.create_casebook("小 A")
    store.archive(casebook.casebook_id, snapshot())
    store.compact()
    store.destroy()

    assert not path.exists()
    assert not any(sidecar.exists() for sidecar in sidecar_paths(path))
