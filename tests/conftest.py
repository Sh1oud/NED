"""Shared pytest fixtures.

NED is offline and stateless, so the fixtures are just the engine, a client, and - for the
casebook storage tests - a scratch directory to put a database in.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.rules import RuleBook
from ned.app.main import create_app


@pytest.fixture(scope="session")
def book() -> RuleBook:
    """The shipped rule packs."""

    return RuleBook.load()


@pytest.fixture(scope="session")
def analyzer(book: RuleBook) -> NedAnalyzer:
    """A shared analyzer instance (loads rule packs once)."""

    return NedAnalyzer(book=book)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A TestClient bound to a fresh application instance."""

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def workdir() -> Iterator[Path]:
    """A fresh, writable, empty directory for one test - then gone.

    This does not use ``tempfile.mkdtemp`` (and therefore not ``tmp_path`` either): ``mkdtemp``
    creates its directory with mode ``0o700``, which a confined session that enforces its own
    access control cannot then write into or even list. A plainly created directory with a unique
    name works everywhere, needs no plugin, and is removed by the fixture.
    """

    root = Path(tempfile.gettempdir()) / "ned-tests"
    root.mkdir(parents=True, exist_ok=True)
    directory = root / uuid.uuid4().hex
    directory.mkdir()
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)
