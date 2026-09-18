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


class ImmutableRecordError(CasebookError):
    """An archived case file or entry was about to be changed.

    Both layers refuse this: the repository exposes no update path for those tables, and the
    database carries a trigger that aborts an UPDATE even from raw SQL.
    """


class CasebookNotFoundError(CasebookError):
    """The requested casebook, case file or entry is not in the file."""


__all__ = [
    "CasebookConfigError",
    "CasebookCorruptError",
    "CasebookDisabledError",
    "CasebookError",
    "CasebookNotFoundError",
    "ImmutableRecordError",
    "SchemaTooNewError",
]
