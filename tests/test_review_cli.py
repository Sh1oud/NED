"""M3: the CLI's explicit review - same engine, same report, one extra block on request.

The CLI is a second front door, so it gets the same discipline: without ``--with-casebook`` it
reads nothing at all, and with it the report it prints is the report it always printed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ned.app.cli import app
from ned.app.core.analyzer import NedAnalyzer
from ned.app.store import CASEBOOK_ENV, CASEBOOK_PATH_ENV
from typer.testing import CliRunner

RUNNER = CliRunner()
TEXT = "她今天又主动找我"
LABEL = "小 A"


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


def create(label: str = LABEL) -> None:
    code, out = invoke("casebook", "create", "--label", label)
    assert code == 0, out


def file_into(text: str, occurred: str | None = None) -> None:
    args = ["casebook", "archive", "--casebook", LABEL, "--text", text]
    if occurred:
        args += ["--occurred", occurred, "--precision", "day"]
    code, out = invoke(*args)
    assert code == 0, out


# ------------------------------------------------------------------ default path ---
def test_the_json_report_is_unchanged_without_the_flag(switched_on: Path) -> None:
    code, out = invoke("analyze", TEXT, "--json")
    assert code == 0
    payload = json.loads(out)
    expected = NedAnalyzer().analyze_text(TEXT).model_dump(mode="json")
    payload.pop("generated_at")
    expected.pop("generated_at")
    assert payload == expected
    assert "casebook_review" not in payload


def test_without_the_flag_nothing_is_read(switched_on: Path) -> None:
    """A corrupt casebook file cannot break an ordinary analysis: it is never opened."""

    switched_on.parent.mkdir(parents=True, exist_ok=True)
    switched_on.write_bytes(b"definitely not a database" * 50)

    code, out = invoke("analyze", TEXT, "--json")
    assert code == 0
    assert "casebook_review" not in json.loads(out)


def test_the_flag_is_refused_when_the_casebook_is_off(switched_off: Path) -> None:
    code, out = invoke("analyze", TEXT, "--with-casebook", LABEL)
    assert code != 0
    assert "casebook" in out.lower()


# ----------------------------------------------------------------- explicit path ---
def test_the_review_can_be_asked_for_by_label(switched_on: Path) -> None:
    create()
    file_into("她说喜欢我", occurred="2026-07-12")

    code, out = invoke("analyze", TEXT, "--with-casebook", LABEL, "--json")
    assert code == 0, out
    payload = json.loads(out)
    review = payload["casebook_review"]
    assert review["casebook_label"] == LABEL
    assert review["items"][0]["relation"] == "supports"
    assert review["counts"]["supports"] == 1
    assert review["scored"] is False


def test_the_report_is_identical_with_and_without_the_review(switched_on: Path) -> None:
    create()
    file_into("她说喜欢我", occurred="2026-07-12")

    plain = json.loads(invoke("analyze", TEXT, "--json")[1])
    joint = json.loads(invoke("analyze", TEXT, "--with-casebook", LABEL, "--json")[1])
    joint.pop("casebook_review")
    plain.pop("generated_at")
    joint.pop("generated_at")
    assert plain == joint


def test_a_review_of_a_positive_history_supports_the_current_case(switched_on: Path) -> None:
    create()
    file_into("她连续两次主动找我")

    code, out = invoke("analyze", TEXT, "--with-casebook", LABEL, "--json")
    assert code == 0, out
    review = json.loads(out)["casebook_review"]
    assert review["items"][0]["relation"] == "supports"
    assert review["summary_code"] == "only_supports"


def test_a_declared_event_time_makes_the_order_known(switched_on: Path) -> None:
    create()
    file_into("她说喜欢我", occurred="2026-07-12")

    code, out = invoke(
        "analyze",
        "她明确说只想做朋友",
        "--with-casebook",
        LABEL,
        "--occurred",
        "2026-08-03",
        "--precision",
        "day",
        "--json",
    )
    assert code == 0, out
    review = json.loads(out)["casebook_review"]
    assert review["items"][0]["relation"] == "superseded"
    assert review["governing"]["item_kind"] == "current_case"


def test_the_printed_block_says_what_it_is(switched_on: Path) -> None:
    create()
    file_into("她说喜欢我", occurred="2026-07-12")

    code, out = invoke("analyze", TEXT, "--with-casebook", LABEL)
    assert code == 0, out
    assert "Casebook review" in out
    assert "not a new verdict" in out
    assert "casebook opinion" in out


def test_an_unknown_casebook_is_reported_not_invented(switched_on: Path) -> None:
    create()
    code, out = invoke("analyze", TEXT, "--with-casebook", "cb_does_not_exist")
    assert code != 0
    assert "cb_does_not_exist" in out


def test_a_date_without_the_flag_is_an_error_rather_than_a_silent_ignore(
    switched_on: Path,
) -> None:
    create()
    code, out = invoke("analyze", TEXT, "--occurred", "2026-08-03")
    assert code != 0
    assert "--with-casebook" in out


def test_a_review_writes_nothing_to_the_casebook(switched_on: Path) -> None:
    create()
    file_into("她说喜欢我", occurred="2026-07-12")

    before = invoke("casebook", "status")[1]
    invoke("analyze", TEXT, "--with-casebook", LABEL)
    after = invoke("casebook", "status")[1]
    assert before == after
