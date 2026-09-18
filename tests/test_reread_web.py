"""M4C: the web layer's contract for the reread - explicit, per case file, and labelled.

No browser is needed here: the script's shape and the copy are pinned. The behaviour is driven for
real in ``_rc/pr6m4c/browser_reread.py`` against a live server.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from ned.app.main import create_app
from ned.app.ui import personality as p

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "ned" / "app" / "static" / "app.js").read_text(encoding="utf-8")
STYLE = (ROOT / "ned" / "app" / "static" / "style.css").read_text(encoding="utf-8")


def casebook_module() -> str:
    start = SCRIPT.index(
        "/* -------------------------------------------------------------- casebook */"
    )
    end = SCRIPT.index(
        "/* ------------------------------------------------------------- hall copy */"
    )
    return SCRIPT[start:end]


def reread_module() -> str:
    module = casebook_module()
    return module[
        module.index(
            "/* ------------------------------------------------------------- the reread */"
        ) :
    ]


def test_the_client_asks_for_a_reread_exactly_once_and_only_from_the_button() -> None:
    module = casebook_module()
    # one URL builder, one click handler, and one call site plus one definition
    assert module.count('+ "/reread"') == 1
    builder = module[module.index("function rereadUrl") :]
    builder = builder[: builder.index("function runReread")]
    assert '"/reread"' in builder
    assert "rereadButton.addEventListener" in module
    assert module.count("runReread(") == 2


def test_opening_the_panel_never_runs_a_reread() -> None:
    """The panel loads the recorded history only; reading is a separate, explicit act."""

    module = casebook_module()
    detail = module[module.index("function openDetailIfNeeded") :]
    detail = detail[: detail.index("function renderCasebookList")]
    assert "runReread" not in detail
    listing = module[module.index("function refreshCasebookList") :]
    listing = listing[: listing.index("function openDetailIfNeeded")]
    assert "runReread" not in listing
    status = module[module.index("function loadCasebookStatus") :]
    status = status[: status.index("function refreshCasebookList")]
    assert "runReread" not in status


def test_the_reread_renders_two_columns_and_a_note() -> None:
    module = reread_module()
    assert "casebook_reread_recorded_heading" in module
    assert "casebook_reread_today_heading" in module
    assert "casebook_reread_changed_note" in module
    assert "casebook_reread_same_note" in module
    assert "result.identical === true" in module
    assert 'line.setAttribute("data-difference", txt(row.difference))' in module


def test_the_five_classes_have_copy_and_are_rendered_from_it() -> None:
    module = reread_module()
    for difference in ("same", "changed", "missing", "ambiguous", "new"):
        assert f"casebook_reread_class_{difference}" in module, difference
        assert f"casebook_reread_class_{difference}" in p.FRONT_DESK_COPY, difference


def test_the_copy_says_the_history_is_not_modified() -> None:
    note = p.FRONT_DESK_COPY["casebook_reread_changed_note"]
    assert "历史记录未被修改" in note["zh"]
    assert "was not modified" in note["en"]
    same = p.FRONT_DESK_COPY["casebook_reread_same_note"]
    assert "未发现差异" in same["zh"]


def test_the_reread_copy_is_complete_in_both_languages() -> None:
    keys = [key for key in p.FRONT_DESK_COPY if key.startswith("casebook_reread_")]
    assert len(keys) >= 18
    for key in keys:
        values = p.FRONT_DESK_COPY[key]
        assert set(values) == {"zh", "en"}, key
        assert values["zh"].strip() and values["en"].strip(), key
        assert values["zh"] != values["en"], key


def test_the_reread_carries_no_score_vocabulary() -> None:
    module = reread_module().lower()
    for forbidden in ("percent", "score", "trend", "average", "weight"):
        assert forbidden not in module, forbidden


def test_the_reread_block_is_styled_without_a_new_colour() -> None:
    assert ".casebook-reread" in STYLE
    assert ".casebook-reread-columns" in STYLE
    block = STYLE[STYLE.index("front desk: PR-6M4C") :]
    assert "var(--line)" in block and "var(--text)" in block
    assert "#" not in block, "no literal colour enters the desk"


def test_the_client_keeps_no_hidden_persistence_for_the_reread() -> None:
    module = casebook_module()
    assert "localStorage" not in module
    assert "sessionStorage" not in module


def test_the_reread_action_carries_its_label_from_the_catalogue() -> None:
    module = casebook_module()
    assert 'casebookCopy("casebook_reread_action")' in module
    assert p.FRONT_DESK_COPY["casebook_reread_action"]["zh"] == "用当前版本重读"


def test_the_served_page_is_unchanged_by_this_feature() -> None:
    """The reread is built per case file by the script: the static page needs no new element."""

    with TestClient(create_app()) as client:
        page = client.get("/").text
    assert "casebook-reread" not in page
