"""FRONT DESK RENEWAL-6: the hall's copy exists once, in the shared catalogue.

The front desk is the easiest place in this product to grow a second source of
truth: a window name typed into the template, or a script that invents its own
fallback sentence. These pins freeze the opposite.

* the five hall labels exist once, in ``personality.web_personality_catalog()``,
  complete in both languages, with the wording the commander froze;
* the shipped template, script and stylesheet carry no copy of that wording, and
  the client names no stage, no progress and no issuance outcome;
* the labels are hall chrome: they never reach a result screen, they consult no
  situation, and a boundary screen gains no administrative punchline from them;
* the 47 catalogue keys that existed at ``1ab2c13`` keep their meaning, key by
  key. ``first_screen`` is inside that guard, so ``no_signal``, ``boundary`` and
  ``timeline_boundary`` copy cannot move either.

Regenerate the digests with ``_rc\\fd6\\make_pins.py`` (kept with the batch
evidence) after a change that is genuinely meant to move an old catalogue key.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ned.app.main import app as api_app
from ned.app.ui import personality as p

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "ned" / "app" / "templates" / "index.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "ned" / "app" / "static" / "app.js").read_text(encoding="utf-8")
STYLE = (ROOT / "ned" / "app" / "static" / "style.css").read_text(encoding="utf-8")

#: The frozen wording, key by key: (zh, en). The English intake heading is
#: "Submit material for review", not the longer draft this batch started from.
FRONT_DESK = {
    "hall_title": (
        "NED 不确定性审查局 · 网上办事大厅",
        "NED Uncertainty Review Bureau · Online Service Hall",
    ),
    "intake_heading": ("请提交待审查材料", "Submit material for review"),
    "submit_label": ("提交审查", "Submit for review"),
    "records_heading": ("审查记录", "Review record"),
    "issuance_heading": ("签发状态", "Issuance status"),
}

#: One hall label per injected element. ``analyze-submit`` is the pre-existing
#: button; every other anchor is the element the label was always meant to name.
ANCHORS = {
    "hall_title": "hall-title",
    "intake_heading": "intake-heading",
    "submit_label": "analyze-submit",
    "records_heading": "records-heading",
    "issuance_heading": "issuance-heading",
}

#: Punchlines a serious screen is never allowed to carry. The register is scoped
#: per situation: ``timeline_boundary``'s own locked copy contains 「害羞」 only
#: inside the denial "后面的边界也不是害羞", so that screen is judged on the two
#: emoji the older pin already bans there. A new hall label must smuggle none of
#: this into either register.
ADMIN_JOKES = {
    p.SITUATION_BOUNDARY: ("👍", "🤠", "人好", "七种替代解释", "十年", "同行评审", "害羞"),
    p.SITUATION_TIMELINE_BOUNDARY: ("👍", "🤠"),
}

#: sha256 (first 16 hex digits) of each legacy catalogue value's canonical JSON,
#: recorded before FD-6 added ``front_desk``. Any semantic move inside one of these
#: keys fails this pin with the key's own name.
LEGACY_DIGESTS = {
    "analysis": "250b372248f860cc",
    "aspect_boundary_copy": "f35f3b28c894921c",
    "aspect_card_situations": "60a82af717b9b183",
    "aspect_copy": "499adcce0093fcfc",
    "aspect_page_labels": "bedf503416663423",
    "audit_copy": "dec15f86cddb9642",
    "audit_default_lines": "ffd37c09aa8ebe8a",
    "audit_flavours": "b44625121b37182b",
    "boundary_page_types": "d8769523cb558fab",
    "boundary_situations": "ecb9ba9ac7a04d69",
    "clause_separators": "38c3028c45d8c064",
    "comedy_by_rule": "57927ada31f096ff",
    "comedy_packs": "a3d68173fda4b574",
    "comparison_reason_verdicts": "dcf655e6a52c16da",
    "display_repairs": "0c85798b360cae47",
    "duration_artifacts": "6280be706771d8e3",
    "explanation_audit_situation": "ad2cd00b23e1fded",
    "explicit_quality": "7234881cfcd7008f",
    "fact_fixed": "8a91dc777c8e26a9",
    "fact_from_observed": "4fa517ba814a6f40",
    "fact_signal_types": "ba3275bfc9079256",
    "first_screen": "8c8b7922998baf13",
    "fnbp": "7994bf15041ee88d",
    "forbidden_emoji": "481b2746fd57ccc6",
    "greeting_one_off_fact": "50c73d562e214552",
    "greeting_rule": "c761251984edf77a",
    "material_registry_copy": "bbd6798b3ec0ab33",
    "material_source_labels": "9e1d5564cd46516d",
    "materials_fallback": "e91bc9d0e4f42b71",
    "materials_slot": "4c574c2750831337",
    "multiple_aspects_promotes": "5c24f383b7663c99",
    "multiple_aspects_situation": "707ae98de8e6e1d1",
    "nea_framing": "663e20a49009c236",
    "pair_quality_labels": "4451d1cf98c3ffe4",
    "quality_bands": "6574afa83267a357",
    "quality_source": "9bcb5f2fb56fa750",
    "quality_top": "d8d703409a488ac1",
    "reading_signal_types": "746cb6535b12e731",
    "reading_slot": "f5ed8765ad778d8a",
    "routine_claim": "1594749f33ff93ae",
    "routine_markers": "c4eb024617f279ec",
    "self_discount_promotes": "f9436d130c0792a1",
    "self_discount_signal_types": "48ad26d88952017e",
    "situation_by_comparison_reason": "326ef654387ae3aa",
    "situation_by_verdict": "cb5134fcf1c2a773",
    "user_reading": "ebd7685ebb268c9e",
    "verdict_overrides": "43d774733393a9ee",
}


def digest(value: object) -> str:
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def hall_section() -> str:
    """The hall-copy block of app.js, with its whole-line comments removed."""

    match = re.search(r"/\* -+ hall copy \*/(.*?)/\* -+ init \*/", SCRIPT, re.DOTALL)
    assert match is not None, "the hall-copy block is missing from app.js"
    return "\n".join(
        line for line in match.group(1).splitlines() if not line.strip().startswith("//")
    )


def screens() -> list[str]:
    """Every first screen the catalogue ships, as one flat list of blobs."""

    return [
        " ".join([screen.title, *screen.lines, screen.reality])
        for per_mode in p.FIRST_SCREEN.values()
        for languages in per_mode.values()
        for screen in languages.values()
    ]


# --------------------------------------------------------------------------- #
# the copy: one block, five labels, both languages
# --------------------------------------------------------------------------- #


def test_the_hall_has_exactly_the_five_frozen_labels() -> None:
    catalog = p.web_personality_catalog()
    assert catalog["front_desk"] == p.FRONT_DESK_COPY
    assert set(catalog["front_desk"]) == set(FRONT_DESK)
    for key, wording in FRONT_DESK.items():
        assert catalog["front_desk"][key] == {"zh": wording[0], "en": wording[1]}, key


@pytest.mark.parametrize("key", sorted(FRONT_DESK))
def test_every_hall_label_is_complete_in_both_languages(key: str) -> None:
    values = p.FRONT_DESK_COPY[key]
    assert set(values) == {"zh", "en"}, key
    assert values["zh"].strip() and values["en"].strip(), key
    assert values["zh"] != values["en"], key


def test_the_served_page_embeds_the_hall_copy() -> None:
    """The client can only look the labels up because the page carries them."""

    with TestClient(api_app) as client:
        page = client.get("/").text
    match = re.search(r'<script id="personality-catalog"[^>]*>(.*?)</script>', page, re.DOTALL)
    assert match is not None
    embedded = json.loads(match.group(1))
    assert embedded["front_desk"] == p.FRONT_DESK_COPY
    # the served markup keeps the strings the page has always shipped; the hall
    # labels replace them at runtime, never in the template.
    assert "Analyze Evidence" in page
    assert "Technical Details" in page


# --------------------------------------------------------------------------- #
# the web assets: catalogue only, no fallback copy, no invented stage
# --------------------------------------------------------------------------- #


def test_the_web_assets_hold_no_second_copy_of_the_hall_labels() -> None:
    for key, (zh, en) in FRONT_DESK.items():
        for text in (zh, en):
            assert text not in TEMPLATE, (key, text)
            assert text not in SCRIPT, (key, text)
            assert text not in STYLE, (key, text)


def test_the_injection_reads_the_catalogue_and_names_no_stage() -> None:
    section = hall_section()
    assert 'catalogueObj("front_desk")' in section
    for key in FRONT_DESK:
        assert key in section, key
    for anchor in ANCHORS.values():
        assert f'"{anchor}"' in section, anchor
    # hall chrome, not a status machine: no result state, no situation, no verdict
    for banned in ("situation", "boundary", "verdict", "payload", "stage", "loading"):
        assert banned not in section, banned


def test_the_injection_is_wired_into_the_page_start() -> None:
    assert "renderFrontDeskCopy();" in SCRIPT
    match = re.search(r"function init\(\) \{(.*?)\n  \}", SCRIPT, re.DOTALL)
    assert match is not None
    assert "renderFrontDeskCopy();" in match.group(1)


def test_the_anchors_exist_in_the_shipped_template() -> None:
    for anchor in ANCHORS.values():
        assert f'id="{anchor}"' in TEMPLATE, anchor


def test_the_injection_holds_no_fallback_copy() -> None:
    """A silent catalogue leaves the shipped text standing; nothing is invented."""

    section = hall_section()
    for literal in ("Analyze Evidence", "Technical Details", "Verdict", "Evidence Intake"):
        assert literal not in section, literal


def test_the_language_choice_follows_the_document_declaration() -> None:
    """No locale mechanism is invented: the document's own declaration decides.

    ``zh`` and ``zh-CN`` take the zh variant; every other declaration -- including
    a missing or unknown one -- takes en. The block owns no private locale state,
    so there is nothing here to drift away from the document.
    """

    section = hall_section()
    assert "document.documentElement" in section
    assert 'getAttribute("lang")' in section
    assert 'indexOf("zh") === 0' in section
    for foreign in ("localStorage", "sessionStorage", "navigator.language", "cookie"):
        assert foreign not in section, foreign


# --------------------------------------------------------------------------- #
# the boundary: hall chrome never turns into a joke
# --------------------------------------------------------------------------- #


def test_no_hall_label_reaches_a_result_screen() -> None:
    for blob in screens():
        for key, (zh, en) in FRONT_DESK.items():
            assert zh not in blob, key
            assert en not in blob, key


@pytest.mark.parametrize("language", ("zh", "en"))
@pytest.mark.parametrize("situation", (p.SITUATION_BOUNDARY, p.SITUATION_TIMELINE_BOUNDARY))
def test_a_boundary_screen_gains_no_new_administrative_joke(situation: str, language: str) -> None:
    for mode in p.MODES:
        screen = p.first_screen(situation, mode, language)
        blob = " ".join([screen.title, *screen.lines, screen.reality])
        for ban in ADMIN_JOKES[situation]:
            assert ban not in blob, (situation, language, mode, ban)
        for key, (zh, en) in FRONT_DESK.items():
            assert zh not in blob and en not in blob, (situation, language, mode, key)


# --------------------------------------------------------------------------- #
# the 47 keys that were already there
# --------------------------------------------------------------------------- #


def test_the_legacy_catalogue_keys_are_not_overwritten() -> None:
    catalog = p.web_personality_catalog()
    assert set(catalog) == set(LEGACY_DIGESTS) | {"front_desk"}
    changed = [key for key, want in LEGACY_DIGESTS.items() if digest(catalog[key]) != want]
    assert not changed, changed
