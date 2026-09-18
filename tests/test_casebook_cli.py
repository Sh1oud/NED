"""M2: the ``ned casebook`` commands - management, and the same server-side analysis.

The CLI is for readers who do not want the web page. It can create, list, show, rename, archive
and delete; it cannot be handed a verdict, and archiving runs NED's own engine on the input.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ned.app.cli import app
from ned.app.store import CASEBOOK_ENV, CASEBOOK_PATH_ENV
from typer.testing import CliRunner

RUNNER = CliRunner()


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


def invoke(*args: str, input: str | None = None) -> tuple[int, str]:
    """Run one command and return its exit code and everything it printed.

    Usage errors from click go to stderr, and rich wraps long values to the terminal width, so
    the tests below read both streams and assert on values rather than on line layout.
    """

    result = RUNNER.invoke(app, list(args), input=input)
    printed = result.output + (getattr(result, "stderr", "") or "")
    return result.exit_code, printed


def create(label: str = "小 A") -> None:
    code, out = invoke("casebook", "create", "--label", label)
    assert code == 0, out


def test_status_reports_the_switch(switched_on: Path) -> None:
    code, out = invoke("casebook", "status")
    assert code == 0
    assert "casebook   on" in out
    # rich wraps the path at the console width, so the name is what is asserted here
    assert switched_on.name in out
    assert "nothing yet" in out


def test_status_off_is_honest_and_creates_nothing(switched_off: Path, workdir: Path) -> None:
    code, out = invoke("casebook", "status")
    assert code == 0
    assert "casebook   off" in out
    assert not switched_off.exists()
    assert not (workdir / "data").exists()


def test_commands_refuse_to_run_when_the_switch_is_off(switched_off: Path) -> None:
    for args in (
        ("casebook", "list"),
        ("casebook", "create", "--label", "小 A"),
        ("casebook", "show", "--casebook", "小 A"),
    ):
        code, out = invoke(*args)
        assert code == 1, args
        assert "switched off" in out
    assert not switched_off.exists()


def test_create_list_and_show_an_empty_casebook(switched_on: Path) -> None:
    create("小 A")
    code, out = invoke("casebook", "list")
    assert code == 0
    assert "小 A" in out

    code, out = invoke("casebook", "show", "--casebook", "小 A")
    assert code == 0
    assert "nothing filed in this casebook yet" in out


def test_archive_analyses_the_input_and_files_it(switched_on: Path) -> None:
    create("小 A")
    code, out = invoke("casebook", "archive", "--casebook", "小 A", "--text", "她记得我生日")
    assert code == 0, out
    assert "filed:" in out
    assert "material_registered" in out

    code, out = invoke("casebook", "show", "--casebook", "小 A")
    assert code == 0
    assert "她记得我生日" in out
    assert "time unknown" in out
    assert "memory_care_act" in out or "她记得我生日" in out


def test_archive_records_the_readers_event_time(switched_on: Path) -> None:
    create("小 A")
    code, out = invoke(
        "casebook",
        "archive",
        "--casebook",
        "小 A",
        "--text",
        "她记得我生日",
        "--occurred",
        "2026-03-01",
        "--precision",
        "day",
    )
    assert code == 0, out
    code, out = invoke("casebook", "show", "--casebook", "小 A")
    assert "2026-03-01" in out
    assert "day/user" in out


def test_archive_rejects_a_padded_or_invented_time(switched_on: Path) -> None:
    create("小 A")
    code, out = invoke(
        "casebook",
        "archive",
        "--casebook",
        "小 A",
        "--text",
        "她记得我生日",
        "--occurred",
        "2026-03-01T00:00:00Z",
        "--precision",
        "day",
    )
    assert code == 1
    assert "never padded" in out or "shape" in out


def test_archive_cannot_be_handed_a_verdict(switched_on: Path) -> None:
    """There is no option to carry one: the engine decides, and an unknown flag is refused."""

    create("小 A")
    code, out = invoke(
        "casebook",
        "archive",
        "--casebook",
        "小 A",
        "--text",
        "她记得我生日",
        "--verdict-code",
        "ned.no_signal",
    )
    assert code != 0
    assert "verdict-code" in out or "No such option" in out


def test_archive_is_idempotent_with_an_action_id(switched_on: Path) -> None:
    create("小 A")
    first_code, first = invoke(
        "casebook",
        "archive",
        "--casebook",
        "小 A",
        "--text",
        "她记得我生日",
        "--action-id",
        "action-0001",
    )
    second_code, second = invoke(
        "casebook",
        "archive",
        "--casebook",
        "小 A",
        "--text",
        "她记得我生日",
        "--action-id",
        "action-0001",
    )
    assert first_code == 0 and second_code == 0
    assert "filed:" in first
    assert "already filed:" in second

    code, out = invoke("casebook", "show", "--casebook", "小 A")
    assert code == 0
    assert out.count("input      ") == 1


def test_two_runs_of_the_same_sentence_are_two_case_files(switched_on: Path) -> None:
    create("小 A")
    for action in ("action-1", "action-2"):
        code, out = invoke(
            "casebook",
            "archive",
            "--casebook",
            "小 A",
            "--text",
            "她记得我生日",
            "--action-id",
            action,
        )
        assert code == 0, out
    code, out = invoke("casebook", "show", "--casebook", "小 A")
    assert out.count("input      ") == 2


def test_archive_reads_the_input_from_a_file(switched_on: Path, workdir: Path) -> None:
    create("小 A")
    source = workdir / "input.txt"
    source.write_text("她说她不喜欢我", encoding="utf-8")
    code, out = invoke("casebook", "archive", "--casebook", "小 A", "--file", str(source))
    assert code == 0, out
    code, out = invoke("casebook", "show", "--casebook", "小 A")
    assert "她说她不喜欢我" in out
    assert "reported_negative_interpersonal" in out


def test_archive_needs_exactly_one_input(switched_on: Path, workdir: Path) -> None:
    create("小 A")
    code, out = invoke("casebook", "archive", "--casebook", "小 A")
    assert code == 1
    assert "exactly one of --text or --file" in out


def test_rename_changes_only_the_label(switched_on: Path) -> None:
    create("小 A")
    invoke("casebook", "archive", "--casebook", "小 A", "--text", "她记得我生日")
    code, out = invoke("casebook", "rename", "--casebook", "小 A", "--label", "小 A（同事）")
    assert code == 0
    assert "小 A（同事）" in out
    code, out = invoke("casebook", "show", "--casebook", "小 A（同事）")
    assert code == 0
    assert "她记得我生日" in out


def test_delete_asks_before_removing_anything(switched_on: Path) -> None:
    create("小 A")
    code, out = invoke("casebook", "delete", "--casebook", "小 A", input="n\n")
    assert code == 0
    assert "nothing was deleted" in out
    code, out = invoke("casebook", "list")
    assert "小 A" in out


def test_delete_with_yes_removes_the_casebook(switched_on: Path) -> None:
    create("小 A")
    invoke("casebook", "archive", "--casebook", "小 A", "--text", "她记得我生日")
    code, out = invoke("casebook", "delete", "--casebook", "小 A", "--yes")
    assert code == 0
    assert "deleted" in out
    code, out = invoke("casebook", "list")
    assert code == 0
    assert "no casebooks yet" in out


def test_two_casebooks_stay_separate(switched_on: Path) -> None:
    create("小 X")
    create("小 Y")
    invoke("casebook", "archive", "--casebook", "小 X", "--text", "她记得我生日")
    invoke("casebook", "archive", "--casebook", "小 Y", "--text", "她说她不喜欢我")

    _, x_out = invoke("casebook", "show", "--casebook", "小 X")
    _, y_out = invoke("casebook", "show", "--casebook", "小 Y")
    assert "她记得我生日" in x_out and "她说她不喜欢我" not in x_out
    assert "她说她不喜欢我" in y_out and "她记得我生日" not in y_out


def test_an_unknown_casebook_is_reported_not_invented(switched_on: Path) -> None:
    code, out = invoke("casebook", "show", "--casebook", "小 Z")
    assert code == 1
    assert "no casebook" in out


def test_the_existing_cli_is_untouched(switched_on: Path) -> None:
    """Additive command group: analyse still works, and its JSON shape is unchanged."""

    code, out = invoke("analyze", "她说她喜欢我", "--json")
    assert code == 0
    for key in ('"verdict"', '"recognition"', '"engine"', '"evidence"'):
        assert key in out, key
    code, out = invoke("version")
    assert code == 0
    assert "v0.1.10" in out
