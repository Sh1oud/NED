"""M1: the casebook is off by default, and off means nothing is created anywhere.

The audit that preceded this batch found that the old "we store nothing" test only looked inside
the installed package, so a database in the user data directory would have slipped past it. These
tests check the path NED would really use, resolved through the same code the store reads, and
they check that neither importing the layer nor running the whole analysis path touches disk.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ned.app.main import create_app
from ned.app.store import (
    CASEBOOK_ENV,
    CASEBOOK_FILENAME,
    CASEBOOK_PATH_ENV,
    CasebookConfigError,
    CasebookDisabledError,
    casebook_enabled,
    casebook_path,
    open_casebook,
    require_casebook,
    sidecar_paths,
)

ROOT = Path(__file__).resolve().parents[1]


def test_the_switch_is_off_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CASEBOOK_ENV, raising=False)
    assert casebook_enabled() is False


@pytest.mark.parametrize("value", ["on", "1", "true", "yes", "enable", "enabled", " ON "])
def test_the_switch_accepts_the_on_values(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CASEBOOK_ENV, value)
    assert casebook_enabled() is True


@pytest.mark.parametrize("value", ["off", "0", "false", "no", "disable", "disabled", ""])
def test_the_switch_accepts_the_off_values(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CASEBOOK_ENV, value)
    assert casebook_enabled() is False


def test_a_typo_is_a_configuration_error_not_a_silent_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(CASEBOOK_ENV, "maybe")
    with pytest.raises(CasebookConfigError):
        casebook_enabled()


def test_off_creates_nothing_at_all(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = workdir / "data" / CASEBOOK_FILENAME
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(target))
    monkeypatch.delenv(CASEBOOK_ENV, raising=False)

    assert open_casebook() is None
    assert not target.exists()
    assert not target.parent.exists()
    assert not any(sidecar.exists() for sidecar in sidecar_paths(target))


def test_asking_for_a_disabled_casebook_is_an_error_that_says_so(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(workdir / "data" / CASEBOOK_FILENAME))
    monkeypatch.delenv(CASEBOOK_ENV, raising=False)
    with pytest.raises(CasebookDisabledError):
        require_casebook()
    assert not (workdir / "data").exists()


def test_an_explicit_path_is_opened_whatever_the_switch_says(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = workdir / "explicit" / CASEBOOK_FILENAME
    monkeypatch.delenv(CASEBOOK_ENV, raising=False)
    store = open_casebook(target)
    assert store is not None
    with store:
        assert store.path == target
        assert target.is_file()


def test_the_override_wins(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    expected = (workdir / "chosen" / "book.sqlite3").resolve()
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(expected))
    assert casebook_path() == expected


def test_a_relative_override_resolves_against_the_working_directory(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(workdir)
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(Path("relative") / CASEBOOK_FILENAME))
    expected = (workdir / "relative" / CASEBOOK_FILENAME).resolve()
    assert casebook_path() == expected


def test_the_default_lives_outside_the_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CASEBOOK_PATH_ENV, raising=False)
    resolved = casebook_path()
    assert resolved.name == CASEBOOK_FILENAME
    assert ROOT not in resolved.parents
    assert (ROOT / "ned") not in resolved.parents


def test_a_path_inside_the_package_is_refused(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(ROOT / "ned" / "casebook.sqlite3"))
    with pytest.raises(CasebookConfigError):
        casebook_path()


def test_resolving_a_path_creates_nothing(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = workdir / "resolved" / CASEBOOK_FILENAME
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(target))
    monkeypatch.setenv(CASEBOOK_ENV, "on")
    for _ in range(3):
        casebook_path()
    assert not target.exists()
    assert not target.parent.exists()


def test_importing_the_layer_writes_nothing(workdir: Path) -> None:
    """A fresh interpreter imports the store and the app, with a path that does not exist yet."""

    target = workdir / "data" / CASEBOOK_FILENAME
    environment = {
        "PATH": "",
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        CASEBOOK_PATH_ENV: str(target),
    }
    completed = subprocess.run(
        [sys.executable, "-c", "import ned.app.main, ned.app.store"],
        cwd=str(workdir),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert not target.exists()
    assert not target.parent.exists()
    assert list(workdir.iterdir()) == []


def test_the_whole_analysis_path_writes_nothing_even_when_the_switch_is_on(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M1 adds no product wiring: analysing must not open the casebook even when it is enabled.

    This is the strongest form of "the analysis path is unchanged": the switch is on, the path is
    pointed at a writable temporary directory, and a real request still leaves the directory
    empty - because nothing in ``/api/analyze`` reaches the store.
    """

    target = workdir / "data" / CASEBOOK_FILENAME
    monkeypatch.setenv(CASEBOOK_ENV, "on")
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(target))

    with TestClient(create_app()) as client:
        response = client.post("/api/analyze", json={"text": "她说她喜欢我"})
        assert response.status_code == 200
        assert response.json()["verdict"]["code"]

    assert not target.exists()
    assert not target.parent.exists()
    assert not any(sidecar.exists() for sidecar in sidecar_paths(target))
