"""POST-v0.1.10-L1: the launcher asks before NED is allowed to keep anything.

``start_ned.bat`` is the file a Windows reader double-clicks (it is what
``README.md`` tells them to run), so it is the first place the product can either
respect or wreck the casebook's privacy promise. Before this batch it named
``NED_CASEBOOK`` nowhere: the reader got whatever the process happened to inherit,
with no way to see or choose it.

These pins freeze the opposite, at the byte level the launcher itself depends on:

* the file stays **ASCII only and CRLF only**, and never calls ``chcp`` - a ``.bat``
  is decoded with the machine's console codepage, so non-ASCII bytes differ between
  locales and mis-decoded bytes can be split by ``cmd.exe`` and executed;
* the casebook mode is settled **per startup**: an explicit, legal ``NED_CASEBOOK``
  from the caller is honoured and printed, and only when there is none is the reader
  asked;
* **off is the state before the prompt** and only the exact answer ``2`` turns it on,
  so a mistyped key, an empty line, a closed input or an interrupt can never enable
  the casebook;
* the mode is exported with ``set`` - this process only, inside the ``setlocal`` -
  and **never** with ``setx``, and it is exported before the server starts, from
  both entry paths;
* the copy keeps the meaning: mode 2 is "you may file material yourself", never
  "everything is saved for you".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from ned.app.store.paths import (
    CASEBOOK_ENV,
    SCHEMA_VERSION,
    _FALSE_VALUES,
    _TRUE_VALUES,
    casebook_enabled,
)

ROOT = Path(__file__).resolve().parents[1]
BAT_PATH = ROOT / "start_ned.bat"
RAW = BAT_PATH.read_bytes()
TEXT = RAW.decode("ascii")  # raises if a non-ASCII byte ever appears
LINES = TEXT.split("\r\n")
README = (ROOT / "README.md").read_text(encoding="utf-8")

#: What cmd.exe would actually execute: the ``rem`` lines are commentary and name
#: ``setx``/``chcp`` precisely in order to forbid them.
COMMANDS = "\n".join(line for line in LINES if not line.strip().lower().startswith("rem"))


def line_number(exact: str) -> int:
    """The 1-based line that is exactly ``exact``."""

    for number, line in enumerate(LINES, start=1):
        if line == exact:
            return number
    raise AssertionError(f"no line is exactly {exact!r}")


def line_containing(needle: str) -> int:
    """The 1-based line that first contains ``needle``."""

    for number, line in enumerate(LINES, start=1):
        if needle in line:
            return number
    raise AssertionError(f"no line contains {needle!r}")


def vocabulary(switch: str) -> list[str]:
    """The words the launcher accepts for one mode, from its ``for %%V in ( ... )`` line."""

    for line in LINES:
        if line.startswith("for %%V in (") and f"NED_CASEBOOK_MODE={switch}" in line:
            return line.split("(", 1)[1].split(")", 1)[0].split()
    raise AssertionError(f"no vocabulary line for {switch!r}")


# --------------------------------------------------------------------- the file ---
def test_the_launcher_is_the_document_entry_point() -> None:
    """This is the file the README hands a Windows reader, and it starts the server."""

    assert "start_ned.bat" in README
    assert BAT_PATH.is_file()
    assert '"%NED_CLI%" serve' in COMMANDS


def test_the_launcher_is_ascii_only() -> None:
    assert all(byte < 128 for byte in RAW)


def test_the_launcher_is_crlf_only() -> None:
    assert b"\n" not in RAW.replace(b"\r\n", b"")
    assert RAW.count(b"\r\n") == len(LINES) - 1


def test_the_launcher_never_changes_the_console_codepage() -> None:
    assert not re.search(r"(?im)^\s*chcp\b", COMMANDS)


def test_the_launcher_never_writes_the_windows_environment() -> None:
    """``setx``, ``reg add`` and the .NET setter all survive after this window closes."""

    assert not re.search(r"(?im)^\s*setx\b", COMMANDS)
    assert not re.search(r"(?im)\bsetx\b", COMMANDS)
    assert not re.search(r"(?im)^\s*reg\s+add\b", COMMANDS)
    assert "SetEnvironmentVariable" not in COMMANDS


def test_the_launcher_runs_inside_a_setlocal() -> None:
    assert "setlocal" in COMMANDS.lower()


# ------------------------------------------------------- the caller is respected ---
@pytest.mark.parametrize("word", sorted(_TRUE_VALUES))
def test_the_caller_vocabulary_for_on_is_recognised(word: str) -> None:
    """The product's own words decide, so an explicit setting is never overridden."""

    assert word in vocabulary("on")


@pytest.mark.parametrize("word", sorted(value for value in _FALSE_VALUES if value))
def test_the_caller_vocabulary_for_off_is_recognised(word: str) -> None:
    assert word in vocabulary("off")


def test_an_empty_value_is_not_a_choice() -> None:
    """``NED_CASEBOOK=`` means "not configured": the reader is asked rather than guessed at."""

    for line in LINES:
        assert '==""' not in line.replace(" ", "")


def test_an_explicit_setting_is_printed_with_its_source() -> None:
    assert "from NED_CASEBOOK, set before startup" in COMMANDS
    assert 'set "NED_MODE_SOURCE=caller"' in COMMANDS


def test_the_menu_is_skipped_only_when_a_mode_was_recognised() -> None:
    assert line_containing('set "NED_MODE_SOURCE=caller"') < line_number(":mode_summary")
    assert line_containing("if defined NED_CASEBOOK_MODE goto :mode_summary") < line_containing(
        "Startup mode"
    )


# ------------------------------------------------------------------- the reader ---
def test_off_is_the_state_before_the_prompt() -> None:
    assert line_number('set "NED_CASEBOOK_MODE=off"') < line_containing('set /p "NED_CHOICE=')


def test_only_the_exact_answer_two_enables_the_casebook() -> None:
    enabling = re.findall(r'if "%NED_CHOICE%"=="([^"]*)" (.*)', COMMANDS)
    assert enabling == [("2", 'set "NED_CASEBOOK_MODE=on"')]


def test_an_unrecognised_answer_is_announced_and_stays_off() -> None:
    assert "Not 1 or 2 - using normal mode." in COMMANDS
    assert line_containing('set /p "NED_CHOICE=') < line_containing("Not 1 or 2 - using normal mode.")


def test_the_menu_offers_both_modes() -> None:
    assert "[1] Normal mode" in COMMANDS
    assert "[2] Casebook on" in COMMANDS
    assert "Choose [1/2]: " in COMMANDS


def test_the_menu_keeps_the_privacy_meaning() -> None:
    """Mode 2 is permission to file, never a promise that NED saves things by itself."""

    assert "You may file material into a local casebook yourself." in COMMANDS
    assert "A plain analysis still saves nothing automatically." in COMMANDS
    assert "Nothing is filed or kept." in COMMANDS
    for promise in ("saved automatically", "saves your input", "we keep", "stores everything"):
        assert promise not in COMMANDS


# ------------------------------------------------------------- what it exports ---
def test_the_mode_is_exported_once_and_before_the_server() -> None:
    assert COMMANDS.count('set "NED_CASEBOOK=%NED_CASEBOOK_MODE%"') == 1
    assert line_number('set "NED_CASEBOOK=%NED_CASEBOOK_MODE%"') < line_containing('"%NED_CLI%" serve')


def test_the_exported_name_is_the_products_switch() -> None:
    assert CASEBOOK_ENV == "NED_CASEBOOK"
    assert 'set "NED_CASEBOOK=%NED_CASEBOOK_MODE%"' in COMMANDS


def test_both_entry_paths_reach_the_mode_block() -> None:
    """The "environment already ready" shortcut must not jump past the prompt."""

    assert COMMANDS.count("goto :startup_mode") == 1
    assert line_containing("goto :startup_mode") < line_number(":startup_mode")
    # the install branch falls through into the same label
    install_end = line_containing('if not exist "%NED_CLI%" goto :err_launcher_missing')
    assert install_end < line_number(":startup_mode")
    between = LINES[install_end : line_number(":startup_mode") - 1]
    assert not any("goto :launch" in line for line in between)


def test_the_mode_block_runs_before_the_launch_label() -> None:
    assert line_number(":startup_mode") < line_number(":launch")


# --------------------------------------------------------------- the product ---
def test_the_casebook_is_off_when_nothing_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """The launcher's safe default is also the product's default."""

    monkeypatch.delenv(CASEBOOK_ENV, raising=False)
    assert casebook_enabled() is False


def test_the_schema_version_is_unchanged() -> None:
    """A launcher batch touches no storage."""

    assert SCHEMA_VERSION == 1
