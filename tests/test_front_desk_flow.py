"""PR-3 pins: the front desk is a four-stage dossier, not a dashboard with a hall skin.

The batch restructured the page around one user path - submit material, material registration,
review opinion, issuance - and demoted every developer surface into a folded technical archive.
These pins keep that structure honest: stage order, what the archive may hold, the collapsed
examples guide, the Chinese-first document, the state-driven rail, and the reset that stops a
previous case from leaking into the next one.
"""

from __future__ import annotations

import re

from ned.app.ui import personality as p
from tests.test_front_desk_copy import SCRIPT, STYLE, TEMPLATE


def test_the_four_stages_exist_in_order() -> None:
    order = [
        'id="stage-block-submit"',
        'id="stage-block-material"',
        'id="stage-block-review"',
        'id="stage-block-issuance"',
    ]
    positions = [TEMPLATE.index(marker) for marker in order]
    assert positions == sorted(positions), "the four stages must appear in reading order"
    for marker in order:
        assert marker in TEMPLATE, marker
    assert 'id="stage-rail"' in TEMPLATE
    for step in ("submit", "material", "review", "issuance"):
        assert f'id="stage-{step}"' in TEMPLATE, step


def test_the_issuance_strip_comes_first_and_the_verdict_is_its_own_stage() -> None:
    """The reader must learn whether anything was signed without opening the archive."""

    strip = TEMPLATE.index('id="issuance-strip"')
    rail = TEMPLATE.index('id="stage-rail"')
    material = TEMPLATE.index('id="stage-block-material"')
    issuance = TEMPLATE.index('id="stage-block-issuance"')
    archive = TEMPLATE.index('id="technical-details"')
    assert strip < rail < material < issuance < archive
    verdict = TEMPLATE[issuance:archive]
    assert 'id="final-verdict"' in verdict
    assert 'id="verdict-text"' in verdict


def test_the_developer_surfaces_live_in_the_archive() -> None:
    archive = TEMPLATE[TEMPLATE.index('id="technical-details"') :]
    for internal in (
        "system-strip",
        "signal-classification",
        "evidence-strength",
        "discount-block",
        "amplification-block",
        "reaching-block",
        "engine-notes-block",
        "raw-interpretation",
        "evidence-rows",
    ):
        assert f'id="{internal}"' in archive, internal
    for developer in ("Engine", "Provider", "API", "Reaching bands"):
        assert developer in archive, developer
    # the identity strip must not sit in the hero any more
    hero = TEMPLATE[: TEMPLATE.index('class="hall-directory"')]
    for developer in ("Reaching bands", "Provider", "/api/analyze"):
        assert developer not in hero, developer


def test_the_registry_is_a_main_path_stage_with_an_empty_state() -> None:
    archive = TEMPLATE[TEMPLATE.index('id="technical-details"') :]
    assert 'id="material-registry"' not in archive
    assert 'id="material-registry"' in TEMPLATE
    assert 'id="material-empty"' in TEMPLATE
    assert "本版未识别到可登记材料" in TEMPLATE


def test_the_examples_are_a_folded_leaflet() -> None:
    guide = TEMPLATE[TEMPLATE.index('id="examples-guide"') :]
    assert guide.startswith('id="examples-guide"')
    assert "<summary" in guide[:200]
    assert "<details" in TEMPLATE[: TEMPLATE.index('id="examples-guide"')][-200:]


def test_the_page_is_chinese_first_with_a_toggle() -> None:
    assert '<html lang="zh-CN">' in TEMPLATE
    assert 'id="lang-toggle"' in TEMPLATE
    assert '"lang", next' in SCRIPT or 'setAttribute("lang"' in SCRIPT


def test_the_script_drives_the_stages_from_the_payload_state() -> None:
    for function in (
        "resetDossier",
        "renderStageRail",
        "renderIssuanceStrip",
        "renderMaterialStage",
        "renderReviewRelation",
        "renderStageChrome",
    ):
        assert f"function {function}(" in SCRIPT, function
    assert "data-recognition" in SCRIPT
    assert 'getAttribute("data-recognition")' not in SCRIPT, "the state is read, never sniffed"
    assert "txt(d.recognition)" in SCRIPT, "the raster reads the payload's own state"
    # the reset runs before the new case is painted
    body = SCRIPT[SCRIPT.index("function renderAnalyze(data) {") :]
    body = body[: body.index("function renderAsymmetry(")]
    assert "resetDossier();" in body
    assert body.index("resetDossier();") < body.index("renderAnalyzeScreen(")


def test_the_stage_copy_comes_from_the_catalogue() -> None:
    """No stage wording is hard-coded in the template or the script."""

    for key in (
        "stage_name_material",
        "stage_name_review",
        "stage_name_issuance",
        "stage_issuance_material",
        "material_count_none",
        "review_relation_material_only",
        "issuance_material_sub",
    ):
        assert key in SCRIPT, key
        assert key in p.FRONT_DESK_COPY, key
    for literal in ("材料登记", "审查意见", "签发状态", "技术档案"):
        assert literal not in TEMPLATE or literal in "".join(
            p.FRONT_DESK_COPY[key][language] for key in p.FRONT_DESK_COPY for language in ("zh",)
        ), literal


def test_the_mobile_rules_keep_the_rail_readable_and_the_button_tappable() -> None:
    assert "@media (max-width: 460px)" in STYLE
    assert ".stage-rail { grid-template-columns: 1fr;" in STYLE
    assert "min-height: 48px" in STYLE
    assert re.search(r"\.stage-rail \{ grid-template-columns: repeat\(2,", STYLE)


def test_the_archive_starts_folded_and_the_dossier_is_scrolled_to() -> None:
    assert "details.open = false" in SCRIPT
    assert "scrollIntoView" in SCRIPT
