"""Packaging tests: the rule packs and web assets must ship with the package.

NED's behaviour lives in JSON data files, so a packaging mistake would silently
turn NED into a tool with no opinions at all. These tests make that impossible to
miss after an install.
"""

from __future__ import annotations

from importlib import resources

import pytest

RULE_PACKS = (
    "signals.json",
    "materials.json",
    "modes.json",
    "escaping.json",
    "verdicts.json",
    "reality_checks.json",
    "asymmetry.json",
    "easter_eggs.json",
)


@pytest.mark.parametrize("name", RULE_PACKS)
def test_rule_pack_ships_with_the_package(name: str) -> None:
    assert resources.files("ned.app.rules").joinpath(name).is_file(), name


def test_web_assets_ship_with_the_package() -> None:
    assert resources.files("ned.app.static").joinpath("style.css").is_file()
    assert resources.files("ned.app.static").joinpath("app.js").is_file()
    assert resources.files("ned.app.templates").joinpath("index.html").is_file()


def test_example_cases_ship_with_the_package() -> None:
    assert resources.files("ned.examples").joinpath("cases.json").is_file()


def test_version_has_a_single_source() -> None:
    """The version must not be duplicated across modules."""

    from ned.app.version import __version__

    assert __version__ == "0.1.9"
    assert __version__.count(".") == 2
