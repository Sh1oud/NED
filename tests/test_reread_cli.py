"""M4C: ``ned casebook reread`` - the same read-only reread from the command line.

The CLI can name a case file; it cannot supply the text, and it cannot write.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ned.app.cli import app
from ned.app.store import CASEBOOK_ENV, CASEBOOK_PATH_ENV
from typer.testing import CliRunner

RUNNER = CliRunner()
TEXT = "她记得我生日，但她说我们只是朋友"
LABEL = "小 X"


@pytest.fixture
def switched_on(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = workdir / "data" / "casebook.sqlite3"
    monkeypatch.setenv(CASEBOOK_ENV, "on")
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(target))
    return target


@pytest.fixture
def switched_off(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv(CASEBOOK_ENV, raising=False)
    target = workdir / "data" / "casebook.sqlite3"
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(target))
    return target


def invoke(*args: str) -> tuple[int, str]:
    result = RUNNER.invoke(app, list(args))
    return result.exit_code, result.output + (getattr(result, "stderr", "") or "")


def archive(text: str = TEXT) -> str:
    code, out = invoke("casebook", "create", "--label", LABEL)
    assert code == 0, out
    code, out = invoke("casebook", "archive", "--casebook", LABEL, "--text", text)
    assert code == 0, out
    return out


def case_file_id() -> str:
    """The archive command prints the case file id; read it back from the panel instead."""

    code, out = invoke("casebook", "show", "--casebook", LABEL)
    assert code == 0, out
    for token in out.replace("|", " ").replace("│", " ").split():
        if token.startswith("cf_"):
            return token.strip("│|, ")
    raise AssertionError(f"no case file id in:\n{out}")


def test_the_reread_can_be_read_as_json(switched_on: Path) -> None:
    archive()
    identifier = case_file_id()
    code, out = invoke(
        "casebook", "reread", "--casebook", LABEL, "--case-file", identifier, "--json"
    )
    assert code == 0, out
    payload = json.loads(out)
    assert payload["case_file_id"] == identifier
    assert payload["input_text"] == TEXT
    assert payload["identical"] is True
    assert payload["counts"]["same"] == 2


def test_the_printed_reread_says_it_is_not_a_rewrite(switched_on: Path) -> None:
    archive()
    identifier = case_file_id()
    code, out = invoke("casebook", "reread", "--casebook", LABEL, "--case-file", identifier)
    assert code == 0, out
    assert "Reread" in out
    assert "not a rewrite" in out
    assert "recorded" in out and "today" in out
    assert "counts: same 2" in out


def test_the_cli_cannot_supply_the_text(switched_on: Path) -> None:
    archive()
    identifier = case_file_id()
    code, out = invoke(
        "casebook",
        "reread",
        "--casebook",
        LABEL,
        "--case-file",
        identifier,
        "--text",
        "她此刻正爱着我",
    )
    assert code != 0
    assert "--text" in out or "No such option" in out


def test_an_unknown_case_file_is_reported(switched_on: Path) -> None:
    archive()
    code, out = invoke("casebook", "reread", "--casebook", LABEL, "--case-file", "cf_nope")
    assert code != 0
    assert "cf_nope" in out


def test_a_switched_off_casebook_refuses_a_reread(switched_off: Path) -> None:
    code, out = invoke("casebook", "reread", "--casebook", LABEL, "--case-file", "cf_x")
    assert code != 0
    assert "casebook" in out.lower()


def test_a_reread_writes_nothing(switched_on: Path) -> None:
    archive()
    identifier = case_file_id()
    before = invoke("casebook", "status")[1]
    code, out = invoke("casebook", "reread", "--casebook", LABEL, "--case-file", identifier)
    assert code == 0, out
    after = invoke("casebook", "status")[1]
    assert before == after
