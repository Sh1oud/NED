"""Stage 2: Multiple Aspects.

What this file defends, in the order the Mission Contract lists it:

* an input that reports more than one material page gets a screen that files
  them, instead of a screen that answers with one of them;
* every page keeps its own grade: nothing is averaged, added, ranked or scored;
* a stated boundary keeps its screen word for word, and the second page never
  becomes an appeal against it;
* hostile input gets no combined view at all;
* the reader's own conclusion is never overruled by material the engine found.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from ned.app.cli import render_aspect_breakdown, render_first_screen, screen_context
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.aspects import POSITIVE_PAGE_MIN_STRENGTH, page_fragment
from ned.app.ui import personality as p
from rich.console import Console

RULES = Path(__file__).resolve().parent.parent / "ned" / "app" / "rules" / "signals.json"

#: The four accepted golden cases, and nothing beyond them.
GOLDEN_MULTIPLE = "她夸我可爱，但她三天没回我消息。"
GOLDEN_BOUNDARY = (
    "她记得我爱吃什么，但她说我们还是做朋友吧。",
    "他给我点了一杯奶茶，但他说我们不合适。",
    "他约我周末看电影，后来又说我们保持距离吧。",
)

#: Screens that must not be promoted, with the reason they must not be.
BOUNDARY = (
    "她说我们还是做朋友吧",
    "他说我们还是保持距离吧",
    "他说我很好 但我们不合适",
)
HOSTILE = ("她说你他妈有病吧，但我给她点了奶茶。", "她骂了我，但我想也许只是人好")
READER_CONCLUSION = (
    "她主动找我聊了两个小时，但五分钟没回复，她肯定不想理我。",
    "她夸我可爱，但她三天没回我，她肯定不想理我。",
    "她夸我可爱，但她三天没回我，我觉得她不喜欢我。",
)
STAGE1_AUDIT = "她说喜欢我，但三天没回我，可能只是礼貌。"
SELF_WORTH = "她说喜欢我，但我根本不值得被喜欢"
SINGLE_SIDED = ("她三天没回我消息。", "她夸我可爱", "她回了我一个嗯。", "今天天气不错。")
BELOW_FLOOR = "她发了个爱心表情，但她三天没回我。"

#: Wording that would mean NED judged the pages together. The refusal row is
#: allowed to name the arithmetic it did not do; nothing else is.
FORBIDDEN_VOCABULARY = (
    "五五开",
    "各占一半",
    "一半一半",
    "综合来看",
    "总体上",
    "总体态度分",
    "总体分数",
    "加权",
    "更可信",
    "正面赢",
    "负面赢",
    "mixed signal",
    "probability",
    "score",
)

#: The one row allowed to name arithmetic, and the only words it may use.
REFUSAL_WORDS = ("相加", "平均", "排名", "总分", "概率")

#: Wording that would soften a stated boundary or hand out comfort.
BOUNDARY_FORBIDDEN = ("也许", "未必", "还有可能", "至少", "继续观察", "还有戏")
COMFORT = (
    "至少她",
    "别想太多",
    "也许她只是忙",
    "她还是在乎你的",
    "会好的",
    "说明她",
    "相信自己",
)


@pytest.fixture(scope="module")
def analyzer() -> NedAnalyzer:
    return NedAnalyzer()


@pytest.fixture(scope="module")
def rules() -> dict[str, dict[str, object]]:
    pack = json.loads(RULES.read_text(encoding="utf-8"))
    return {rule["id"]: rule for rule in pack["signals"]}


def analyse(analyzer: NedAnalyzer, text: str) -> Any:
    return analyzer.analyze_text(text, mode="normal")


def situation_of(analyzer: NedAnalyzer, text: str) -> str:
    return screen_context(analyse(analyzer, text))[0]


def capture(render: Callable[[Console], None]) -> str:
    """What the CLI would print for one render call."""

    out = Console(width=100, force_terminal=False, highlight=False)
    with out.capture() as recording:
        render(out)
    return recording.get()


def first_screen_text(analyzer: NedAnalyzer, text: str) -> str:
    result = analyse(analyzer, text)
    situation, basis, language = screen_context(result)
    return capture(lambda out: render_first_screen(result, situation, basis, language, out))


def card_text(analyzer: NedAnalyzer, text: str) -> str:
    result = analyse(analyzer, text)
    situation = screen_context(result)[0]
    return capture(lambda out: render_aspect_breakdown(result, situation, out))


def rows_language(analyzer: NedAnalyzer, text: str) -> str:
    return "en" if analyse(analyzer, text).language == "en" else "zh"


def rows_of(analyzer: NedAnalyzer, text: str) -> dict[str, str]:
    result = analyse(analyzer, text)
    aspects = result.material_aspects
    assert aspects is not None
    situation = screen_context(result)[0]
    return dict(
        p.aspect_breakdown_rows(
            aspects, result.evidence, situation=situation, language=result.language
        )
    )


# --------------------------------------------------------------------------- #
# 1. the four golden cases
# --------------------------------------------------------------------------- #


def test_the_flagship_input_gets_the_filing_screen(analyzer: NedAnalyzer) -> None:
    assert situation_of(analyzer, GOLDEN_MULTIPLE) == p.SITUATION_MULTIPLE_ASPECTS
    screen = first_screen_text(analyzer, GOLDEN_MULTIPLE)
    assert "MULTIPLE ASPECTS DETECTED" in screen
    assert "已分别入档" in screen
    assert "本机构拒绝把它们相加" in screen


def test_the_flagship_screen_names_both_pages_verbatim(analyzer: NedAnalyzer) -> None:
    screen = first_screen_text(analyzer, GOLDEN_MULTIPLE)
    assert "「夸我可爱」" in screen
    assert "「她三天没回我消息」" in screen


def test_the_flagship_screen_prints_no_quality(analyzer: NedAnalyzer) -> None:
    """No scoreboard: the screen shows no grade for either page, or for a total."""

    assert "Evidence quality" not in first_screen_text(analyzer, GOLDEN_MULTIPLE)


@pytest.mark.parametrize("text", GOLDEN_BOUNDARY)
def test_a_stated_boundary_keeps_its_screen(analyzer: NedAnalyzer, text: str) -> None:
    assert situation_of(analyzer, text) == p.SITUATION_BOUNDARY
    assert "EXPLICIT BOUNDARY 🚧" in first_screen_text(analyzer, text)


#: The boundary screen, word for word, exactly as v0.1.7 shipped it. Stage 2 may
#: add a card under it and may not touch a single character of it.
BOUNDARY_SCREEN_LINES = (
    "EXPLICIT BOUNDARY 🚧",
    "明确拒绝 / 边界表达",
    "明确",
    "明确边界。NED 停止狡辩。🚧",
    "不确定性，不等于否认明确证据。",
    "说出口的边界是一个行为，不是推断。NED 不对这条证据降权。",
)


@pytest.mark.parametrize("text", GOLDEN_BOUNDARY)
def test_a_boundary_screen_keeps_its_own_words(analyzer: NedAnalyzer, text: str) -> None:
    """Word for word, page or no page: the boundary screen is not reworded."""

    screen = first_screen_text(analyzer, text)
    for line in BOUNDARY_SCREEN_LINES:
        assert line in screen, (text, line)
    assert "MULTIPLE ASPECTS" not in screen, text
    assert "👍" not in screen, text
    assert "🤠" not in screen, text


@pytest.mark.parametrize("text", GOLDEN_BOUNDARY)
def test_a_boundary_keeps_the_other_page_in_the_card(analyzer: NedAnalyzer, text: str) -> None:
    card = card_text(analyzer, text)
    assert "已入档的另一份材料" in card
    assert "边界" in card
    assert "这份材料不会削弱边界。" in card
    assert "未比较。未合并。未排名。" in card
    assert "已经明确" in card
    assert "输入报告了明确边界" in card


@pytest.mark.parametrize("text", GOLDEN_BOUNDARY)
def test_a_boundary_card_carries_no_joke_and_no_hesitation(
    analyzer: NedAnalyzer, text: str
) -> None:
    card = card_text(analyzer, text)
    for emoji in ("👍", "🤠"):
        assert emoji not in card, (text, emoji)
    for word in BOUNDARY_FORBIDDEN:
        assert word not in card, (text, word)


@pytest.mark.parametrize("text", GOLDEN_BOUNDARY)
def test_a_boundary_card_never_says_the_boundary_is_unknown(
    analyzer: NedAnalyzer, text: str
) -> None:
    card = card_text(analyzer, text)
    assert "边界态度未知" not in card
    assert "总体态度" not in card
    assert "对方未表达的其他心理动机" in card


# --------------------------------------------------------------------------- #
# 2. the two gates: build and promotion
# --------------------------------------------------------------------------- #


def test_the_build_gate_files_two_pages(analyzer: NedAnalyzer) -> None:
    result = analyse(analyzer, GOLDEN_MULTIPLE)
    aspects = result.material_aspects
    assert aspects is not None
    assert len(aspects.materials) >= 2
    assert aspects.relation_assessed is False


def test_the_build_gate_needs_a_positive_page(analyzer: NedAnalyzer) -> None:
    """A one-sided input reports one page, however many spans it has."""

    for text in SINGLE_SIDED:
        assert analyse(analyzer, text).material_aspects is None, text


def test_the_build_gate_refuses_a_trace(analyzer: NedAnalyzer) -> None:
    """Below the 有限 band a positive is a trace, not a page."""

    result = analyse(analyzer, BELOW_FLOOR)
    assert result.material_aspects is None
    assert situation_of(analyzer, BELOW_FLOOR) == p.SITUATION_STARTED_AGAIN


def test_the_build_gate_gives_a_hostile_input_nothing(analyzer: NedAnalyzer) -> None:
    for text in HOSTILE:
        assert analyse(analyzer, text).material_aspects is None, text
        assert card_text(analyzer, text).strip() == "", text


def test_the_promotion_gate_only_promotes_the_amplification_screen(analyzer: NedAnalyzer) -> None:
    """The whitelist is data, and it holds one entry."""

    assert p.MULTIPLE_ASPECTS_PROMOTES == (p.SITUATION_STARTED_AGAIN,)


def test_the_promotion_gate_never_fires_without_data(analyzer: NedAnalyzer) -> None:
    assert p.screen_situation(p.SITUATION_STARTED_AGAIN, aspects=False) == (
        p.SITUATION_STARTED_AGAIN
    )


def test_the_promotion_gate_refuses_a_reader_conclusion() -> None:
    assert (
        p.screen_situation(p.SITUATION_STARTED_AGAIN, aspects=True, reader_conclusion=True)
        == p.SITUATION_STARTED_AGAIN
    )


def test_the_promotion_gate_refuses_the_stage_one_audit() -> None:
    assert p.screen_situation(p.SITUATION_STARTED_AGAIN, aspects=True, audit=True) == (
        p.SITUATION_STARTED_AGAIN
    )


def test_the_promotion_gate_never_fires_on_a_boundary() -> None:
    for base in (p.SITUATION_BOUNDARY, p.SITUATION_TIMELINE_BOUNDARY, p.SITUATION_HOSTILE):
        assert p.screen_situation(base, aspects=True) == base, base


@pytest.mark.parametrize("text", READER_CONCLUSION)
def test_a_reader_conclusion_is_not_overruled(analyzer: NedAnalyzer, text: str) -> None:
    assert situation_of(analyzer, text) == p.SITUATION_STARTED_AGAIN
    assert card_text(analyzer, text).strip() == ""


def test_the_stage_one_audit_keeps_its_own_situation(analyzer: NedAnalyzer) -> None:
    """Stage 1 has priority: the reader's own explanation is the subject there."""

    result = analyse(analyzer, STAGE1_AUDIT)
    assert result.interpretation_audit is not None
    assert result.material_aspects is not None
    assert situation_of(analyzer, STAGE1_AUDIT) == p.SITUATION_STARTED_AGAIN
    assert card_text(analyzer, STAGE1_AUDIT).strip() == ""


def test_a_self_worth_conclusion_gets_no_pages(analyzer: NedAnalyzer) -> None:
    assert analyse(analyzer, SELF_WORTH).material_aspects is None
    assert situation_of(analyzer, SELF_WORTH) != p.SITUATION_MULTIPLE_ASPECTS


@pytest.mark.parametrize("text", HOSTILE)
def test_hostile_input_never_shows_the_card(analyzer: NedAnalyzer, text: str) -> None:
    assert card_text(analyzer, text).strip() == ""


# --------------------------------------------------------------------------- #
# 2b. page fidelity: qualifiers the input reported stay on the page
# --------------------------------------------------------------------------- #

#: The material's own time qualifier is part of the material. Each case is
#: (input, the fragment the page must show).
TIME_QUALIFIER_CASES = (
    ("她夸我可爱，但她三天没回我消息。", "她三天没回我消息"),
    ("她主动找我聊了两个小时，但五分钟没回复", "五分钟没回复"),
    ("她跟我说晚安了，但今天没回我。", "今天没回我"),
    ("他昨天没回我，但今天主动找我聊天了。", "他昨天没回我"),
    ("他今天没回消息，但昨天陪我聊了很久", "他今天没回消息"),
)

#: A one-sided input has no second page, but its own screen must still carry
#: the qualifier the input reported.
SINGLE_SIDED_QUALIFIERS = (("她三天没回我消息。", "3 天"),)


@pytest.mark.parametrize(("text", "expected"), SINGLE_SIDED_QUALIFIERS)
def test_a_single_sided_screen_keeps_its_qualifier(
    analyzer: NedAnalyzer, text: str, expected: str
) -> None:
    assert analyse(analyzer, text).material_aspects is None, text
    assert expected in first_screen_text(analyzer, text), text


@pytest.mark.parametrize(("text", "expected"), TIME_QUALIFIER_CASES)
def test_a_latency_page_keeps_its_time_qualifier(
    analyzer: NedAnalyzer, text: str, expected: str
) -> None:
    """ "没回" without its duration is a different material from "三天没回"."""

    result = analyse(analyzer, text)
    aspects = result.material_aspects
    assert aspects is not None, text
    fragments = [item.text for item in aspects.materials]
    assert expected in fragments, (text, fragments)
    for fragment in fragments:
        assert fragment in text, (text, fragment)


def test_the_flagship_pages_are_the_input_words_in_order(analyzer: NedAnalyzer) -> None:
    result = analyse(analyzer, GOLDEN_MULTIPLE)
    aspects = result.material_aspects
    assert aspects is not None
    assert [item.text for item in aspects.materials] == [
        "夸我可爱",
        "她三天没回我消息",
    ]


def test_the_fragment_rule_is_one_clause_for_an_event(analyzer: NedAnalyzer) -> None:
    """The rule at its source: an event page takes its clause, a statement does not."""

    result = analyse(analyzer, GOLDEN_MULTIPLE)
    latency = next(s for s in result.evidence if s.signal_type.value == "response_latency")
    positive = next(s for s in result.evidence if s.polarity == "positive")
    assert page_fragment(result.input, latency) == "她三天没回我消息"
    assert page_fragment(result.input, positive) == "夸我可爱"
    assert page_fragment(result.input, latency) in result.input
    assert page_fragment(result.input, positive) in result.input


def test_no_duration_the_engine_tagged_is_dropped(analyzer: NedAnalyzer) -> None:
    """Whatever duration the evidence carries, the page keeps its wording."""

    for text, _expected in TIME_QUALIFIER_CASES:
        result = analyse(analyzer, text)
        aspects = result.material_aspects
        if aspects is None:
            continue
        for item in aspects.materials:
            span = result.evidence[item.evidence_index]
            surface = "" if span.duration is None else span.duration.surface
            if surface and surface in text:
                assert surface in item.text, (text, surface, item.text)


def test_stage_one_material_column_is_untouched(analyzer: NedAnalyzer) -> None:
    """The asymmetry is deliberate: Stage 1 files the reader's explanation and
    keeps its tail-completed fragments, Stage 2 files events and keeps their
    whole clause. Neither layer re-reads the other's data.
    """

    result = analyse(analyzer, STAGE1_AUDIT)
    audit = result.interpretation_audit
    aspects = result.material_aspects
    assert audit is not None and aspects is not None
    assert "没回我" in audit.material
    assert "三天没回我" in [item.text for item in aspects.materials]


# --------------------------------------------------------------------------- #
# 3. the no-netting contract
# --------------------------------------------------------------------------- #


def test_the_schema_has_no_analysis_number(analyzer: NedAnalyzer) -> None:
    """Selectors and pointers only: no strength, no score, no probability."""

    result = analyse(analyzer, GOLDEN_MULTIPLE)
    aspects = result.material_aspects
    assert aspects is not None
    assert set(type(aspects).model_fields) == {"materials", "relation_assessed"}
    assert set(type(aspects.materials[0]).model_fields) == {"evidence_index", "text"}
    for name, field in type(aspects.materials[0]).model_fields.items():
        if name == "evidence_index":
            continue
        assert field.annotation is str, name


def test_a_page_points_at_the_evidence_it_came_from(analyzer: NedAnalyzer) -> None:
    result = analyse(analyzer, GOLDEN_MULTIPLE)
    aspects = result.material_aspects
    assert aspects is not None
    for item in aspects.materials:
        assert 0 <= item.evidence_index < len(result.evidence)
        assert item.text in result.input


def test_the_pages_are_in_input_order(analyzer: NedAnalyzer) -> None:
    result = analyse(analyzer, GOLDEN_MULTIPLE)
    aspects = result.material_aspects
    assert aspects is not None
    starts = [result.evidence[item.evidence_index].start for item in aspects.materials]
    assert starts == sorted(starts)


def test_one_act_of_text_is_one_page(analyzer: NedAnalyzer) -> None:
    """Two rules covering the same words are one page, not two."""

    result = analyse(analyzer, "她主动找我聊了两个小时，但他昨天没回我。")
    aspects = result.material_aspects
    assert aspects is not None
    positives = [
        item
        for item in aspects.materials
        if result.evidence[item.evidence_index].polarity == "positive"
    ]
    assert len(positives) == 1, [item.text for item in positives]


def test_the_threshold_is_the_shipped_band_edge() -> None:
    """25.0 is the 有限 band edge, not a number chosen for these samples."""

    assert p.quality_label(POSITIVE_PAGE_MIN_STRENGTH) == "有限"
    assert p.quality_label(POSITIVE_PAGE_MIN_STRENGTH - 0.1) == "较弱"


def test_no_grade_moves_when_the_second_page_appears(analyzer: NedAnalyzer) -> None:
    """The ledger grows; no existing material's grade changes."""

    pairs = (
        ("她夸我可爱，但她三天没回我消息。", "她夸我可爱", "她三天没回我消息。"),
        ("她记得我爱吃什么，但她说我们还是做朋友吧。", "她记得我爱吃什么", "她说我们还是做朋友吧"),
        ("他给我点了一杯奶茶，但他说我们不合适。", "他给我点了奶茶", "他说我们不合适"),
    )
    for together, first_alone, second_alone in pairs:
        combined = analyse(analyzer, together)
        for alone in (first_alone, second_alone):
            single = analyse(analyzer, alone)
            for span in single.evidence:
                match = next(
                    (item for item in combined.evidence if item.rule_id == span.rule_id), None
                )
                assert match is not None, (together, span.rule_id)
                assert match.base_strength == span.base_strength, (together, span.rule_id)
                assert match.information_content == span.information_content, (
                    together,
                    span.rule_id,
                )
                assert match.polarity == span.polarity, (together, span.rule_id)


def test_a_boundary_grade_never_moves(analyzer: NedAnalyzer) -> None:
    for with_material, alone in (
        ("她记得我爱吃什么，但她说我们还是做朋友吧。", "她说我们还是做朋友吧"),
        ("他约我周末看电影，后来又说我们保持距离吧。", "他说我们保持距离吧"),
    ):
        combined, single = analyse(analyzer, with_material), analyse(analyzer, alone)
        kept = next(
            span for span in combined.evidence if span.signal_type.value == "direct_rejection"
        )
        base = next(
            span for span in single.evidence if span.signal_type.value == "direct_rejection"
        )
        assert kept.base_strength == base.base_strength
        assert kept.information_content == base.information_content
        assert p.page_grade(kept, "zh") == p.page_grade(base, "zh") == "明确"


def test_the_card_carries_no_number_at_all(analyzer: NedAnalyzer) -> None:
    """No aggregate, no average, no percentage, no count, no score.

    The card names its pages with words (材料一/材料二) and grades them with the
    shipped ladder, so it contains no digit anywhere. Any number would have to be
    a number NED computed about the two pages together.
    """

    for text in (GOLDEN_MULTIPLE, *GOLDEN_BOUNDARY):
        card = card_text(analyzer, text)
        assert not any(character.isdigit() for character in card), card


NEGATIONS = ("未", "不", "没")


def test_the_filing_register_names_the_arithmetic_it_did_not_do(analyzer: NedAnalyzer) -> None:
    """ "We did not add them up" is a promise, and the promise is explicit."""

    rows = rows_of(analyzer, GOLDEN_MULTIPLE)
    refusal = rows["本机构没有做"]
    for word in REFUSAL_WORDS:
        assert word in refusal, word


def test_arithmetic_is_never_performed_in_any_register(analyzer: NedAnalyzer) -> None:
    """Every arithmetic word is either inside the refusal row or negated where it
    stands ("未排名"). The boundary register names no arithmetic at all: it refuses a
    different thing, and it still computes nothing.
    """

    for text in (GOLDEN_MULTIPLE, *GOLDEN_BOUNDARY):
        language = rows_language(analyzer, text)
        situation = situation_of(analyzer, text)
        rows = rows_of(analyzer, text)
        refuse_label = p.aspect_copy(situation, language)["not_done_label"]
        assert refuse_label in rows, refuse_label
        for label, value in rows.items():
            for word in REFUSAL_WORDS:
                for position in range(len(value)):
                    if not value.startswith(word, position):
                        continue
                    before = value[position - 1] if position else ""
                    assert before in NEGATIONS or label == refuse_label, (text, label, word, value)
        if situation == p.SITUATION_BOUNDARY:
            for word in ("相加", "平均", "总分", "概率", "%"):
                assert word not in card_text(analyzer, text), (text, word)


def test_the_cards_never_use_aggregate_vocabulary(analyzer: NedAnalyzer) -> None:
    for text in (GOLDEN_MULTIPLE, *GOLDEN_BOUNDARY):
        blob = first_screen_text(analyzer, text) + card_text(analyzer, text)
        for word in FORBIDDEN_VOCABULARY:
            assert word not in blob, (text, word)


def test_the_cards_never_comfort(analyzer: NedAnalyzer) -> None:
    for text in (GOLDEN_MULTIPLE, *GOLDEN_BOUNDARY, BELOW_FLOOR, STAGE1_AUDIT):
        blob = card_text(analyzer, text)
        for word in COMFORT:
            assert word not in blob, (text, word)


def test_materials_are_what_the_input_reports(analyzer: NedAnalyzer) -> None:
    """Reported material, never a verified fact and never a family example."""

    for text in (GOLDEN_MULTIPLE, *GOLDEN_BOUNDARY):
        card = card_text(analyzer, text)
        assert "输入报告" in card
        for claim in ("已确认", "属实", "事实上", "证明", "说明她"):
            assert claim not in card, (text, claim)


def test_the_card_is_only_shown_where_it_is_promised(analyzer: NedAnalyzer) -> None:
    assert p.ASPECT_CARD_SITUATIONS == (p.SITUATION_MULTIPLE_ASPECTS, p.SITUATION_BOUNDARY)
    for text in (*SINGLE_SIDED, *HOSTILE, SELF_WORTH, STAGE1_AUDIT, *READER_CONCLUSION):
        assert card_text(analyzer, text).strip() == "", text
