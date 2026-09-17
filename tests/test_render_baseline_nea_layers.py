"""BATCH 6-A: the render baseline for the three evidence-comparison layers.

Nothing here changes what the layers compute; the file freezes how they are presented
and keeps the two surfaces presenting them the same way.

The three layer names are the one part of the comparison surface that is *not* in the
shared personality catalogue: the CLI spells them out in ``cli.py`` and the web page
spells them out in ``index.html``. Two literal copies with no single source is exactly
how a surface drifts, so these assertions are what keep them saying the same thing.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from ned.app.cli import render_asymmetry_panel
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import AsymmetryResult
from ned.app.main import app as api_app
from rich.console import Console

POSITIVE = "她昨天陪我聊了两个小时，还主动问我今天怎么样。"
NEGATIVE = "她今天让我别再联系她了。"

#: The layers, in the order a reader meets them: the clues, then the policy, then the
#: only section allowed to say anything about the reader.
LAYERS = ("Evidence Profile", "NED Treatment", "Your Reading")
CARD_TITLE = "Evidence Comparison"

#: The legacy composite. It stays in the payload for old clients and is never printed
#: as a result. The page names it only to say it is deprecated, in its own wording.
LEGACY_COMPOSITE = ("asymmetry_score", "sub_scores")
PAGE_LEGACY_DISCLOSURE = ("asymmetry_score", "asymmetry_label", "sub-scores")


@pytest.fixture(scope="module")
def asymmetry() -> AsymmetryResult:
    analyzer = NedAnalyzer()
    return analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)


def cli_panel_text(asymmetry: AsymmetryResult) -> str:
    console = Console(record=True, width=120, file=io.StringIO())
    console.print(render_asymmetry_panel(asymmetry))
    return console.export_text()


def web_page_text() -> str:
    with TestClient(api_app) as client:
        return client.get("/").text


def test_the_cli_prints_the_three_layers_in_reading_order(asymmetry: AsymmetryResult) -> None:
    text = cli_panel_text(asymmetry)
    positions = [text.find(layer) for layer in LAYERS]
    assert all(position >= 0 for position in positions), (LAYERS, positions)
    assert positions == sorted(positions), positions


def test_the_web_page_names_the_same_three_layers_in_the_same_order() -> None:
    page = web_page_text()
    positions = [page.find(layer) for layer in LAYERS]
    assert all(position >= 0 for position in positions), (LAYERS, positions)
    assert positions == sorted(positions), positions


def test_both_surfaces_call_the_comparison_by_the_same_name(asymmetry: AsymmetryResult) -> None:
    assert CARD_TITLE in cli_panel_text(asymmetry)
    assert CARD_TITLE in web_page_text()


def test_the_cli_never_prints_the_legacy_composite(asymmetry: AsymmetryResult) -> None:
    """The composite is in the data and still withheld from the screen."""

    payload = asymmetry.model_dump(mode="json")
    assert "asymmetry_score" in payload, "the legacy field must still exist in the payload"
    assert payload["sub_scores"], "the legacy sub-scores must still be populated"
    assert asymmetry.asymmetry_score_is_legacy is True
    text = cli_panel_text(asymmetry)
    for field in LEGACY_COMPOSITE:
        assert field not in text, field


def test_the_web_page_declares_the_legacy_fields_compatibility_only() -> None:
    """The page may *name* the legacy fields, but only to say they are deprecated.

    The comparison card itself must not present them as results.
    """

    page = web_page_text()
    for field in PAGE_LEGACY_DISCLOSURE:
        assert field in page, (
            f"{field} is no longer disclosed as a compatibility-only field; if the "
            "disclosure was removed on purpose, update this baseline"
        )
    assert "compatibility-only" in page
    assert "deprecated" in page


def test_every_layer_name_is_present_on_both_surfaces(asymmetry: AsymmetryResult) -> None:
    """The drift guard: a rename on one surface alone fails here."""

    cli = cli_panel_text(asymmetry)
    page = web_page_text()
    for layer in LAYERS:
        assert layer in cli, layer
        assert layer in page, layer
