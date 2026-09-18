"""The SQLite casebook: the only module in NED that imports ``sqlite3``.

Design rules this module is built to keep:

* **Off by default.** Nothing here runs unless the caller asks for it; opening a store is an
  explicit act and the switch lives in :mod:`ned.app.store.paths`.
* **Archived facts are immutable.** ``case_files`` and ``entries`` carry a trigger that aborts
  any UPDATE, and the repository exposes no update path for them. A later reinterpretation is a
  new, parallel ``reread`` record - never an overwrite.
* **Idempotent, but not text-deduplicated.** Two identical sentences on two different days are
  two real events and archive as two case files. Replaying *the same* archive call changes
  nothing: the archive token is derived from the analysis instance, not from its words.
* **Deletion is a storage behaviour, not a promise.** Deletes are real deletes, followed by a
  WAL checkpoint and a vacuum, and the tests scan the bytes of the database and its sidecars
  afterwards. Nothing here claims anything about the physical medium beyond those files.
* **A newer schema is never downgraded.** A file whose ``user_version`` is above this build's is
  refused for writing and can only be opened read-only.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from ned.app.store.errors import (
    CasebookBusyError,
    CasebookConfigError,
    CasebookCorruptError,
    CasebookNotFoundError,
    IdempotencyConflictError,
    ImmutableRecordError,
    SchemaTooNewError,
)
from ned.app.store.fingerprint import rules_fingerprint
from ned.app.store.models import (
    ArchiveOutcome,
    CasebookRecord,
    CaseFileRecord,
    CaseFileSnapshot,
    DeleteOutcome,
    EntryRecord,
    MaterialSnapshot,
)
from ned.app.store.paths import SCHEMA_VERSION, sidecar_paths

#: Every statement of schema version 1. Ordered: tables, then indexes, then the immutability
#: triggers, so a partially applied migration cannot leave tables without their guard.
_SCHEMA_V1: tuple[str, ...] = (
    """
    CREATE TABLE casebooks (
        casebook_id    TEXT PRIMARY KEY,
        label          TEXT NOT NULL CHECK (length(label) > 0),
        subject_note   TEXT NOT NULL DEFAULT '',
        created_at     TEXT NOT NULL,
        archived_at    TEXT,
        schema_version INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE case_files (
        case_file_id       TEXT PRIMARY KEY,
        casebook_id        TEXT NOT NULL REFERENCES casebooks(casebook_id) ON DELETE CASCADE,
        archive_token      TEXT NOT NULL UNIQUE,
        input_text         TEXT NOT NULL CHECK (length(input_text) > 0),
        input_sha256       TEXT NOT NULL,
        title              TEXT NOT NULL DEFAULT '',
        mode               TEXT NOT NULL,
        language           TEXT NOT NULL,
        recognition        TEXT NOT NULL,
        verdict_code       TEXT NOT NULL,
        verdict_text       TEXT NOT NULL,
        verdict_severity   TEXT NOT NULL,
        signal_type        TEXT NOT NULL,
        signal_label       TEXT NOT NULL,
        engine_name        TEXT NOT NULL,
        engine_version     TEXT NOT NULL,
        rules_version      TEXT NOT NULL,
        rules_fingerprint  TEXT NOT NULL,
        generated_at       TEXT NOT NULL,
        saved_at           TEXT NOT NULL,
        occurred_at        TEXT,
        occurred_precision TEXT NOT NULL,
        occurred_source    TEXT NOT NULL,
        user_note          TEXT NOT NULL DEFAULT '',
        schema_version     INTEGER NOT NULL,
        CHECK (occurred_precision IN
               ('year', 'month', 'day', 'hour', 'minute', 'second', 'unknown')),
        CHECK (occurred_source IN ('user', 'input_relative', 'unknown')),
        CHECK ((occurred_source = 'user') = (occurred_at IS NOT NULL)),
        CHECK ((occurred_precision = 'unknown') = (occurred_at IS NULL))
    )
    """,
    """
    CREATE TABLE entries (
        entry_id           TEXT PRIMARY KEY,
        case_file_id       TEXT NOT NULL REFERENCES case_files(case_file_id) ON DELETE CASCADE,
        casebook_id        TEXT NOT NULL REFERENCES casebooks(casebook_id) ON DELETE CASCADE,
        entry_kind         TEXT NOT NULL CHECK (entry_kind IN ('material', 'event', 'user_note')),
        material_index     INTEGER,
        material_id        TEXT,
        material_kind      TEXT NOT NULL DEFAULT '',
        reported_content   TEXT NOT NULL DEFAULT '',
        start_offset       INTEGER,
        end_offset         INTEGER,
        source_kind        TEXT NOT NULL DEFAULT '',
        reporter_role      TEXT NOT NULL DEFAULT '',
        proposition_owner  TEXT NOT NULL DEFAULT '',
        target             TEXT NOT NULL DEFAULT '',
        polarity           TEXT NOT NULL DEFAULT '',
        epistemic_status   TEXT NOT NULL DEFAULT '',
        origin_rule_id     TEXT NOT NULL DEFAULT '',
        subject_label      TEXT,
        note               TEXT NOT NULL DEFAULT '',
        generated_at       TEXT NOT NULL,
        saved_at           TEXT NOT NULL,
        occurred_at        TEXT,
        occurred_precision TEXT NOT NULL,
        occurred_source    TEXT NOT NULL,
        schema_version     INTEGER NOT NULL,
        CHECK (occurred_precision IN
               ('year', 'month', 'day', 'hour', 'minute', 'second', 'unknown')),
        CHECK (occurred_source IN ('user', 'input_relative', 'unknown')),
        CHECK ((occurred_source = 'user') = (occurred_at IS NOT NULL)),
        CHECK ((occurred_precision = 'unknown') = (occurred_at IS NULL)),
        UNIQUE (case_file_id, material_id)
    )
    """,
    "CREATE INDEX idx_case_files_casebook ON case_files(casebook_id, generated_at)",
    "CREATE INDEX idx_case_files_saved ON case_files(saved_at)",
    "CREATE INDEX idx_entries_case_file ON entries(case_file_id, material_index)",
    "CREATE INDEX idx_entries_casebook ON entries(casebook_id, generated_at)",
    """
    CREATE TRIGGER case_files_are_immutable BEFORE UPDATE ON case_files
    BEGIN
        SELECT RAISE(ABORT, 'an archived case file is immutable');
    END
    """,
    """
    CREATE TRIGGER entries_are_immutable BEFORE UPDATE ON entries
    BEGIN
        SELECT RAISE(ABORT, 'an archived entry is immutable');
    END
    """,
    """
    CREATE TRIGGER casebooks_keep_their_history
    BEFORE UPDATE OF casebook_id, created_at, schema_version ON casebooks
    BEGIN
        SELECT RAISE(ABORT, 'a casebook id, creation time and schema are immutable');
    END
    """,
)

#: ``(from_version, to_version, statements)``. M1 ships version 1 only, and the migration runner
#: is written to take more: a test injects a synthetic pair to prove backup, ordering and
#: rollback without shipping a schema it does not use yet.
MIGRATIONS: tuple[tuple[int, int, tuple[str, ...]], ...] = ((0, 1, _SCHEMA_V1),)

#: Columns a caller may change on a casebook. Everything else about a casebook is history.
CASEBOOK_EDITABLE_COLUMNS = frozenset({"label", "subject_note", "archived_at"})


def utc_now_iso() -> str:
    """The one clock the store uses for ``saved_at``."""

    return datetime.now(UTC).isoformat()


def sha256_text(text: str) -> str:
    """Content hash of the archived input, kept for integrity - never as an identity."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def archive_token(casebook_id: str, snapshot: CaseFileSnapshot, idempotency_key: str = "") -> str:
    """A stable idempotency token for one archive call.

    It identifies the **action**, not the words. The engine's ``generated_at`` is part of the
    seed, and so is the caller's ``idempotency_key`` when it supplies one: a retry or a
    double-click reuses the same key and therefore the same token, while two identical sentences
    filed by two different actions stay two real case files.
    """

    if idempotency_key:
        # The caller named the action. The token is then a function of that name and the
        # casebook, so a retry of one action lands on the same token even though the archive
        # endpoint ran a fresh analysis (and therefore a fresh ``generated_at``) for it.
        seed = {"casebook_id": casebook_id, "idempotency_key": idempotency_key}
    else:
        seed = {
            "casebook_id": casebook_id,
            "input_sha256": sha256_text(snapshot.input_text),
            "generated_at": snapshot.generated_at_utc,
            "mode": str(snapshot.mode),
            "engine_version": snapshot.engine_version,
            "rules_fingerprint": snapshot.rules_fingerprint,
        }
    blob = json.dumps(seed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "arc_" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _is_busy(error: sqlite3.Error) -> bool:
    """SQLite says "locked" or "busy" when the file is held; that is a retry, not corruption."""

    message = str(error).lower()
    return "locked" in message or "busy" in message


def _busy_error(error: sqlite3.Error) -> CasebookBusyError:
    return CasebookBusyError(f"the casebook file is in use: {error}")


def _enable_wal(connection: sqlite3.Connection, *, timeout: float = 5.0) -> None:
    """Switch the file to WAL, waiting out a switch another connection is making.

    ``PRAGMA busy_timeout`` does not cover this pragma: SQLite returns SQLITE_BUSY immediately
    when the journal mode is changing somewhere else, so the wait has to be explicit. WAL is what
    lets readers and the writer share the file at all, so it is worth the few retries.
    """

    deadline = time.monotonic() + timeout
    while True:
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            return
        except sqlite3.OperationalError as error:
            if not _is_busy(error) or time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


class CasebookStore:
    """A handle on one casebook file.

    Construct it through :meth:`open` or :meth:`open_read_only`.
    """

    def __init__(self, path: Path, connection: sqlite3.Connection, *, read_only: bool) -> None:
        self.path = path
        self._connection = connection
        self.read_only = read_only

    # -- lifecycle ---------------------------------------------------------
    @classmethod
    def open(cls, path: Path) -> CasebookStore:
        """Open (creating and migrating if needed) the casebook at ``path``."""

        path.parent.mkdir(parents=True, exist_ok=True)
        connection = cls._connect_or_corrupt(path, read_only=False)
        store = cls(path, connection, read_only=False)
        try:
            store._initialise()
        except sqlite3.OperationalError as error:
            connection.close()
            if _is_busy(error):
                raise _busy_error(error) from error
            raise
        except BaseException:
            connection.close()
            raise
        return store

    @classmethod
    def open_read_only(cls, path: Path) -> CasebookStore:
        """Open an existing casebook without ever writing to it.

        This is the only way to look at a file whose schema is newer than this build.
        """

        if not path.exists():
            raise CasebookNotFoundError(str(path))
        connection = cls._connect_or_corrupt(path, read_only=True)
        store = cls(path, connection, read_only=True)
        try:
            store._check_integrity()
        except BaseException:
            connection.close()
            raise
        return store

    @classmethod
    def _connect_or_corrupt(cls, path: Path, *, read_only: bool) -> sqlite3.Connection:
        """Connecting to something that is not a database is corruption, not a traceback."""

        try:
            return cls._connect(path, read_only=read_only)
        except sqlite3.OperationalError as error:
            if _is_busy(error):
                raise _busy_error(error) from error
            raise
        except sqlite3.DatabaseError as error:
            raise CasebookCorruptError(f"the casebook file cannot be read: {error}") from error

    @staticmethod
    def _connect(path: Path, *, read_only: bool) -> sqlite3.Connection:
        if read_only:
            # ``as_uri`` percent-encodes spaces and drive letters the way SQLite expects.
            connection = sqlite3.connect(
                path.resolve().as_uri() + "?mode=ro", uri=True, isolation_level=None
            )
        else:
            connection = sqlite3.connect(str(path), isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if not read_only:
            _enable_wal(connection)
            connection.execute("PRAGMA secure_delete = ON")
            connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> CasebookStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- schema ------------------------------------------------------------
    def user_version(self) -> int:
        row = self._connection.execute("PRAGMA user_version").fetchone()
        return int(row[0])

    def _initialise(self) -> None:
        try:
            version = self.user_version()
        except sqlite3.DatabaseError as error:
            raise CasebookCorruptError(f"the casebook file cannot be read: {error}") from error
        if version > SCHEMA_VERSION:
            raise SchemaTooNewError(
                f"this casebook was written by a newer NED (schema {version} > "
                f"{SCHEMA_VERSION}); it is opened "
                "read-only and never downgraded"
            )
        if version < SCHEMA_VERSION:
            # A migration that fails is a defect in the chain, not corruption of the file: it is
            # allowed to propagate, because the transaction has already put the file back.
            self._backup(version)
            self._migrate(version)
        self._check_integrity()

    def _backup(self, version: int) -> None:
        """Copy the file before changing its shape. A fresh file has nothing to back up."""

        if version == 0 or not self.path.exists() or self.path.stat().st_size == 0:
            return
        target = self.path.with_name(f"{self.path.name}.bak.v{version}")
        shutil.copyfile(self.path, target)

    def _migrate(self, current: int) -> None:
        """Apply the chain under the write lock, re-reading the version *inside* it.

        ``BEGIN IMMEDIATE`` is taken before the version is read, so two opens that race on a fresh
        file cannot both decide to create schema 1: the loser waits for the winner's commit, then
        sees the finished schema and does nothing. The whole chain is one transaction, so the
        statements and the version number still move together or not at all.
        """

        with self.transaction():
            current = self.user_version()
            if current > SCHEMA_VERSION:
                raise SchemaTooNewError(
                    f"this casebook was written by a newer NED (schema {current} > "
                    f"{SCHEMA_VERSION}); it is opened read-only and never downgraded"
                )
            if current == SCHEMA_VERSION:
                return
            pending = [step for step in MIGRATIONS if step[0] >= current]
            for from_version, to_version, statements in sorted(pending):
                if from_version != current:
                    raise CasebookConfigError(
                        f"no migration path from schema {current} to {to_version}"
                    )
                for statement in statements:
                    self._connection.execute(statement)
                self._connection.execute(f"PRAGMA user_version = {to_version}")
                current = to_version

    def _check_integrity(self) -> None:
        try:
            row = self._connection.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as error:
            raise CasebookCorruptError(f"the casebook file cannot be read: {error}") from error
        verdict = str(row[0]) if row is not None else ""
        if verdict != "ok":
            raise CasebookCorruptError(f"integrity_check said {verdict!r}")

    def foreign_key_violations(self) -> list[tuple[object, ...]]:
        return [tuple(row) for row in self._connection.execute("PRAGMA foreign_key_check")]

    # -- transactions ------------------------------------------------------
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """One atomic unit of work. Nothing half-archived survives a failure."""

        self._require_writable()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield self._connection
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        else:
            self._connection.execute("COMMIT")

    def _require_writable(self) -> None:
        if self.read_only:
            raise ImmutableRecordError("this casebook is open read-only")

    # -- casebooks ---------------------------------------------------------
    def create_casebook(self, label: str, subject_note: str = "") -> CasebookRecord:
        casebook_id = _new_id("cb")
        with self.transaction():
            self._connection.execute(
                "INSERT INTO casebooks (casebook_id, label, subject_note, created_at,"
                " archived_at, schema_version) VALUES (?, ?, ?, ?, NULL, ?)",
                (casebook_id, label, subject_note, utc_now_iso(), SCHEMA_VERSION),
            )
        return self.get_casebook(casebook_id)

    def get_casebook(self, casebook_id: str) -> CasebookRecord:
        row = self._connection.execute(
            "SELECT * FROM casebooks WHERE casebook_id = ?", (casebook_id,)
        ).fetchone()
        if row is None:
            raise CasebookNotFoundError(casebook_id)
        return CasebookRecord.model_validate(dict(row))

    def list_casebooks(self, *, include_archived: bool = True) -> list[CasebookRecord]:
        sql = "SELECT * FROM casebooks"
        if not include_archived:
            sql += " WHERE archived_at IS NULL"
        sql += " ORDER BY created_at, casebook_id"
        return [CasebookRecord.model_validate(dict(row)) for row in self._connection.execute(sql)]

    def update_casebook(self, casebook_id: str, **changes: str | None) -> CasebookRecord:
        """Change a casebook's display name or note. History is out of reach by construction."""

        unknown = set(changes) - CASEBOOK_EDITABLE_COLUMNS
        if unknown:
            raise ImmutableRecordError(
                "a casebook's {} cannot be changed".format(", ".join(sorted(unknown)))
            )
        self.get_casebook(casebook_id)
        if changes:
            assignments = ", ".join(f"{name} = ?" for name in changes)
            with self.transaction():
                self._connection.execute(
                    f"UPDATE casebooks SET {assignments} WHERE casebook_id = ?",
                    (*changes.values(), casebook_id),
                )
        return self.get_casebook(casebook_id)

    # -- archiving ---------------------------------------------------------
    def archive(
        self, casebook_id: str, snapshot: CaseFileSnapshot, idempotency_key: str = ""
    ) -> ArchiveOutcome:
        """Archive one analysis. Replaying the same action is a no-op, not a duplicate.

        ``idempotency_key`` is the caller's name for the user action that produced this call
        (the API's action id, the CLI's ``--action-id``). Together with the snapshot it decides
        the token, so a retry of the same action cannot file a second case file.
        """

        casebook = self.get_casebook(casebook_id)
        fingerprint = snapshot.rules_fingerprint or rules_fingerprint()
        pinned = snapshot.model_copy(update={"rules_fingerprint": fingerprint})
        token = archive_token(casebook_id, pinned, idempotency_key)
        existing = self._connection.execute(
            "SELECT case_file_id, input_sha256 FROM case_files WHERE archive_token = ?", (token,)
        ).fetchone()
        if existing is not None:
            case_file_id = str(existing["case_file_id"])
            if str(existing["input_sha256"]) != sha256_text(pinned.input_text):
                raise IdempotencyConflictError(
                    f"action {idempotency_key!r} was already used to file different "
                    "content into this casebook"
                )
            return ArchiveOutcome(
                created=False,
                case_file_id=case_file_id,
                casebook_id=casebook_id,
                archive_token=token,
                entry_count=self._count_entries(case_file_id),
            )

        case_file_id = _new_id("cf")
        saved_at = utc_now_iso()
        with self.transaction():
            self._connection.execute(
                "INSERT INTO case_files (case_file_id, casebook_id, archive_token, input_text,"
                " input_sha256, title, mode, language, recognition, verdict_code, verdict_text,"
                " verdict_severity, signal_type, signal_label, engine_name, engine_version,"
                " rules_version, rules_fingerprint, generated_at, saved_at, occurred_at,"
                " occurred_precision, occurred_source, user_note, schema_version)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
                " ?, ?)",
                (
                    case_file_id,
                    casebook_id,
                    token,
                    pinned.input_text,
                    sha256_text(pinned.input_text),
                    pinned.title,
                    str(pinned.mode),
                    str(pinned.language),
                    str(pinned.recognition),
                    pinned.verdict_code,
                    pinned.verdict_text,
                    str(pinned.verdict_severity),
                    str(pinned.signal_type),
                    pinned.signal_label,
                    pinned.engine_name,
                    pinned.engine_version,
                    pinned.rules_version,
                    pinned.rules_fingerprint,
                    pinned.generated_at_utc,
                    saved_at,
                    pinned.occurred.occurred_at,
                    pinned.occurred.occurred_precision,
                    pinned.occurred.occurred_source,
                    pinned.user_note,
                    SCHEMA_VERSION,
                ),
            )
            for material in pinned.materials:
                self._insert_entry(
                    case_file_id, casebook_id, casebook.label, pinned, material, saved_at
                )
        return ArchiveOutcome(
            created=True,
            case_file_id=case_file_id,
            casebook_id=casebook_id,
            archive_token=token,
            entry_count=len(pinned.materials),
        )

    def _insert_entry(
        self,
        case_file_id: str,
        casebook_id: str,
        casebook_label: str,
        snapshot: CaseFileSnapshot,
        material: MaterialSnapshot,
        saved_at: str,
    ) -> None:
        """Insert one entry, copying the case file's time snapshot into it.

        The copy is a value, not a reference: after this transaction the entry owns its time and
        is never re-bound to its parent. An undated material must not become "today" merely
        because it was archived today, so the inherited event time is the case file's event
        time - which may well be "unknown".
        """

        inherited = material.occurred if material.occurred is not None else snapshot.occurred
        subject = material.subject_label if material.subject_label is not None else casebook_label
        self._connection.execute(
            "INSERT INTO entries (entry_id, case_file_id, casebook_id, entry_kind,"
            " material_index, material_id, material_kind, reported_content, start_offset,"
            " end_offset, source_kind, reporter_role, proposition_owner, target, polarity,"
            " epistemic_status, origin_rule_id, subject_label, note, generated_at, saved_at,"
            " occurred_at, occurred_precision, occurred_source, schema_version)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _new_id("en"),
                case_file_id,
                casebook_id,
                material.entry_kind,
                material.material_index,
                material.material_id,
                material.material_kind,
                material.reported_content,
                material.start_offset,
                material.end_offset,
                str(material.source_kind),
                material.reporter_role,
                material.proposition_owner,
                material.target,
                str(material.polarity),
                str(material.epistemic_status),
                material.origin_rule_id,
                subject,
                material.note,
                snapshot.generated_at_utc,
                saved_at,
                inherited.occurred_at,
                inherited.occurred_precision,
                inherited.occurred_source,
                SCHEMA_VERSION,
            ),
        )

    # -- reading -----------------------------------------------------------
    def get_case_file(self, case_file_id: str) -> CaseFileRecord:
        row = self._connection.execute(
            "SELECT * FROM case_files WHERE case_file_id = ?", (case_file_id,)
        ).fetchone()
        if row is None:
            raise CasebookNotFoundError(case_file_id)
        return CaseFileRecord.model_validate(dict(row))

    def list_case_files(self, casebook_id: str | None = None) -> list[CaseFileRecord]:
        """Case files in archival order.

        Ordered by ``generated_at`` and ``saved_at`` - both complete UTC instants. Ordering by
        ``occurred_at`` is deliberately absent: that needs precision-aware comparison and
        belongs to the review layer, not to storage.
        """

        params: tuple[object, ...]
        if casebook_id is None:
            sql, params = "SELECT * FROM case_files ORDER BY generated_at, case_file_id", ()
        else:
            sql = (
                "SELECT * FROM case_files WHERE casebook_id = ? ORDER BY generated_at, case_file_id"
            )
            params = (casebook_id,)
        return [
            CaseFileRecord.model_validate(dict(row))
            for row in self._connection.execute(sql, params)
        ]

    def list_entries(
        self, case_file_id: str | None = None, casebook_id: str | None = None
    ) -> list[EntryRecord]:
        """Entries of one case file, or of one casebook, or of the whole file.

        Ordering the three ways keeps every read narrow: a request for one casebook's entries
        never loads another casebook's rows.
        """

        params: tuple[object, ...]
        if case_file_id is not None:
            sql = "SELECT * FROM entries WHERE case_file_id = ? ORDER BY material_index, entry_id"
            params = (case_file_id,)
        elif casebook_id is not None:
            sql = "SELECT * FROM entries WHERE casebook_id = ? ORDER BY saved_at, material_index"
            params = (casebook_id,)
        else:
            sql, params = "SELECT * FROM entries ORDER BY saved_at, entry_id", ()
        return [
            EntryRecord.model_validate(dict(row)) for row in self._connection.execute(sql, params)
        ]

    def find_case_file(self, casebook_id: str, case_file_id: str) -> CaseFileRecord:
        """One case file, looked up through its casebook: isolation is in the query."""

        row = self._connection.execute(
            "SELECT * FROM case_files WHERE casebook_id = ? AND case_file_id = ?",
            (casebook_id, case_file_id),
        ).fetchone()
        if row is None:
            raise CasebookNotFoundError(case_file_id)
        return CaseFileRecord.model_validate(dict(row))

    def find_entry(self, casebook_id: str, entry_id: str) -> EntryRecord:
        """One entry, looked up through its casebook, for the same reason."""

        row = self._connection.execute(
            "SELECT * FROM entries WHERE casebook_id = ? AND entry_id = ?",
            (casebook_id, entry_id),
        ).fetchone()
        if row is None:
            raise CasebookNotFoundError(entry_id)
        return EntryRecord.model_validate(dict(row))

    def stats(self) -> dict[str, int]:
        """How much is on file: casebooks, case files and entries."""

        def count(table: str) -> int:
            row = self._connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            return int(row["n"]) if row is not None else 0

        return {
            "casebooks": count("casebooks"),
            "case_files": count("case_files"),
            "entries": count("entries"),
        }

    def _count_entries(self, case_file_id: str) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) AS n FROM entries WHERE case_file_id = ?", (case_file_id,)
        ).fetchone()
        return int(row["n"]) if row is not None else 0

    # -- deletion ----------------------------------------------------------
    def delete_entry(self, entry_id: str) -> DeleteOutcome:
        row = self._connection.execute(
            "SELECT reported_content FROM entries WHERE entry_id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            return DeleteOutcome(deleted=False, kind="entry", identifier=entry_id)
        with self.transaction():
            self._connection.execute("DELETE FROM entries WHERE entry_id = ?", (entry_id,))
        self.compact()
        return DeleteOutcome(
            deleted=True,
            kind="entry",
            identifier=entry_id,
            detail="entry and the material it quoted were removed from the casebook",
        )

    def delete_case_file(self, case_file_id: str) -> DeleteOutcome:
        exists = self._connection.execute(
            "SELECT 1 FROM case_files WHERE case_file_id = ?", (case_file_id,)
        ).fetchone()
        if exists is None:
            return DeleteOutcome(deleted=False, kind="case_file", identifier=case_file_id)
        with self.transaction():
            self._connection.execute(
                "DELETE FROM case_files WHERE case_file_id = ?", (case_file_id,)
            )
        self.compact()
        return DeleteOutcome(
            deleted=True,
            kind="case_file",
            identifier=case_file_id,
            detail="case file, its input and every entry it carried were removed",
        )

    def delete_casebook(self, casebook_id: str) -> DeleteOutcome:
        exists = self._connection.execute(
            "SELECT 1 FROM casebooks WHERE casebook_id = ?", (casebook_id,)
        ).fetchone()
        if exists is None:
            return DeleteOutcome(deleted=False, kind="casebook", identifier=casebook_id)
        with self.transaction():
            self._connection.execute("DELETE FROM casebooks WHERE casebook_id = ?", (casebook_id,))
        self.compact()
        return DeleteOutcome(
            deleted=True,
            kind="casebook",
            identifier=casebook_id,
            detail="the casebook and everything filed under it were removed",
        )

    def compact(self) -> None:
        """Reclaim and overwrite the space a delete freed.

        ``secure_delete`` overwrites freed pages; the checkpoint empties the write-ahead log and
        the vacuum rewrites the file so no copy survives in a free page or a sidecar. Verified
        by scanning the bytes in ``tests/test_casebook_deletion.py``.
        """

        self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._connection.execute("VACUUM")

    def destroy(self) -> None:
        """Close the store and delete the database and its sidecars."""

        self.close()
        for path in (self.path, *sidecar_paths(self.path)):
            if path.exists():
                path.unlink()

    # -- export ------------------------------------------------------------
    def export(self) -> dict[str, object]:
        """The whole casebook as plain data. Read-only, portable, and the audit trail."""

        return {
            "schema_version": self.user_version(),
            "exported_at": utc_now_iso(),
            "casebooks": [record.model_dump() for record in self.list_casebooks()],
            "case_files": [record.model_dump() for record in self.list_case_files()],
            "entries": [record.model_dump() for record in self.list_entries()],
        }


__all__ = [
    "CASEBOOK_EDITABLE_COLUMNS",
    "MIGRATIONS",
    "CasebookStore",
    "archive_token",
    "sha256_text",
    "utc_now_iso",
]
