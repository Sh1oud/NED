"""M3: the web layer's contract for the review - one block, one explicit action, one honest line.

No browser is needed here: the markup, the script's shape and the copy are pinned. The behaviour
is driven for real in ``_rc/pr6m3/browser_review.py`` against a live server.
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

REVIEW_IDS = (
    "review-with-casebook",
    "casebook-reviewbox",
    "casebook-review-picker",
    "casebook-review-occurred",
    "casebook-review-confirm",
    "casebook-review-cancel",
    "casebook-review-status",
    "result-run-mode",
    "casebook-review-block",
    "casebook-review-label",
    "casebook-review-mode",
    "casebook-review-counts",
    "casebook-review-rows",
    "casebook-review-opinion",
    "casebook-review-note",
)

ANCHORED = (
    ("review-with-casebook", "casebook_review_action"),
    ("casebook-review-label", "casebook_review_heading"),
    ("casebook-review-choose", "casebook_review_choose"),
    ("casebook-review-occurred-label", "casebook_review_occurred"),
    ("casebook-review-confirm", "casebook_review_confirm"),
    ("casebook-review-cancel", "casebook_review_cancel"),
    ("casebook-review-note", "casebook_review_note"),
)


@pytest.fixture
def page() -> str:
    with TestClient(create_app()) as client:
        return client.get("/").text


def casebook_module() -> str:
    start = SCRIPT.index(
        "/* -------------------------------------------------------------- casebook */"
    )
    end = SCRIPT.index(
        "/* ------------------------------------------------------------- hall copy */"
    )
    return SCRIPT[start:end]


def test_the_page_carries_every_review_element(page: str) -> None:
    for element_id in REVIEW_IDS:
        assert f'id="{element_id}"' in page, element_id


def test_the_review_block_is_hidden_until_a_review_arrives(page: str) -> None:
    match = re.search(r'<section[^>]*id="casebook-review-block"[^>]*>', page)
    assert match is not None
    assert "hidden" in match.group(0)
    assert 'setHidden("casebook-review-block", false)' in SCRIPT or "block.hidden = false" in SCRIPT


def test_the_review_block_sits_inside_the_review_stage(page: str) -> None:
    """After the review opinion and before the issuance: a sub-block, not a new stage."""

    stage = page.index('id="stage-block-review"')
    issuance = page.index('id="stage-block-issuance"')
    block = page.index('id="casebook-review-block"')
    grid = page.index('class="review-grid"')
    assert stage < grid < block < issuance


def test_the_action_waits_for_an_analysis_and_for_the_server(page: str) -> None:
    match = re.search(r'<button[^>]*id="review-with-casebook"[^>]*>', page)
    assert match is not None
    assert "hidden" in match.group(0)
    module = casebook_module()
    assert "review.hidden = !enabled || !state.analyze" in module
    assert "function openReviewBox()" in module
    assert "function confirmReview()" in module


def test_the_markup_fallback_matches_the_catalogue(page: str) -> None:
    for anchor, key in ANCHORED:
        match = re.search(rf'id="{re.escape(anchor)}"[^>]*>([^<]*)<', page)
        assert match is not None, anchor
        assert match.group(1).strip() == p.FRONT_DESK_COPY[key]["zh"], anchor


def test_the_review_copy_is_complete_in_both_languages() -> None:
    keys = [key for key in p.FRONT_DESK_COPY if key.startswith("casebook_review_")]
    keys += [key for key in p.FRONT_DESK_COPY if key.startswith("casebook_opinion_")]
    assert len(keys) >= 30
    for key in keys:
        values = p.FRONT_DESK_COPY[key]
        assert set(values) == {"zh", "en"}, key
        assert values["zh"].strip() and values["en"].strip(), key
        assert values["zh"] != values["en"], key


def test_every_relation_and_opinion_has_copy_in_both_languages() -> None:
    module = casebook_module()
    for relation in (
        "supports",
        "conflicts",
        "superseded",
        "unrelated",
        "not_comparable",
        "insufficient",
    ):
        assert f"casebook_review_relation_{relation}" in module, relation
        assert f"casebook_review_relation_{relation}" in p.FRONT_DESK_COPY, relation
    for code in (
        "no_history",
        "nothing_comparable",
        "current_case_has_no_direction",
        "boundary_governs",
        "order_unknown",
        "mixed_directions",
        "only_supports",
        "only_conflicts",
    ):
        assert f"casebook_opinion_{code}" in module, code
        assert f"casebook_opinion_{code}" in p.FRONT_DESK_COPY, code


def test_only_the_confirm_handler_posts_a_casebook_to_the_analyzer() -> None:
    """One call site: the reader's explicit click. Nothing selects a casebook on its own."""

    module = casebook_module()
    assert module.count('"/api/analyze"') == 1
    body = module[module.index('postJson("/api/analyze"') :]
    body = body[: body.index("})", body.index(".then"))]
    assert "casebook: selection" in body
    assert "selection = { casebook_id: casebookId }" in module


def test_the_client_never_selects_a_casebook_by_itself() -> None:
    """Nothing in the client remembers a casebook or attaches one to a plain analysis."""

    module = casebook_module()
    # the review selection is built per click and never stored
    assert "state.casebook.selected" not in SCRIPT
    assert "localStorage" not in module
    assert "sessionStorage" not in module
    plain = SCRIPT[SCRIPT.index("function runAnalyze()") :]
    plain = plain[: plain.index("function legacyCopy")]
    assert "casebook" not in plain


def test_the_review_block_renders_from_the_payload_it_came_with() -> None:
    module = casebook_module()
    assert "renderCasebookReviewBlock(d.casebook_review)" in SCRIPT
    assert "function renderCasebookReviewBlock(review)" in module
    # the mode line is set for both kinds of run, so the reader can tell them apart
    assert 'mode.setAttribute("data-run-mode", "joint")' in module
    assert 'mode.setAttribute("data-run-mode", "single")' in module


def test_the_review_block_carries_no_score_vocabulary() -> None:
    module = casebook_module()
    review = module[module.index("function renderCasebookReviewBlock") :]
    for forbidden in ("percent", "score", "percentage", "trend", "average", "weight"):
        assert forbidden not in review.lower(), forbidden


def test_the_review_note_says_it_is_not_a_verdict() -> None:
    note = p.FRONT_DESK_COPY["casebook_review_note"]
    assert "不是新的最终裁决" in note["zh"]
    assert "not a new verdict" in note["en"]


def test_the_language_toggle_rerenders_the_review() -> None:
    """The review is copy, so switching the desk language has to redraw it."""

    init = SCRIPT[SCRIPT.index("function init()") :]
    handler = init[: init.index("var analyzeBtn")]
    assert "renderCasebookCopy()" in handler
    assert "renderAnalyze(state.analyze)" in handler


def test_the_served_page_carries_the_review_markup(page: str) -> None:
    assert 'id="casebook-review-block"' in page
    assert "卷宗联合审查" in page
    assert 'id="result-run-mode"' in page
