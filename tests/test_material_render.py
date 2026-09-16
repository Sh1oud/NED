"""PHASE 3.5B-3B: the CLI material registry — registered, and nothing more.

The material layer already knows what an input reports. This card is where a reader
first sees it, so the card has exactly one job: say that the reported statement was
registered, and say that registering it decided nothing else. A material is not
evidence and not a verdict, and the card may not imply either.

Two lines hold this together. The card is driven by ``AnalysisResult.materials``
only - never by ``material_aspects``, which is a different display object with a
different source - and it is withheld entirely under a stated boundary, because one
input can carry both a reported attitude and a plainly stated boundary, and the
boundary outranks any material presentation.
"""

from __future__ import annotations

import inspect
import io
import json

import pytest
from fastapi.testclient import TestClient
from ned.app.cli import app, render_aspect_breakdown, render_material_registry, screen_context
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.rules import RuleBook
from ned.app.main import app as api_app
from ned.app.ui import personality as p
from rich.console import Console
from typer.testing import CliRunner

ANALYZER = NedAnalyzer(book=RuleBook.load())
runner = CliRunner()

FLAGSHIP = "她说她讨厌我"
BOUNDARY_COLLISION = "她跟我说她讨厌我，但她说我们还是做朋友吧。"

#: The 3A collisions, verbatim: 4 material shapes x 3 boundary shapes x 2 joiners.
COLLISION_MATERIALS = (
    "她跟我说她讨厌我",
    "她说她讨厌我",
    "她告诉我她很烦我",
    "她跟我抱怨她讨厌我",
)
COLLISION_BOUNDARIES = (
    "她说我们还是做朋友吧",
    "她说别再联系我",
    "她让我保持距离",
)
COLLISION_CASES = tuple(
    f"{material}{joiner}{boundary}。"
    for material in COLLISION_MATERIALS
    for boundary in COLLISION_BOUNDARIES
    for joiner in ("，", "。")
)

#: The card may never say any of these. Truth claims, verdict claims, aggregate
#: vocabulary and comfort - the whole existing forbidden-copy contract, applied to
#: the new surface so it is not an ungated region of copy.
FORBIDDEN_COPY = (
    # the order's list
    "证据显示",
    "已经确认",
    "事实是",
    "负面证据成立",
    "已验证",
    "可信度高",
    "她确实讨厌你",
    "关系结论：负面",
    "坏消息",
    "关系负面",
    "负面结论",
    "对方态度已确认",
    "更可信",
    "score",
    "probability",
    "加权",
    "综合来看",
    "总体上",
    "mixed signal",
    "五五开",
    "一半一半",
    "正面赢",
    "负面赢",
    # the contracts the existing cards already obey
    "综合来看",
    "总体态度分",
    "总体分数",
    "也许",
    "未必",
    "还有可能",
    "至少她",
    "继续观察",
    "还有戏",
    "别想太多",
    "也许她只是忙",
    "她还是在乎你的",
    "会好的",
    "说明她",
    "相信自己",
)

#: Words that must never appear in the card at all (technical surface).
TECHNICAL_MARKERS = (
    "material_id",
    "origin_rule_id",
    "epistemic_status",
    "mat_",
    "start=",
    "end=",
    "zh.material.",
)


def cli_output(text: str) -> str:
    result = runner.invoke(app, ["analyze", text])
    assert result.exit_code == 0, result.output
    return result.stdout


def card_of(text: str) -> str:
    """The registry card's own text, rendered in isolation. Empty when withheld."""

    result = ANALYZER.analyze_text(text, mode="normal")
    situation, _basis, _language = screen_context(result)
    console = Console(record=True, width=120, file=io.StringIO())
    render_material_registry(result, situation, console)
    return console.export_text()


def aspect_card_of(text: str) -> str:
    result = ANALYZER.analyze_text(text, mode="normal")
    situation, _basis, _language = screen_context(result)
    console = Console(record=True, width=120, file=io.StringIO())
    render_aspect_breakdown(result, situation, console)
    return console.export_text()


# --------------------------------------------------------------------------- #
# 1. the flagship: a registered material, with no promotion
# --------------------------------------------------------------------------- #


def test_the_flagship_case_shows_a_registered_material() -> None:
    result = ANALYZER.analyze_text(FLAGSHIP, mode="normal")
    assert len(result.materials) == 1
    assert result.evidence == []
    assert result.verdict.code == "ned.no_signal"

    output = cli_output(FLAGSHIP)
    assert p.MATERIAL_REGISTRY_COPY["zh"]["card_title"] in output
    assert "她讨厌我" in output
    assert p.MATERIAL_SOURCE_LABELS["zh"]["attributed_report"] in output
    assert p.material_registry_copy("zh")["disclaimer"] in output
    assert p.material_registry_copy("zh")["conclusion_isolation"] in output


def test_the_card_is_driven_only_by_the_registry() -> None:
    """No evidence means no material page, even though the card has content."""

    result = ANALYZER.analyze_text(FLAGSHIP, mode="normal")
    assert result.material_aspects is None
    assert card_of(FLAGSHIP)


def test_the_card_copy_comes_from_the_shared_catalogue() -> None:
    """One copy source: the CLI and any future web page read the same strings."""

    catalog = p.web_personality_catalog()
    assert catalog["material_registry_copy"]["zh"] == p.material_registry_copy("zh")
    assert catalog["material_registry_copy"]["en"] == p.material_registry_copy("en")
    assert catalog["material_source_labels"] == p.MATERIAL_SOURCE_LABELS


def test_the_restraint_line_is_the_existing_one_not_a_second_copy() -> None:
    for key in ("zh", "en"):
        assert p.material_registry_copy(key)["disclaimer"] == p.ASPECT_COPY[key]["disclaimer"]


# --------------------------------------------------------------------------- #
# 2. no material, no noise
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", ("我觉得她讨厌我", "她主动找我聊天了", "今天天气不错"))
def test_a_material_less_input_gets_no_card_and_no_noise(text: str) -> None:
    assert ANALYZER.analyze_text(text, mode="normal").materials == []
    assert card_of(text) == ""
    output = cli_output(text)
    for noise in ("未发现材料", "暂无材料", "0 项附件", "没有材料"):
        assert noise not in output, noise


# --------------------------------------------------------------------------- #
# 3. negative polarity is a content direction, never a verdict
# --------------------------------------------------------------------------- #


def test_negative_material_is_not_a_negative_verdict() -> None:
    card = card_of(FLAGSHIP)
    assert card
    for word in ("坏消息", "关系负面", "负面结论", "已确认", "对方态度已确认"):
        assert word not in card, word
    assert ANALYZER.analyze_text(FLAGSHIP, mode="normal").verdict.code == "ned.no_signal"


def test_the_card_does_not_print_polarity() -> None:
    card = card_of(FLAGSHIP)
    for word in ("polarity", "negative", "负向"):
        assert word not in card, word


# --------------------------------------------------------------------------- #
# 4. source_kind is provenance, never truth
# --------------------------------------------------------------------------- #


def test_source_kind_says_where_the_words_came_from() -> None:
    card = card_of(FLAGSHIP)
    assert p.MATERIAL_SOURCE_LABELS["zh"]["attributed_report"] in card
    for word in ("verified", "已确认", "事实是", "attributed_report"):
        assert word not in card, word
    # the only sentence about verification says the opposite of a truth claim
    assert "不是本机构核实过的事实" in card


def test_direct_user_statement_is_not_a_verified_fact() -> None:
    assert p.MATERIAL_SOURCE_LABELS["zh"]["direct_user_statement"] == "用户直接陈述"
    label = p.MATERIAL_SOURCE_LABELS["zh"]["direct_user_statement"]
    for word in ("已确认", "事实", "verified"):
        assert word not in label, word


# --------------------------------------------------------------------------- #
# 5/6. explicit boundary outranks the material card
# --------------------------------------------------------------------------- #


def test_the_boundary_collision_registers_material_but_shows_no_card() -> None:
    result = ANALYZER.analyze_text(BOUNDARY_COLLISION, mode="normal")
    assert result.materials, "the material half is registered"
    assert result.verdict.code == "ned.direct_rejection"

    assert card_of(BOUNDARY_COLLISION) == ""
    output = cli_output(BOUNDARY_COLLISION)
    assert "EXPLICIT BOUNDARY" in output
    for forbidden in (
        p.MATERIAL_REGISTRY_COPY["zh"]["card_title"],
        "材料已登记",
        "材料已收悉",
        "👍",
        "🤠",
    ):
        assert forbidden not in output, forbidden


@pytest.mark.parametrize("text", COLLISION_CASES)
def test_every_boundary_collision_is_suppressed(text: str) -> None:
    result = ANALYZER.analyze_text(text, mode="normal")
    situation, _basis, _language = screen_context(result)
    assert situation in p.BOUNDARY_SITUATIONS, text
    assert result.materials, f"{text} should still register the material"
    assert card_of(text) == "", text


def test_all_twenty_four_collisions_still_register_material() -> None:
    """The gate is only meaningful because the material really is there."""

    assert len(COLLISION_CASES) == 24
    assert all(ANALYZER.analyze_text(text, mode="normal").materials for text in COLLISION_CASES)


# --------------------------------------------------------------------------- #
# 7. the registry and the filing card stay separate objects
# --------------------------------------------------------------------------- #


def test_the_row_builder_takes_no_aspects() -> None:
    signature = inspect.signature(p.material_registry_rows)
    assert list(signature.parameters) == ["materials", "language"]


def test_the_two_cards_never_absorb_each_other() -> None:
    aspect_result = ANALYZER.analyze_text("她夸我可爱，但她三天没回我消息。", mode="normal")
    assert aspect_result.material_aspects is not None
    pages = [item.text for item in aspect_result.material_aspects.materials]
    assert pages

    registry_result = ANALYZER.analyze_text(FLAGSHIP, mode="normal")
    assert registry_result.materials

    # A hybrid carrying both layers must still render them through their own paths,
    # each under the situation that card belongs to.
    hybrid = registry_result.model_copy(update={"material_aspects": aspect_result.material_aspects})
    registry_situation, _basis, _language = screen_context(hybrid)
    registry_console = Console(record=True, width=120, file=io.StringIO())
    render_material_registry(hybrid, registry_situation, registry_console)
    registry_text = registry_console.export_text()
    aspect_console = Console(record=True, width=120, file=io.StringIO())
    render_aspect_breakdown(hybrid, p.SITUATION_MULTIPLE_ASPECTS, aspect_console)
    aspect_text = aspect_console.export_text()

    assert "她讨厌我" in registry_text
    for page in pages:
        assert page not in registry_text, page
    assert aspect_text
    for page in pages:
        assert page in aspect_text, page
    assert "她讨厌我" not in aspect_text


def test_aspects_alone_do_not_produce_a_registry_card() -> None:
    assert card_of("她夸我可爱，但她三天没回我消息。") == ""
    assert aspect_card_of("她夸我可爱，但她三天没回我消息。")


# --------------------------------------------------------------------------- #
# 8. technical fields stay out of the default card
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", (FLAGSHIP, "她跟我说她讨厌我", "她告诉我她很烦我"))
def test_the_default_card_hides_the_technical_surface(text: str) -> None:
    card = card_of(text)
    assert card
    for marker in TECHNICAL_MARKERS:
        assert marker not in card, marker
    for token in ("reported", "attributed_report"):
        assert token not in card, token


# --------------------------------------------------------------------------- #
# 9. the payload does not move
# --------------------------------------------------------------------------- #


def test_the_json_report_is_the_engine_payload_untouched() -> None:
    result = runner.invoke(app, ["analyze", FLAGSHIP, "--json"])
    payload = json.loads(result.stdout)
    expected = ANALYZER.analyze_text(FLAGSHIP, mode="normal").model_dump(mode="json")
    assert payload.keys() == expected.keys()
    assert payload["materials"] == expected["materials"]
    assert payload["evidence"] == expected["evidence"]
    assert payload["verdict"] == expected["verdict"]


def test_the_api_payload_is_unchanged() -> None:
    with TestClient(api_app) as client:
        response = client.post("/api/analyze", json={"text": FLAGSHIP, "mode": "normal"})
    assert response.status_code == 200
    payload = response.json()
    assert "materials" in payload
    assert len(payload["materials"]) == 1
    assert payload["verdict"]["code"] == "ned.no_signal"
    assert payload["evidence"] == []

    with TestClient(api_app) as client:
        quiet = client.post("/api/analyze", json={"text": "我觉得她讨厌我", "mode": "normal"})
    assert "materials" not in quiet.json()


def test_rendering_does_not_mutate_the_result() -> None:
    result = ANALYZER.analyze_text(FLAGSHIP, mode="normal")
    before = result.model_dump(mode="json")
    situation, _basis, _language = screen_context(result)
    console = Console(record=True, width=120, file=io.StringIO())
    render_material_registry(result, situation, console)
    assert result.model_dump(mode="json") == before


# --------------------------------------------------------------------------- #
# 10. forbidden copy
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", (FLAGSHIP, "她说讨厌我", "她跟我说她讨厌我"))
def test_the_card_carries_no_forbidden_copy(text: str) -> None:
    card = card_of(text)
    assert card
    for word in FORBIDDEN_COPY:
        assert word not in card, (text, word)


def test_the_card_does_not_use_the_no_signal_heading() -> None:
    """``MATERIALS RECEIVED`` belongs to the no-signal screen; the card differs."""

    heading = p.MATERIAL_REGISTRY_COPY["zh"]["card_title"]
    assert heading != "MATERIALS RECEIVED"
    for other in ("材料已收悉", "Materials received"):
        assert other not in heading


def test_the_card_names_no_qualification_state() -> None:
    card = card_of(FLAGSHIP)
    for word in (
        "qualification",
        "qualified",
        "unqualified",
        "is_qualified",
        "is_verified",
        "evidence_status",
        "confidence",
        "权重",
    ):
        assert word not in card, word


# --------------------------------------------------------------------------- #
# 11. the old first-screen slot keeps its old job
# --------------------------------------------------------------------------- #


def test_the_first_screen_slot_still_serves_only_multiple_aspects() -> None:
    situation, _basis, language = screen_context(ANALYZER.analyze_text(FLAGSHIP, mode="normal"))
    assert situation != p.SITUATION_MULTIPLE_ASPECTS
    screen = p.first_screen(situation, "normal", language, materials=("她讨厌我",))
    blob = " ".join([screen.title, *screen.lines, screen.reality])
    assert "她讨厌我" not in blob


def test_the_first_screen_slot_still_fills_for_multiple_aspects() -> None:
    text = "她夸我可爱，但她三天没回我消息。"
    result = ANALYZER.analyze_text(text, mode="normal")
    situation, _basis, language = screen_context(result)
    assert situation == p.SITUATION_MULTIPLE_ASPECTS
    assert result.material_aspects is not None
    pages = tuple(item.text for item in result.material_aspects.materials)
    screen = p.first_screen(situation, "normal", language, materials=pages)
    blob = " ".join([screen.title, *screen.lines, screen.reality])
    assert pages[0] in blob
