"""PR-4R permanent regression: the front desk may not contradict its own payload.

The four samples below are the ones the commander pinned. pytest cannot run a browser, so each
sample is checked in the two layers pytest *can* see:

  * the engine's own answer over the real HTTP API - recognition, material list, evidence list
    and verdict. These values are the truth the page has to present;
  * the shipped presentation contract - which screen the payload's recognition state selects,
    what the stage rail is allowed to say about material, what the stamp says, and whether a
    registered material can be hidden by the situation or the register.

The browser-level confirmation of the same four samples lives in the batch evidence
(``_rc/pr4r``), because the product ships no in-pytest browser suite.

Samples:
  B1  she remembered my birthday, but she says we are only friends
  B2  she says we should stay friends, but she remembered my birthday
  A   a positive verdict with no separate material record
  D   nothing recognised at all
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ned.app.main import app as api_app
from ned.app.ui import personality as p

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = (REPO / "ned/app/templates/index.html").read_text(encoding="utf-8")
SCRIPT = (REPO / "ned/app/static/app.js").read_text(encoding="utf-8")
STYLE = (REPO / "ned/app/static/style.css").read_text(encoding="utf-8")

B1 = "她记得我生日，但她说我们只是朋友"
B2 = "她说“我们还是做朋友吧”，不过她记得我生日"
A = "她说她喜欢我"
D = "今天食堂的饭难吃"

MATERIAL_ONLY = p.SITUATION_MATERIAL_ONLY
NO_SIGNAL = p.SITUATION_NO_SIGNAL


def analyse(text: str) -> dict:
    """The real payload the page receives for one submission."""

    with TestClient(api_app) as client:
        response = client.post("/api/analyze", json={"text": text, "mode": "normal"})
    assert response.status_code == 200, response.text
    return response.json()


def function_body(name: str) -> str:
    """One top-level app.js function, with whole-line comments removed."""

    match = re.search(rf"\n  function {name}\((.*?)\n  \}}\n", SCRIPT, re.DOTALL)
    assert match is not None, f"{name} is missing from app.js"
    body = match.group(0)
    return "\n".join(line for line in body.splitlines() if not line.strip().startswith("//"))


def screen_blob(situation: str, language: str = "zh") -> str:
    screen = p.first_screen(situation, "normal", language)
    return " ".join([screen.title, *screen.lines, screen.reality])


def situations_hiding(needle: str) -> set[str]:
    """Every situation whose CSS block hides ``needle``."""

    hidden: set[str] = set()
    for head, body in re.findall(r"([^{}]*)\{([^{}]*)\}", STYLE):
        if needle in head and "display: none" in body:
            hidden.update(re.findall(r'\[data-situation="([^"]+)"\]', head))
    return hidden


# --------------------------------------------------------------------------- #
# B1 - material on file, no verdict: never the empty screen
# --------------------------------------------------------------------------- #


def test_b1_files_material_and_is_never_shown_as_nothing_recognised() -> None:
    payload = analyse(B1)
    assert payload["recognition"] == "material_registered"
    assert len(payload["materials"]) >= 1
    assert payload["evidence"] == []

    # the page reaches that screen from the payload's recognition state, not from the evidence
    body = function_body("displaySituation")
    assert '"material_registered"' in body, "the screen must be chosen from the recognition state"
    assert '"material_only"' in body
    guard = [
        line
        for line in body.splitlines()
        if '"material_registered"' in line and "material_only" in line
    ]
    assert guard, "the material-only promotion must be a single line"
    assert "evidence" not in guard[0] and "materials" not in guard[0], (
        "the promotion may not be inferred from the evidence list"
    )

    # and the two screens cannot be confused
    assert screen_blob(MATERIAL_ONLY) != screen_blob(NO_SIGNAL)
    assert "已登记" in screen_blob(MATERIAL_ONLY)
    assert p.first_screen(MATERIAL_ONLY, "normal", "zh").title != "NO RECOGNIZED MATERIAL"
    assert p.first_screen(MATERIAL_ONLY, "normal", "en").title != "NO RECOGNIZED MATERIAL"


# --------------------------------------------------------------------------- #
# B2 - a stated boundary never destroys a registered material
# --------------------------------------------------------------------------- #


def test_b2_keeps_its_material_visible_under_a_stated_boundary() -> None:
    payload = analyse(B2)
    assert payload["recognition"] == "adjudicated"
    assert payload["verdict"]["code"] == "ned.direct_rejection"
    assert len(payload["materials"]) == 1

    # the renderer's only hiding condition is the real material list
    body = function_body("renderMaterialRegistry")
    assert "boundary_situations" not in body
    assert "materials.length === 0" in body
    assert body.index("materials.length === 0") < body.index("card.hidden = false")

    # the stage renderer hides the registry for an empty list too, and for nothing else
    stage = function_body("renderMaterialStage")
    assert 'setHidden("material-registry", true)' in stage
    assert stage.index("materials === 0") < stage.index('setHidden("material-registry", true)')

    # no situation rule may suppress the registry - the emblem is a different matter
    assert not situations_hiding("#material-registry")
    assert situations_hiding("#verdict-emoji") == {"boundary", "timeline_boundary"}


# --------------------------------------------------------------------------- #
# A - evidence without a separate material record
# --------------------------------------------------------------------------- #


def test_a_never_claims_that_nothing_was_recognised() -> None:
    payload = analyse(A)
    assert payload["recognition"] == "adjudicated"
    # the engine omits an empty material list from the payload entirely; the page treats the
    # absent key as "no material on file"
    assert "materials" not in payload
    assert len(payload["evidence"]) >= 1

    rail = function_body("renderStageRail")
    # the empty wording belongs to the nothing-recognised branch alone
    assert rail.index('"nothing_recognized"') < rail.index("stage_material_none")
    assert "stage_material_independent_none" in rail
    assert rail.index("stage_material_independent_none") > rail.index("stage_material_none")

    independent = p.FRONT_DESK_COPY["stage_material_independent_none"]
    assert "未识别到" not in independent["zh"]
    assert "not recognise" not in independent["en"]
    note = p.FRONT_DESK_COPY["material_empty_independent_none"]
    assert "未识别到" not in note["zh"]
    assert "证据" in note["zh"]
    assert "evidence" in note["en"]
    # the script restores the shipped sentence for the true empty case, and states the
    # architecture for this one
    stage = function_body("renderMaterialStage")
    assert 'recognition === "nothing_recognized"' in stage
    assert "stage_material_none" not in stage, "stage 02 no longer keys off the empty wording"


# --------------------------------------------------------------------------- #
# D - nothing recognised keeps the empty wording
# --------------------------------------------------------------------------- #


def test_d_keeps_the_empty_wording_for_a_true_nothing_recognised() -> None:
    payload = analyse(D)
    assert payload["recognition"] == "nothing_recognized"
    assert "materials" not in payload
    assert payload["evidence"] == []

    assert p.FRONT_DESK_COPY["stage_material_none"]["zh"] == "未识别到材料"
    assert p.first_screen(NO_SIGNAL, "normal", "zh").title == "NO RECOGNIZED MATERIAL"
    assert "没有识别到可登记的材料" in screen_blob(NO_SIGNAL)
    # the shipped empty-state sentence stays in the served markup
    assert "本版未识别到可登记材料" in TEMPLATE
    assert 'id="material-empty"' in TEMPLATE


# --------------------------------------------------------------------------- #
# C and D differ on every surface the reader uses
# --------------------------------------------------------------------------- #


def test_the_two_unsigned_states_differ_on_screen_rail_and_stamp() -> None:
    copy = p.FRONT_DESK_COPY
    # titles and bodies
    assert screen_blob(MATERIAL_ONLY) != screen_blob(NO_SIGNAL)
    # stage 02 and stage 04
    assert copy["stage_material_count"]["zh"] != copy["stage_material_none"]["zh"]
    assert copy["stage_issuance_material"]["zh"] != copy["stage_issuance_none"]["zh"]
    assert copy["review_relation_material_only"]["zh"] != copy["review_relation_none"]["zh"]
    # the stamp itself
    assert copy["stamp_material_pending"]["zh"] != copy["stamp_unsigned"]["zh"]
    assert copy["stamp_material_pending"]["en"] != copy["stamp_unsigned"]["en"]
    assert "材料" in copy["stamp_material_pending"]["zh"]
    assert "material" in copy["stamp_material_pending"]["en"].lower()


def test_the_stamp_states_the_recognition_state_from_the_catalogue() -> None:
    strip = function_body("renderIssuanceStrip")
    for key in ("stamp_boundary", "stamp_signed", "stamp_material_pending", "stamp_unsigned"):
        assert key in strip, key
        assert key in p.FRONT_DESK_COPY, key
    assert "deskCopy(stampKey)" in strip
    # no Chinese stamp literal survives in the script
    assert "\\u5df2\\u7b7e" not in strip
    assert "\\u8fb9\\u754c" not in strip


def test_the_strip_and_the_opinion_quote_one_sentence() -> None:
    """PR-4S: the sentence is computed once and printed by both surfaces.

    PR-3's strip printed the raw payload sentence while the review screen printed the
    display-repaired one, so one page could claim both "你又开始了" and "本机构决定继续怀疑",
    or show an unrepaired "—未回复" next to the repaired sentence.
    """

    strip = function_body("renderIssuanceStrip")
    assert "shownVerdict" in strip, "the strip must take the sentence it prints"
    assert "verdict.text" not in strip, "the strip may not read the payload sentence itself"
    assert "renderIssuanceStrip(d, situation, recognition, shownVerdict);" in SCRIPT

    body = function_body("renderAnalyze")
    assert "var shownVerdict = repairDisplayText(" in body
    assert "displayVerdictText(v.code, v.text, situation, basis, language)" in body
    assert body.index("var shownVerdict") < body.index("renderIssuanceStrip(d, situation"), (
        "the sentence must exist before the strip is rendered"
    )


@pytest.mark.parametrize(
    "text",
    ["她发了个爱心表情，但她三天没回我。", "他今天一整天都没回我消息"],
)
def test_the_display_layer_is_still_needed_for_the_raw_sentence(text: str) -> None:
    """The two hazards this contract exists for, measured on the live payload."""

    payload = analyse(text)
    code = payload["verdict"]["code"]
    raw = payload["verdict"]["text"]
    assert code in {"nea.you_started_again", "nea.latency_insufficient"}, code
    if code == "nea.you_started_again":
        # the false second-person claim: only true when the reader stated their own conclusion
        assert "你又开始了" in raw
        assert "without_basis" in p.VERDICT_DISPLAY_OVERRIDES[code]
    else:
        # the unrepaired duration artifact
        assert "—未回复" in raw


def test_the_material_only_screen_is_complete_and_agrees_with_the_cli() -> None:
    """No raw slot, and no no-signal wording on a screen with material on file."""

    payload = analyse(B1)
    situation = p.SITUATION_MATERIAL_ONLY
    screen = p.first_screen(
        situation,
        "normal",
        "zh",
        materials=tuple(item["reported_content"] for item in payload["materials"]),
    )
    assert "{materials}" not in " ".join(screen.lines)
    assert "已登记" in " ".join(screen.lines)
    # the client fills the same slot for the same screen
    assert 'situation === "material_only"' in SCRIPT
    assert "fillMaterials" in SCRIPT
    # the fact row states the count instead of claiming nothing was heard
    fact = p.FRONT_DESK_COPY["fact_material_only"]
    assert "{n}" in fact["zh"] and "{n}" in fact["en"]
    assert "没有检测到" not in fact["zh"]
    assert "no classifiable" not in fact["en"]
    body = function_body("screenFact")
    assert 'deskCopy("fact_material_only")' in body
    assert body.index('situation === "material_only"') < body.index("fact_fixed")


def test_the_stage_leads_follow_the_interface_language() -> None:
    chrome = function_body("renderStageChrome")
    for key in ("material_lead", "review_lead", "issuance_lead", "stage_name_material"):
        assert key in chrome, key
        assert key in p.FRONT_DESK_COPY, key
    for anchor in ('"material-lead"', '"review-lead"', '"issuance-lead"'):
        assert anchor in chrome, anchor
    # the leads left the template's own language and are looked up now
    for lead in ("本机构到底听到了什么", "本机构这次究竟签没签"):
        assert lead in TEMPLATE


# --------------------------------------------------------------------------- #
# the way back to the counter
# --------------------------------------------------------------------------- #


def test_the_result_offers_one_step_back_to_the_counter() -> None:
    assert 'id="submit-another"' in TEMPLATE
    assert "submit_another" in p.FRONT_DESK_COPY
    assert "submit_another" in function_body("renderStageChrome")
    handler_start = SCRIPT.index('var anotherBtn = $("submit-another");')
    handler = SCRIPT[handler_start : SCRIPT.index("\n    }\n", handler_start)]
    assert "scrollIntoView" in handler
    assert "analyze-input" in handler
    assert ".value" not in handler, "the way back never clears what the reader submitted"
    assert "postJson" not in handler, "the way back asks the engine for nothing"


def test_the_first_screen_keeps_the_counter_action_reachable_on_a_phone() -> None:
    block = STYLE[
        STYLE.index("/* ------------------------------------- front desk: first screen") :
    ]
    assert "@media (max-width: 520px)" in block
    # the action is placed directly under the material field on a narrow screen
    assert ".row-inline .field-actions" in block
    assert "order: -1" in block
    # and nothing is pinned to the viewport, so no control can cover the input or the result
    assert "position: fixed" not in block
    assert "position: sticky" not in block
    assert "min-height: 48px" in block


@pytest.mark.parametrize("text", [B1, B2, A, D])
def test_every_sample_keeps_a_machine_readable_recognition_state(text: str) -> None:
    payload = analyse(text)
    assert payload["recognition"] in {
        "adjudicated",
        "material_registered",
        "nothing_recognized",
    }
    assert isinstance(payload.get("materials", []), list)
    assert isinstance(payload["evidence"], list)
    # the page's own state attribute is written from the payload, never sniffed from the DOM
    assert "txt(d.recognition)" in SCRIPT
    assert 'getAttribute("data-recognition")' not in SCRIPT
