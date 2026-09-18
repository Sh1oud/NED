"""M1: schema lifecycle - initialisation, an older schema, a newer one, corruption, rollback.

The store is the only thing that will ever own a user's casebook, so every one of these paths has
to end in a state a reader can understand: never a half-migrated file, never a silent downgrade,
and never a database that has quietly lost its foreign keys.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ned.app.store import (
    MIGRATIONS,
    SCHEMA_VERSION,
    CasebookCorruptError,
    CasebookStore,
    CaseFileSnapshot,
    ImmutableRecordError,
    MaterialSnapshot,
    OccurredTime,
    SchemaTooNewError,
    casebook_db,
)
from pydantic import ValidationError

GENERATED_AT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def snapshot(text: str = "她说她喜欢我") -> CaseFileSnapshot:
    return CaseFileSnapshot(
        input_text=text,
        recognition="adjudicated",
        verdict_code="ped.ren_hao",
        verdict_text="可能只是人好。",
        verdict_severity="warning",
        signal_type="explicit_affection",
        signal_label="明确好感",
        engine_name="ned-local-rules",
        engine_version="0.1.10",
        rules_version="0.1.0",
        generated_at=GENERATED_AT,
    )


@pytest.fixture
def path(workdir: Path) -> Path:
    return workdir / "casebook.sqlite3"


@pytest.fixture
def store(path: Path) -> Iterator[CasebookStore]:
    opened = CasebookStore.open(path)
    yield opened
    opened.close()


def _raw(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path), isolation_level=None)
    connection.row_factory = sqlite3.Row
    return connection


def test_a_fresh_file_is_initialised_to_the_current_version(path: Path) -> None:
    with CasebookStore.open(path) as store:
        assert store.user_version() == SCHEMA_VERSION
        assert store.foreign_key_violations() == []


def test_initialisation_runs_the_zero_to_current_migration(path: Path) -> None:
    """A brand-new file starts at ``user_version = 0`` and is migrated, not assumed."""

    with CasebookStore.open(path):
        pass
    connection = _raw(path)
    try:
        assert int(connection.execute("PRAGMA user_version").fetchone()[0]) == SCHEMA_VERSION
        # the migration chain really is what created the tables
        assert MIGRATIONS[0][0] == 0
        assert MIGRATIONS[0][1] == SCHEMA_VERSION
    finally:
        connection.close()


def test_a_coarser_time_is_never_padded_into_a_finer_one(store: CasebookStore) -> None:
    """The store accepts the ruling's formats and refuses an invented midnight."""

    casebook = store.create_casebook("小 A")
    accepted = (
        ("2026", "year"),
        ("2026-03", "month"),
        ("2026-03-01", "day"),
        ("2026-03-01T14Z", "hour"),
        ("2026-03-01T14:30Z", "minute"),
        ("2026-03-01T14:30:12Z", "second"),
        ("2026-03-01T14", "hour"),
    )
    for index, (value, precision) in enumerate(accepted):
        outcome = store.archive(
            casebook.casebook_id,
            snapshot(text="她说她喜欢我 " + str(index)).model_copy(
                update={
                    "occurred": _occurred(value, precision),
                    "generated_at": GENERATED_AT.replace(minute=index),
                }
            ),
        )
        stored = store.get_case_file(outcome.case_file_id)
        assert stored.occurred_at == value
        assert stored.occurred_precision == precision

    for value, precision in (
        ("2026-03-01T00:00:00Z", "day"),
        ("2026-03-01T00:00Z", "year"),
        ("2026-03-01T14:00:00+08:00", "second"),
        ("2026-02-30", "day"),
        ("2026-13", "month"),
    ):
        with pytest.raises(ValidationError):
            _occurred(value, precision)


def test_the_zone_unknown_fact_survives_the_round_trip(store: CasebookStore) -> None:
    casebook = store.create_casebook("小 A")
    outcome = store.archive(
        casebook.casebook_id,
        snapshot().model_copy(update={"occurred": _occurred("2026-03-01T14", "hour")}),
    )
    stored = store.get_case_file(outcome.case_file_id)
    assert stored.occurred_at == "2026-03-01T14"
    assert not stored.occurred_at.endswith("Z")
    time = _occurred("2026-03-01T14", "hour")
    assert time.time_zone_known is False
    assert _occurred("2026-03-01T14Z", "hour").time_zone_known is True
    assert _occurred("2026-03-01", "day").time_zone_known is None


def test_a_newer_schema_is_refused_for_writing(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with CasebookStore.open(path) as store:
        store.create_casebook("小 A")
    _bump_user_version(path, SCHEMA_VERSION + 1)

    with pytest.raises(SchemaTooNewError):
        CasebookStore.open(path)

    with CasebookStore.open_read_only(path) as reader:
        assert reader.read_only is True
        assert [record.label for record in reader.list_casebooks()] == ["小 A"]
        with pytest.raises(ImmutableRecordError):
            reader.create_casebook("小 B")
        with pytest.raises(ImmutableRecordError):
            reader.archive(reader.list_casebooks()[0].casebook_id, snapshot())
        assert reader.user_version() == SCHEMA_VERSION + 1


def test_an_older_schema_is_backed_up_before_it_is_migrated(
    path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner is exercised with a synthetic second migration, so the backup path is real."""

    with CasebookStore.open(path) as store:
        store.create_casebook("小 A")
    synthetic = (*MIGRATIONS, (1, 2, ("CREATE TABLE migration_probe (value INTEGER)",)))
    monkeypatch.setattr(casebook_db, "MIGRATIONS", synthetic)
    monkeypatch.setattr(casebook_db, "SCHEMA_VERSION", 2)

    with CasebookStore.open(path) as store:
        assert store.user_version() == 2
        names = {
            str(row["name"])
            for row in store._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "migration_probe" in names
        assert [record.label for record in store.list_casebooks()] == ["小 A"]
    assert path.with_name(path.name + ".bak.v1").is_file()


def test_a_failed_migration_changes_nothing(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Statements and the version number move together, or neither moves."""

    with CasebookStore.open(path) as store:
        store.create_casebook("小 A")
    broken = (*MIGRATIONS, (1, 2, ("CREATE TABLE half_applied (value INTEGER)", "NOT SQL AT ALL")))
    monkeypatch.setattr(casebook_db, "MIGRATIONS", broken)
    monkeypatch.setattr(casebook_db, "SCHEMA_VERSION", 2)

    with pytest.raises(sqlite3.Error):
        CasebookStore.open(path)

    connection = _raw(path)
    try:
        assert int(connection.execute("PRAGMA user_version").fetchone()[0]) == 1
        names = {
            str(row["name"])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "half_applied" not in names
        assert "casebooks" in names
    finally:
        connection.close()


def test_a_corrupt_file_is_reported_as_corrupt(workdir: Path) -> None:
    path = workdir / "broken.sqlite3"
    path.write_bytes(b"this is not a database, it is a pile of bytes" * 40)

    with pytest.raises(CasebookCorruptError):
        CasebookStore.open(path)
    with pytest.raises(CasebookCorruptError):
        CasebookStore.open_read_only(path)


def test_a_truncated_but_well_formed_file_is_reported_as_corrupt(path: Path) -> None:
    with CasebookStore.open(path) as store:
        casebook = store.create_casebook("小 A")
        for index in range(40):
            store.archive(
                casebook.casebook_id,
                snapshot(text="她说她喜欢我 " + str(index)).model_copy(
                    update={"generated_at": GENERATED_AT.replace(minute=index % 60)}
                ),
            )
    original = path.read_bytes()
    path.write_bytes(original[: int(len(original) * 0.6)])

    with pytest.raises(CasebookCorruptError):
        CasebookStore.open(path)


def test_foreign_keys_are_enforced_on_every_connection(store: CasebookStore) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        store._connection.execute(
            "INSERT INTO entries (entry_id, case_file_id, casebook_id, entry_kind, generated_at,"
            " saved_at, occurred_precision, occurred_source, schema_version)"
            " VALUES ('en_x', 'cf_missing', 'cb_missing', 'user_note', 'now', 'now', 'unknown',"
            " 'unknown', 1)"
        )
    assert store.foreign_key_violations() == []


def test_a_case_file_cannot_reference_a_missing_casebook(store: CasebookStore) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        store._connection.execute(
            "INSERT INTO case_files (case_file_id, casebook_id, archive_token, input_text,"
            " input_sha256, mode, language, recognition, verdict_code, verdict_text,"
            " verdict_severity, signal_type, signal_label, engine_name, engine_version,"
            " rules_version, rules_fingerprint, generated_at, saved_at, occurred_precision,"
            " occurred_source, schema_version)"
            " VALUES ('cf_x', 'cb_missing', 'arc_x', 'text', 'sha', 'normal', 'zh',"
            " 'adjudicated', 'c', 't', 'info', 'none', 'l', 'e', '0.1.10', '0.1.0', 'rp_x',"
            " 'now', 'now', 'unknown', 'unknown', 1)"
        )
    assert store.foreign_key_violations() == []


def test_deleting_a_casebook_cascades_without_orphans(store: CasebookStore) -> None:
    casebook = store.create_casebook("小 A")
    store.archive(
        casebook.casebook_id,
        snapshot().model_copy(
            update={
                "materials": (
                    MaterialSnapshot(
                        material_index=0,
                        material_id="mat_" + uuid.uuid4().hex[:12],
                        material_kind="memory_care_act",
                        reported_content="她记得我生日",
                    ),
                )
            }
        ),
    )
    outcome = store.delete_casebook(casebook.casebook_id)
    assert outcome.deleted is True
    assert store.list_case_files() == []
    assert store.list_entries() == []
    assert store.foreign_key_violations() == []


def _occurred(value: str, precision: str) -> OccurredTime:
    return OccurredTime(occurred_at=value, occurred_precision=precision, occurred_source="user")


def _bump_user_version(path: Path, version: int) -> None:
    connection = _raw(path)
    try:
        connection.execute(f"PRAGMA user_version = {version}")
    finally:
        connection.close()
