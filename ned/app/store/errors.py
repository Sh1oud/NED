"""Casebook store errors.

Every failure mode the store must survive has a name, so a caller never has to guess what went
wrong and never has to catch a bare ``Exception`` to find out.
"""

from __future__ import annotations


class CasebookError(Exception):
    """Base class for every casebook failure."""


class CasebookDisabledError(CasebookError):
    """The store was asked for while ``NED_CASEBOOK`` is off.

    The default is off, so this is the ordinary path: no directory, no database, no sidecar
    file, and nothing to clean up.
    """


class CasebookConfigError(CasebookError):
    """Configuration cannot be honoured (unknown switch value, path inside the package)."""


class SchemaTooNewError(CasebookError):
    """The file was written by a newer NED than this one.

    The store refuses to write to it rather than downgrade a schema it does not understand.
    """


class CasebookCorruptError(CasebookError):
    """``PRAGMA integrity_check`` did not answer ``ok``."""


class CasebookBusyError(CasebookError):
    """The file is in use by another request and did not come free in time.

    This is a "try again", not a verdict about the file: the store never reports a held lock as
    corruption, and it never reports corruption as a held lock.
    """


class ImmutableRecordError(CasebookError):
    """An archived case file or entry was about to be changed.

    Both layers refuse this: the repository exposes no update path for those tables, and the
    database carries a trigger that aborts an UPDATE even from raw SQL.
    """


class CasebookNotFoundError(CasebookError):
    """The requested casebook, case file or entry is not in the file."""


class IdempotencyConflictError(CasebookError):
    """One action id was reused for different content.

    A replay of the same action is a no-op; a *different* archive wearing the same action id is
    a client mistake, and answering with the first case file would silently lose the second.
    """


__all__ = [
    "CasebookBusyError",
    "CasebookConfigError",
    "CasebookCorruptError",
    "CasebookDisabledError",
    "CasebookError",
    "CasebookNotFoundError",
    "ImmutableRecordError",
    "SchemaTooNewError",
]
