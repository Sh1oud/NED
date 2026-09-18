"""FRONT DESK RENEWAL-4A: the serious presentation register is a closed set.

Presentation only: the register keys on the client-derived ``data-situation`` of the
result root. These pins protect the product contract around it - a stated boundary
must stay serious, must not carry the registry, and must not leak the playful emblem,
while ordinary situations must never drift into the serious register.

They add protection only; no earlier structural pin is relaxed or replaced.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "ned" / "app" / "static" / "style.css").read_text(encoding="utf-8")

SERIOUS = ("boundary", "timeline_boundary")
ORDINARY = ("positive", "no_signal", "multiple_aspects", "neutral", "hostile", "latency")

SITUATION_ATTR = re.compile(r'#analyze-results\[data-situation="([a-z_]+)"\]')
BLOCK = re.compile(r"([^{}]*)\{([^{}]*)\}", re.DOTALL)


def _situations_covered(predicate) -> set[str]:
    """Every situation the register uses for a rule whose body satisfies predicate."""

    covered: set[str] = set()
    for head, body in BLOCK.findall(CSS):
        if predicate(head, body):
            covered.update(SITUATION_ATTR.findall(head))
    return covered


def test_the_register_covers_exactly_the_boundary_situations() -> None:
    covered = _situations_covered(lambda head, body: "inset 3px 0 0 0 var(--text-dim)" in body)
    assert covered == set(SERIOUS), covered


def test_the_register_suppresses_the_emblem() -> None:
    """PR-4R: the serious register keeps the emblem down, and nothing else."""

    covered = _situations_covered(
        lambda head, body: "#verdict-emoji" in head and "display: none" in body
    )
    assert covered == set(SERIOUS), covered


def test_the_register_never_suppresses_a_registered_material() -> None:
    """A material that is really on file is shown whatever the register says."""

    hidden = _situations_covered(
        lambda head, body: "#material-registry" in head and "display: none" in body
    )
    assert not hidden, hidden


def test_ordinary_situations_never_enter_the_serious_register() -> None:
    covered = _situations_covered(lambda head, body: SITUATION_ATTR.search(head) is not None)
    assert not (covered & set(ORDINARY)), covered
    assert covered <= set(SERIOUS), covered


def test_serious_rules_are_scoped_to_the_result_root() -> None:
    """The register must not reach the first screen, which stays a display slot."""

    for situation in SERIOUS:
        marker = f'#first-screen[data-situation="{situation}"]'
        assert marker not in CSS or "#analyze-results" in CSS, marker
