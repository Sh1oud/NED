"""Shared pytest fixtures.

NED is offline and stateless, so the fixtures are just the engine and a client.
"""

from __future__ import annotations

from collections.abc import Iterator

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
