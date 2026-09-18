"""M2: the web layer's contract - what the page offers, and what it refuses to pretend.

No browser is needed for any of these: they pin the markup, the script's shape and the copy. The
behaviour is exercised for real in the browser sequence the batch ships as evidence
(``_rc/pr6m2/browser_casebook.py``), which drives Chrome against a live server.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ned.app.main import create_app
from ned.app.ui import personality as p

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "ned" / "app" / "templates" / "index.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "ned" / "app" / "static" / "app.js").read_text(encoding="utf-8")

CASEBOOK_IDS = (
    "tab-casebook",
    "panel-casebook",
    "file-to-casebook",
    "casebook-filebox",
    "casebook-picker",
    "casebook-file-new",
    "casebook-occurred",
    "casebook-file-confirm",
    "casebook-file-cancel",
    "casebook-file-status",
    "casebook-heading",
    "casebook-intro",
    "casebook-notice",
    "casebook-create-card",
    "casebook-label-input",
    "casebook-create",
    "casebook-list",
    "casebook-status",
)


def casebook_module() -> str:
    """The casebook block of the client script, markers included."""

    start = SCRIPT.index(
        "/* -------------------------------------------------------------- casebook */"
    )
    end = SCRIPT.index(
        "/* ------------------------------------------------------------- hall copy */"
    )
    return SCRIPT[start:end]


@pytest.fixture
def page() -> str:
    with TestClient(create_app()) as client:
        return client.get("/").text


def test_the_page_carries_every_casebook_element(page: str) -> None:
    for element_id in CASEBOOK_IDS:
        assert f'id="{element_id}"' in page, element_id


def test_the_casebook_panel_follows_the_tab_pattern(page: str) -> None:
    assert (
        '<section class="panel" id="panel-casebook" role="tabpanel" aria-labelledby="tab-casebook"'
        in page
    )
    assert re.search(r'<section[^>]*id="panel-casebook"[^>]*hidden', page) is not None


def test_the_tab_is_in_the_client_tab_map() -> None:
    assert '{ tab: "tab-casebook", panel: "panel-casebook" }' in SCRIPT


def test_the_action_is_hidden_until_the_server_says_it_is_available(page: str) -> None:
    """Nothing advertises filing before the status probe has answered."""

    match = re.search(r'<button[^>]*id="file-to-casebook"[^>]*>', page)
    assert match is not None
    assert "hidden" in match.group(0)
    assert "hidden = !enabled" in SCRIPT or "hidden = !enabled" in SCRIPT


def test_filing_is_the_only_thing_that_calls_archive() -> None:
    """One call site: the confirm button. Nothing files an input on its own."""

    module = casebook_module()
    assert module.count('"/archive"') == 1
    assert "confirmFile" in module
    # the action id is minted per user action and dropped after a successful one
    assert "newActionId()" in module
    assert "casebookState().actionId = null" in module


def test_the_client_never_sends_a_verdict_or_material_snapshot() -> None:
    """The anti-forgery rule, seen from the client side: it has nothing to send."""

    module = casebook_module()
    body = module[module.index("var body = {") : module.index("};", module.index("var body = {"))]
    for allowed in ("text", "mode", "action_id"):
        assert allowed in body, allowed
    # the reader's own event time is attached, and carries only the three defined fields
    assert "body.occurred = {" in module
    occurred = module[module.index("body.occurred = {") :]
    occurred = occurred[: occurred.index("};")]
    for allowed in ("occurred_at", "occurred_precision", "occurred_source"):
        assert allowed in occurred, allowed
    # the body is the whole request: no verdict, no material snapshot, no timestamp is built here
    for forbidden in ("verdict", "recognition", "materials", "generated_at", "saved_at"):
        assert forbidden not in body, forbidden
    # and the only other write is the create call, which sends a label
    assert 'fetchJson("/api/casebook", "POST", { label: label })' in module


def test_the_client_keeps_no_hidden_persistence_of_its_own() -> None:
    """Item 7: one switch, one store. The page must not invent a second memory."""

    module = casebook_module()
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "document.cookie"):
        assert forbidden not in module, forbidden


def test_the_panel_says_what_is_kept(page: str) -> None:
    intro = p.FRONT_DESK_COPY["casebook_intro"]["zh"]
    assert intro in page
    assert "只保存在本机" in intro and "主动归入" in intro


def test_the_disabled_notice_is_honest() -> None:
    disabled = p.FRONT_DESK_COPY["casebook_disabled"]["zh"]
    assert "未启用" in disabled and "NED_CASEBOOK=off" in disabled
    assert "任何输入都不会被保存" in disabled
    assert "casebook_disabled" in SCRIPT


def test_the_footer_describes_what_actually_happens(page: str) -> None:
    """The old sentence claimed a session-only browser and no persistence. It was not true."""

    assert "stays in this browser session" not in page
    assert "All input stays in this browser session" not in page
    footer = p.FRONT_DESK_COPY["privacy_footer"]["zh"]
    assert footer in page
    # it names the three things a reader needs to know
    assert "不写入任何数据库" in footer
    assert "归入卷宗" in footer and "写入本机卷宗文件" in footer
    # only the analysis mode is really kept in browser storage; the language switch is
    # page-local, so the footer must not claim that a language preference is stored
    assert "分析模式偏好保存在浏览器本地存储" in footer
    assert "界面语言切换只在当前页面生效" in footer
    assert "无遥测" in footer


def test_the_footer_has_an_english_variant_too() -> None:
    footer = p.FRONT_DESK_COPY["privacy_footer"]["en"]
    assert "casebook" in footer and "browser storage" in footer
    assert "this page only" in footer
    assert "No telemetry" in footer


@pytest.mark.parametrize(
    "key",
    [
        "casebook_tab",
        "casebook_heading",
        "casebook_intro",
        "casebook_disabled",
        "casebook_file_action",
        "casebook_file_confirm",
        "casebook_delete_ask",
        "casebook_delete_yes",
        "casebook_deleted",
        "casebook_occurred_relative",
        "privacy_footer",
    ],
)
def test_the_casebook_copy_is_complete_in_both_languages(key: str) -> None:
    values = p.FRONT_DESK_COPY[key]
    assert set(values) == {"zh", "en"}
    assert values["zh"].strip() and values["en"].strip()
    assert values["zh"] != values["en"]


def test_the_markup_fallback_matches_the_catalogue() -> None:
    """One language in the markup (zh), the English variant only from the catalogue."""

    for anchor, key in (
        ("casebook-heading", "casebook_heading"),
        ("casebook-intro", "casebook_intro"),
        ("casebook-create", "casebook_create"),
        ("casebook-file-confirm", "casebook_file_confirm"),
        ("privacy-footer", "privacy_footer"),
    ):
        match = re.search(rf'id="{re.escape(anchor)}"[^>]*>([^<]*)<', TEMPLATE)
        assert match is not None, anchor
        assert match.group(1).strip() == p.FRONT_DESK_COPY[key]["zh"], anchor


def test_the_client_module_stays_outside_the_hall_copy_block() -> None:
    """The block the copy test polices is for labels only; the casebook is not a label."""

    hall = SCRIPT.index(
        "/* ------------------------------------------------------------- hall copy */"
    )
    assert SCRIPT.index("function initCasebook") < hall


def test_the_language_toggle_rerenders_the_casebook_copy() -> None:
    assert SCRIPT.count("renderCasebookCopy();") >= 2  # the init path and the toggle path
