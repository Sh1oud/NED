"""PHASE 3.5B-3C: the web material registry — same card, same philosophy.

The web page is the second place a reader can meet a registered material, and it is
the easy place to grow a second philosophy: a hardcoded sentence in a template, or a
renderer that quietly reads the old aspect pages instead. These tests freeze the
opposite: the card is driven by ``payload.materials`` only, every word comes from the
shared personality catalogue, and a stated boundary suppresses it entirely.

The web has no build step and no JavaScript test runner, so this follows the house
pattern used for the rest of the page: structural assertions on the shipped template,
source assertions on the shipped script, and equality against the catalogue the server
actually embeds.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ned.app.main import app as api_app
from ned.app.ui import personality as p

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "ned" / "app" / "templates" / "index.html"
SCRIPT = ROOT / "ned" / "app" / "static" / "app.js"

TEMPLATE_TEXT = TEMPLATE.read_text(encoding="utf-8")
SCRIPT_TEXT = SCRIPT.read_text(encoding="utf-8")

SECTION = "material-registry"
HOOKS = (
    "material-registry-title",
    "material-registry-intro",
    "material-registry-rows",
    "material-registry-disclaimer",
    "material-registry-isolation",
)

FLAGSHIP = "她说她讨厌我"
BOUNDARY_COLLISION = "她跟我说她讨厌我，但她说我们还是做朋友吧。"


def section_html(node_id: str = SECTION) -> str:
    """The shipped markup of one element, nested elements included."""

    opening = re.search(rf'<([a-z]+)[^>]*\bid="{node_id}"', TEMPLATE_TEXT)
    assert opening is not None, f"{node_id} is missing from the template"
    tag = opening.group(1)
    depth = 0
    for token in re.finditer(rf"</?{tag}\b", TEMPLATE_TEXT[opening.start() :]):
        if token.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                end = TEMPLATE_TEXT.find(">", opening.start() + token.end())
                return TEMPLATE_TEXT[opening.start() : end + 1]
        else:
            depth += 1
    raise AssertionError(f"{node_id} is not closed")


def function_body(name: str) -> str:
    """The source of one top-level function in app.js."""

    match = re.search(rf"\n  function {name}\((.*?)\n  \}}\n", SCRIPT_TEXT, re.DOTALL)
    assert match is not None, f"{name} is missing from app.js"
    return match.group(0)


def code_lines(body: str) -> str:
    """The function's executable lines, with whole-line comments removed."""

    return "\n".join(line for line in body.splitlines() if not line.strip().startswith("//"))


# --------------------------------------------------------------------------- #
# the container: a section with hooks, and no philosophy of its own
# --------------------------------------------------------------------------- #


def test_the_template_has_a_registry_section() -> None:
    markup = section_html()
    assert f'id="{SECTION}"' in markup
    # PR-3: the registry is stage (2) of the dossier, on the main path, so it is no longer
    # shipped hidden; the client shows or hides it from the real material list.
    details = section_html("technical-details")
    assert f'id="{SECTION}"' not in details, "the registry belongs to the dossier, not the archive"
    for hook in HOOKS:
        assert f'id="{hook}"' in markup, hook


def test_the_template_holds_no_registry_copy() -> None:
    """Every string is filled from the catalogue, so the markup is empty on purpose."""

    markup = section_html()
    copy = p.material_registry_copy("zh")
    for sentence in (
        copy["card_title"],
        copy["registration_intro"],
        copy["disclaimer"],
        copy["conclusion_isolation"],
    ):
        assert sentence not in markup, sentence
    assert p.material_registry_copy("en")["card_title"] not in markup
    # the hooks are empty elements, not pre-filled ones
    for hook in HOOKS:
        assert re.search(rf'id="{hook}"[^>]*></', markup), hook


def test_the_registry_section_is_its_own_card() -> None:
    markup = section_html()
    assert 'id="aspect-breakdown"' not in markup
    assert "aspect-rows" not in markup
    assert 'id="first-screen"' not in markup
    assert 'id="technical-details"' not in markup


# --------------------------------------------------------------------------- #
# the renderer: registry only, catalogue only, boundary first
# --------------------------------------------------------------------------- #


def test_the_renderer_reads_the_registry_and_not_the_aspect_pages() -> None:
    code = code_lines(function_body("renderMaterialRegistry"))
    assert "obj(d).materials" in code
    assert "material_aspects" not in code
    assert "aspectPages" not in code
    assert "aspect-rows" not in code


def test_the_renderer_takes_its_copy_from_the_catalogue() -> None:
    body = function_body("renderMaterialRegistry")
    for key in ("material_registry_copy", "material_source_labels"):
        assert key in body, key


def test_the_renderer_checks_the_boundary_situations_first() -> None:
    body = function_body("renderMaterialRegistry")
    assert '"boundary_situations"' in body
    assert body.index('"boundary_situations"') < body.index("card.hidden = false")


def test_the_renderer_is_wired_into_the_result_page() -> None:
    assert "renderMaterialRegistry(d, situation);" in SCRIPT_TEXT


def test_no_philosophy_is_hardcoded_in_the_web_assets() -> None:
    """The three contract lines exist once, in the catalogue, and are looked up."""

    copy = p.material_registry_copy("zh")
    english = p.material_registry_copy("en")
    for sentence in (
        copy["registration_intro"],
        copy["disclaimer"],
        copy["conclusion_isolation"],
        english["conclusion_isolation"],
    ):
        assert sentence not in SCRIPT_TEXT, sentence
        assert sentence not in TEMPLATE_TEXT, sentence
    for label in p.MATERIAL_SOURCE_LABELS["zh"].values():
        assert label not in SCRIPT_TEXT, label
        assert label not in TEMPLATE_TEXT, label


def test_the_old_aspect_card_is_untouched() -> None:
    assert "material_aspects" in SCRIPT_TEXT
    assert 'id="aspect-breakdown"' in TEMPLATE_TEXT
    assert "renderAspectBreakdown(d, situation);" in SCRIPT_TEXT


# --------------------------------------------------------------------------- #
# the catalogue the page actually receives
# --------------------------------------------------------------------------- #


def test_the_catalogue_carries_the_registry_copy() -> None:
    catalog = p.web_personality_catalog()
    assert catalog["material_registry_copy"]["zh"] == p.material_registry_copy("zh")
    assert catalog["material_registry_copy"]["en"] == p.material_registry_copy("en")
    assert catalog["material_source_labels"] == p.MATERIAL_SOURCE_LABELS
    assert set(catalog["boundary_situations"]) >= set(p.BOUNDARY_SITUATIONS)
    assert catalog["material_registry_copy"]["zh"]["disclaimer"] not in {
        "未证实",
        "存疑",
        "不可信",
    }


def test_the_served_page_embeds_the_same_copy() -> None:
    with TestClient(api_app) as client:
        page = client.get("/").text
    match = re.search(r'<script id="personality-catalog"[^>]*>(.*?)</script>', page, re.DOTALL)
    assert match is not None
    embedded = json.loads(match.group(1))
    assert (
        embedded["material_registry_copy"] == p.web_personality_catalog()["material_registry_copy"]
    )
    assert embedded["material_source_labels"] == p.MATERIAL_SOURCE_LABELS


# --------------------------------------------------------------------------- #
# the data the renderer is handed
# --------------------------------------------------------------------------- #


def test_the_payload_hands_the_renderer_the_registry() -> None:
    with TestClient(api_app) as client:
        loud = client.post("/api/analyze", json={"text": FLAGSHIP, "mode": "normal"}).json()
        quiet = client.post(
            "/api/analyze", json={"text": "我觉得她讨厌我", "mode": "normal"}
        ).json()
        boundary = client.post(
            "/api/analyze", json={"text": BOUNDARY_COLLISION, "mode": "normal"}
        ).json()
    assert len(loud["materials"]) == 1
    assert loud["materials"][0]["reported_content"] == "她讨厌我"
    assert loud["materials"][0]["source_kind"] == "attributed_report"
    assert "materials" not in quiet
    # the boundary case really does carry a material, which is why the gate matters
    assert boundary["materials"]
    assert boundary["verdict"]["code"] == "ned.direct_rejection"


@pytest.mark.parametrize("key", ("card_title", "registration_intro", "conclusion_isolation"))
def test_every_registry_string_is_bilingual(key: str) -> None:
    assert p.MATERIAL_REGISTRY_COPY["zh"][key]
    assert p.MATERIAL_REGISTRY_COPY["en"][key]
