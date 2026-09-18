"""Where the casebook lives, and whether it exists at all.

Two environment variables, mirroring the rule-pack override that already exists
(``ned/app/config.py``): ``NED_CASEBOOK`` is the switch and ``NED_CASEBOOK_PATH`` is the file.

The default is **off**, and off means off: nothing is created - not the directory, not the
database, not a ``-wal`` or ``-shm`` sidecar. A reader who never turns the casebook on gets
exactly the product they had before it existed.

When it is on, the file lives in the platform's user data directory, never inside the installed
package: ``tests/test_api.py`` forbids storage artefacts under the package, and an upgrade of
the package must not be able to delete a user's file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ned.app.store.errors import CasebookConfigError

#: Master switch. Unset or ``off`` keeps the casebook entirely out of the process.
CASEBOOK_ENV = "NED_CASEBOOK"

#: Explicit file path. When set it wins over the platform default, and the switch is ignored.
CASEBOOK_PATH_ENV = "NED_CASEBOOK_PATH"

#: File name inside the platform directory.
CASEBOOK_FILENAME = "casebook.sqlite3"

#: Written into the file's ``user_version`` and into every row.
SCHEMA_VERSION = 1

_TRUE_VALUES = frozenset({"on", "1", "true", "yes", "enable", "enabled"})
#: An empty value counts as off: ``NED_CASEBOOK=`` reads as "present but not enabled", and off is
#: the safe direction. Anything else unrecognised is refused rather than guessed.
_FALSE_VALUES = frozenset({"", "off", "0", "false", "no", "disable", "disabled"})


def _package_root() -> Path:
    """The installed ``ned`` package directory."""

    return Path(__file__).resolve().parents[2]


def casebook_enabled() -> bool:
    """Whether the casebook is switched on.

    An unrecognised value is a configuration error rather than a silent default: a typo must
    not decide whether a user's text is persisted.
    """

    raw = os.environ.get(CASEBOOK_ENV)
    if raw is None:
        return False
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise CasebookConfigError(
        f"{CASEBOOK_ENV} must be one of on/off (got {raw!r}); "
        "NED does not guess whether to store your text."
    )


def casebook_path() -> Path:
    """The resolved casebook file path. Resolving never creates anything.

    An explicit ``NED_CASEBOOK_PATH`` always wins. Otherwise the file goes to the platform's
    user data directory, which is outside the package by construction; a path that would land
    inside the package is refused, because that is where the release tests (rightly) forbid
    storage artefacts.
    """

    override = os.environ.get(CASEBOOK_PATH_ENV)
    resolved = Path(override).expanduser() if override and override.strip() else _default_path()
    resolved = resolved if resolved.is_absolute() else (Path.cwd() / resolved)
    package = _package_root()
    if resolved == package or package in resolved.parents:
        raise CasebookConfigError(
            f"the casebook must live outside the installed package; {resolved} is inside {package}"
        )
    return resolved.resolve()


def _default_path() -> Path:
    """The platform's user data location, with no dependency beyond the standard library."""

    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "NED" / CASEBOOK_FILENAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "NED" / CASEBOOK_FILENAME
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "ned" / CASEBOOK_FILENAME


def sidecar_paths(path: Path) -> tuple[Path, Path]:
    """The ``-wal`` and ``-shm`` files SQLite may keep next to the database."""

    return (
        path.with_name(path.name + "-wal"),
        path.with_name(path.name + "-shm"),
    )


__all__ = [
    "CASEBOOK_ENV",
    "CASEBOOK_FILENAME",
    "CASEBOOK_PATH_ENV",
    "SCHEMA_VERSION",
    "casebook_enabled",
    "casebook_path",
    "sidecar_paths",
]
