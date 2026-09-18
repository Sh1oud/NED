"""M1: the archive itself - schema, idempotency, immutability and the stored snapshot.

Every assertion here is about a fact the casebook has to keep exact: what the reader wrote, what
NED said at the time, which rules read it, and the three time fields. Two identical sentences can
be two real events, so nothing is deduplicated by text; replaying *one* archive call, on the other
hand, must change nothing.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ned.app.store import (
    SCHEMA_VERSION,
    ArchiveOutcome,
    CasebookNotFoundError,
    CasebookStore,
    CaseFileSnapshot,
    ImmutableRecordError,
    MaterialSnapshot,
    OccurredTime,
    archive_token,
    rules_fingerprint,
    sha256_text,
)

GENERATED_AT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def snapshot(
    *,
    text: str = "她说她喜欢我",
    generated_at: datetime = GENERATED_AT,
    materials: tuple[MaterialSnapshot, ...] = (),
    occurred: OccurredTime | None = None,
) -> CaseFileSnapshot:
    return CaseFileSnapshot(
        input_text=text,
        title=text[:12],
        mode="normal",
        language="zh",
        recognition="material_registered" if materials else "adjudicated",
        verdict_code="ped.ren_hao",
        verdict_text="可能只是人好。",
        verdict_severity="warning",
        signal_type="explicit_affection",
        signal_label="明确好感",
        engine_name="ned-local-rules",
        engine_version="0.1.10",
        rules_version="0.1.0",
        generated_at=generated_at,
        occurred=occurred or OccurredTime(),
        materials=materials,
    )


def material(index: int, content: str, material_id: str | None = None) -> MaterialSnapshot:
    return MaterialSnapshot(
        material_index=index,
        entry_kind="event",
        material_id=material_id if material_id is not None else "mat_" + uuid.uuid4().hex[:12],
        material_kind="memory_care_act",
        reported_content=content,
        start_offset=0,
        end_offset=len(content),
        source_kind="direct_user_statement",
        reporter_role="described_person",
        proposition_owner="described_person",
        target="reader",
        polarity="neutral",
        origin_rule_id="zh.event.memory_act",
    )


@pytest.fixture
def store(workdir: Path) -> Iterator[CasebookStore]:
    opened = CasebookStore.open(workdir / "casebook.sqlite3")
    yield opened
    opened.close()


def test_a_new_file_is_stamped_with_this_schema(store: CasebookStore) -> None:
    assert store.user_version() == SCHEMA_VERSION == 1
    assert store.read_only is False


def test_the_schema_has_the_three_tables_its_indexes_and_its_guards(
    store: CasebookStore,
) -> None:
    names = {
        str(row["name"])
        for row in store._connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')"
        )
    }
    for table in ("casebooks", "case_files", "entries"):
        assert table in names, table
    for index in (
        "idx_case_files_casebook",
        "idx_case_files_saved",
        "idx_entries_case_file",
        "idx_entries_casebook",
    ):
        assert index in names, index
    for trigger in (
        "case_files_are_immutable",
        "entries_are_immutable",
        "casebooks_keep_their_history",
    ):
        assert trigger in names, trigger
    enabled = store._connection.execute("PRAGMA foreign_keys").fetchone()
    assert int(enabled[0]) == 1


def test_archiving_stores_the_input_the_snapshot_and_the_provenance(
    store: CasebookStore,
) -> None:
    casebook = store.create_casebook("小 A", subject_note="大学同学")
    fingerprinted = rules_fingerprint()
    outcome = store.archive(
        casebook.casebook_id,
        snapshot(materials=(material(0, "她记得我生日"),)),
    )

    assert isinstance(outcome, ArchiveOutcome)
    assert outcome.created is True
    assert outcome.entry_count == 1

    case_file = store.get_case_file(outcome.case_file_id)
    assert case_file.input_text == "她说她喜欢我"
    assert case_file.input_sha256 == sha256_text("她说她喜欢我")
    assert case_file.recognition == "material_registered"
    assert case_file.verdict_code == "ped.ren_hao"
    assert case_file.verdict_severity == "warning"
    assert case_file.signal_type == "explicit_affection"
    assert case_file.engine_name == "ned-local-rules"
    assert case_file.engine_version == "0.1.10"
    assert case_file.rules_version == "0.1.0"
    assert case_file.rules_fingerprint == fingerprinted
    assert case_file.generated_at == GENERATED_AT.isoformat()
    assert datetime.fromisoformat(case_file.saved_at) >= GENERATED_AT
    assert case_file.schema_version == SCHEMA_VERSION

    entries = store.list_entries(outcome.case_file_id)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.reported_content == "她记得我生日"
    assert entry.start_offset == 0
    assert entry.end_offset == len("她记得我生日")
    assert entry.source_kind == "direct_user_statement"
    assert entry.reporter_role == "described_person"
    assert entry.proposition_owner == "described_person"
    assert entry.target == "reader"
    assert entry.origin_rule_id == "zh.event.memory_act"
    assert entry.material_id and entry.material_id.startswith("mat_")
    # the casebook's own label was copied into the entry at archive time
    assert entry.subject_label == "小 A"


def test_the_source_text_is_never_rewritten_by_the_store(store: CasebookStore) -> None:
    """``reported_content`` is a verbatim slice of the archived input, and it stays that way."""

    text = "她室友说不希望我们走太近"
    casebook = store.create_casebook("小 B")
    outcome = store.archive(
        casebook.casebook_id, snapshot(text=text, materials=(material(0, text),))
    )

    entry = store.list_entries(outcome.case_file_id)[0]
    case_file = store.get_case_file(outcome.case_file_id)
    assert case_file.input_text[entry.start_offset : entry.end_offset] == entry.reported_content


def test_replaying_one_archive_changes_nothing(store: CasebookStore) -> None:
    casebook = store.create_casebook("小 A")
    payload = snapshot(materials=(material(0, "她记得我生日"), material(1, "她说她喜欢我")))

    first = store.archive(casebook.casebook_id, payload)
    replay = store.archive(casebook.casebook_id, payload)

    assert first.created is True
    assert replay.created is False
    assert replay.case_file_id == first.case_file_id
    assert replay.archive_token == first.archive_token
    assert replay.entry_count == 2
    assert len(store.list_case_files(casebook.casebook_id)) == 1
    assert len(store.list_entries()) == 2


def test_two_identical_sentences_on_two_days_are_two_real_events(
    store: CasebookStore,
) -> None:
    """The archive token identifies the analysis instance, never the words."""

    casebook = store.create_casebook("小 A")
    monday = snapshot(text="她说她喜欢我", generated_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC))
    tuesday = snapshot(text="她说她喜欢我", generated_at=datetime(2026, 3, 2, 9, 0, tzinfo=UTC))

    first = store.archive(casebook.casebook_id, monday)
    second = store.archive(casebook.casebook_id, tuesday)

    assert first.created and second.created
    assert first.case_file_id != second.case_file_id
    assert first.archive_token != second.archive_token
    case_files = store.list_case_files(casebook.casebook_id)
    assert len(case_files) == 2
    # the content hash is identical, which is exactly why it is not the identity
    assert case_files[0].input_sha256 == case_files[1].input_sha256


def test_two_identical_sentences_archived_twice_in_one_call_are_still_one_case_file(
    store: CasebookStore,
) -> None:
    casebook = store.create_casebook("小 A")
    outcome = store.archive(
        casebook.casebook_id,
        snapshot(materials=(material(0, "她说她喜欢我"),)),
    )
    assert outcome.created is True
    assert len(store.list_case_files(casebook.casebook_id)) == 1


def test_a_duplicate_material_inside_one_case_file_is_refused_and_rolled_back(
    store: CasebookStore,
) -> None:
    """A half-archived case file must never survive a failed transaction."""

    casebook = store.create_casebook("小 A")
    duplicated = "mat_" + uuid.uuid4().hex[:12]
    payload = snapshot(
        materials=(material(0, "她记得我生日", duplicated), material(1, "她记得我生日", duplicated))
    )
    with pytest.raises(sqlite3.IntegrityError):
        store.archive(casebook.casebook_id, payload)

    assert store.list_case_files(casebook.casebook_id) == []
    assert store.list_entries() == []
    assert store.foreign_key_violations() == []


def test_the_archive_token_is_a_pure_function_of_the_instance() -> None:
    casebook_id = "cb_fixed"
    payload = snapshot()
    assert archive_token(casebook_id, payload) == archive_token(casebook_id, payload)
    other = snapshot(generated_at=datetime(2026, 3, 2, 12, 0, tzinfo=UTC))
    assert archive_token(casebook_id, payload) != archive_token(casebook_id, other)


def test_an_archived_case_file_cannot_be_updated_by_the_repository(
    store: CasebookStore,
) -> None:
    casebook = store.create_casebook("小 A")
    store.archive(casebook.casebook_id, snapshot())
    assert not hasattr(store, "update_case_file")
    assert not hasattr(store, "update_entry")
    assert not hasattr(store, "rename_case_file")


def test_an_archived_case_file_cannot_be_updated_by_raw_sql(store: CasebookStore) -> None:
    casebook = store.create_casebook("小 A")
    outcome = store.archive(casebook.casebook_id, snapshot())
    with pytest.raises(sqlite3.IntegrityError):
        store._connection.execute(
            "UPDATE case_files SET verdict_code = 'ned.no_signal' WHERE case_file_id = ?",
            (outcome.case_file_id,),
        )
    assert store.get_case_file(outcome.case_file_id).verdict_code == "ped.ren_hao"


def test_an_archived_entry_cannot_be_updated_by_raw_sql(store: CasebookStore) -> None:
    casebook = store.create_casebook("小 A")
    outcome = store.archive(
        casebook.casebook_id, snapshot(materials=(material(0, "她记得我生日"),))
    )
    entry = store.list_entries(outcome.case_file_id)[0]
    with pytest.raises(sqlite3.IntegrityError):
        store._connection.execute(
            "UPDATE entries SET reported_content = 'something else' WHERE entry_id = ?",
            (entry.entry_id,),
        )
    assert store.list_entries(outcome.case_file_id)[0].reported_content == "她记得我生日"


def test_a_casebook_may_be_renamed_and_its_history_does_not_move(
    store: CasebookStore,
) -> None:
    casebook = store.create_casebook("小 A")
    outcome = store.archive(
        casebook.casebook_id, snapshot(materials=(material(0, "她记得我生日"),))
    )

    renamed = store.update_casebook(casebook.casebook_id, label="小 A（同事）")
    assert renamed.label == "小 A（同事）"
    # the entry keeps the label it was archived with: the copy is a value, not a reference
    assert store.list_entries(outcome.case_file_id)[0].subject_label == "小 A"


def test_a_casebook_cannot_have_its_identity_or_creation_changed(
    store: CasebookStore,
) -> None:
    casebook = store.create_casebook("小 A")
    for field in ("created_at", "schema_version"):
        with pytest.raises(ImmutableRecordError):
            store.update_casebook(casebook.casebook_id, **{field: "x"})
    # the identity, creation time and schema are immutable in the database itself, too
    for statement in (
        "UPDATE casebooks SET casebook_id = 'cb_other' WHERE casebook_id = ?",
        "UPDATE casebooks SET created_at = '1999-01-01T00:00:00+00:00' WHERE casebook_id = ?",
        "UPDATE casebooks SET schema_version = 99 WHERE casebook_id = ?",
    ):
        with pytest.raises(sqlite3.IntegrityError):
            store._connection.execute(statement, (casebook.casebook_id,))
    unchanged = store.get_casebook(casebook.casebook_id)
    assert unchanged.casebook_id == casebook.casebook_id
    assert unchanged.created_at == casebook.created_at
    assert unchanged.schema_version == casebook.schema_version


def test_a_case_file_that_is_not_dated_does_not_become_today(store: CasebookStore) -> None:
    """An undated material inherits the case file's *event* time, which may well be unknown."""

    casebook = store.create_casebook("小 A")
    outcome = store.archive(
        casebook.casebook_id, snapshot(materials=(material(0, "她记得我生日"),))
    )
    entry = store.list_entries(outcome.case_file_id)[0]
    assert entry.occurred_at is None
    assert entry.occurred_precision == "unknown"
    assert entry.occurred_source == "unknown"
    assert entry.saved_at != entry.occurred_at


def test_an_entry_inherits_the_case_files_event_time_as_a_value(store: CasebookStore) -> None:
    casebook = store.create_casebook("小 A")
    declared = OccurredTime(
        occurred_at="2026-03-01", occurred_precision="day", occurred_source="user"
    )
    outcome = store.archive(
        casebook.casebook_id,
        snapshot(occurred=declared, materials=(material(0, "她记得我生日"),)),
    )
    entry = store.list_entries(outcome.case_file_id)[0]
    assert (entry.occurred_at, entry.occurred_precision, entry.occurred_source) == (
        "2026-03-01",
        "day",
        "user",
    )


def test_an_entry_may_carry_its_own_event_time(store: CasebookStore) -> None:
    casebook = store.create_casebook("小 A")
    own = OccurredTime(occurred_at="2025", occurred_precision="year", occurred_source="user")
    own_material = material(0, "她记得我生日").model_copy(update={"occurred": own})
    outcome = store.archive(
        casebook.casebook_id,
        snapshot(
            occurred=OccurredTime(
                occurred_at="2026-03-01", occurred_precision="day", occurred_source="user"
            ),
            materials=(own_material,),
        ),
    )
    entry = store.list_entries(outcome.case_file_id)[0]
    assert (entry.occurred_at, entry.occurred_precision) == ("2025", "year")


def test_a_relative_time_in_the_text_keeps_its_own_kind(store: CasebookStore) -> None:
    """``input_relative`` records that a clue existed while refusing to invent a date."""

    casebook = store.create_casebook("小 A")
    relative = OccurredTime(
        occurred_at=None, occurred_precision="unknown", occurred_source="input_relative"
    )
    outcome = store.archive(casebook.casebook_id, snapshot(occurred=relative))
    case_file = store.get_case_file(outcome.case_file_id)
    assert case_file.occurred_at is None
    assert case_file.occurred_precision == "unknown"
    assert case_file.occurred_source == "input_relative"


def test_an_unknown_casebook_cannot_be_archived_into(store: CasebookStore) -> None:
    with pytest.raises(CasebookNotFoundError):
        store.archive("cb_missing", snapshot())


def test_deleting_an_unknown_row_is_reported_not_raised(store: CasebookStore) -> None:
    assert store.delete_entry("en_missing").deleted is False
    assert store.delete_case_file("cf_missing").deleted is False
    assert store.delete_casebook("cb_missing").deleted is False


def test_the_export_is_plain_portable_data(store: CasebookStore) -> None:
    casebook = store.create_casebook("小 A")
    store.archive(casebook.casebook_id, snapshot(materials=(material(0, "她记得我生日"),)))

    exported = store.export()
    assert exported["schema_version"] == SCHEMA_VERSION
    assert len(exported["casebooks"]) == 1
    assert len(exported["case_files"]) == 1
    assert len(exported["entries"]) == 1
    assert isinstance(exported["exported_at"], str)
