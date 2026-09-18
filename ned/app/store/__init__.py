"""The casebook store: the only place in NED where a user's text is written to disk.

The layer is additive and self-contained on purpose:

* nothing in the semantic core imports it, and importing it never touches the disk;
* the casebook is **off by default** - with ``NED_CASEBOOK`` unset, :func:`open_casebook`
  returns ``None`` and no file, directory, WAL or shm is created, so the analysis path a reader
  gets is byte-for-byte the product they had before this layer existed;
* when it is on, the file lives in the platform user data directory (``NED_CASEBOOK_PATH``
  overrides it) and never inside the installed package.

M1 shipped storage only. M2 added the API routes, the CLI commands and the web panel, and still
nothing in this package is reachable from ``/api/analyze``.
"""

from __future__ import annotations

from pathlib import Path

from ned.app.store.casebook_db import (
    CASEBOOK_EDITABLE_COLUMNS,
    MIGRATIONS,
    CasebookStore,
    archive_token,
    sha256_text,
    utc_now_iso,
)
from ned.app.store.errors import (
    CasebookBusyError,
    CasebookConfigError,
    CasebookCorruptError,
    CasebookDisabledError,
    CasebookError,
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
    OccurredPrecision,
    OccurredSource,
    OccurredTime,
)
from ned.app.store.paths import (
    CASEBOOK_ENV,
    CASEBOOK_FILENAME,
    CASEBOOK_PATH_ENV,
    SCHEMA_VERSION,
    casebook_enabled,
    casebook_path,
    sidecar_paths,
)
from ned.app.store.snapshot import build_case_file_snapshot


def open_casebook(path: Path | None = None) -> CasebookStore | None:
    """Open the casebook, or return ``None`` when it is switched off.

    ``None`` is the honest answer for "this user has not opted in": the caller has nothing to
    close, nothing to migrate and nothing to leak.
    """

    if path is None:
        if not casebook_enabled():
            return None
        path = casebook_path()
    return CasebookStore.open(path)


def require_casebook(path: Path | None = None) -> CasebookStore:
    """Like :func:`open_casebook`, but a switched-off casebook is an error rather than ``None``."""

    store = open_casebook(path)
    if store is None:
        raise CasebookDisabledError(
            f"{CASEBOOK_ENV} is off; set it to on (or pass an explicit path) to use the casebook"
        )
    return store


__all__ = [
    "CASEBOOK_EDITABLE_COLUMNS",
    "CASEBOOK_ENV",
    "CASEBOOK_FILENAME",
    "CASEBOOK_PATH_ENV",
    "MIGRATIONS",
    "SCHEMA_VERSION",
    "ArchiveOutcome",
    "CaseFileRecord",
    "CaseFileSnapshot",
    "CasebookBusyError",
    "CasebookConfigError",
    "CasebookCorruptError",
    "CasebookDisabledError",
    "CasebookError",
    "CasebookNotFoundError",
    "CasebookRecord",
    "CasebookStore",
    "DeleteOutcome",
    "EntryRecord",
    "IdempotencyConflictError",
    "ImmutableRecordError",
    "MaterialSnapshot",
    "OccurredPrecision",
    "OccurredSource",
    "OccurredTime",
    "SchemaTooNewError",
    "archive_token",
    "build_case_file_snapshot",
    "casebook_enabled",
    "casebook_path",
    "open_casebook",
    "require_casebook",
    "rules_fingerprint",
    "sha256_text",
    "sidecar_paths",
    "utc_now_iso",
]
