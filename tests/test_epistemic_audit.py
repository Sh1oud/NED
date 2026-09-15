"""Stage 1: the Alternative Explanation Audit.

What this file defends, in the order the Mission Contract lists it:

* an explanation the reader submitted is audited; one NED invented is not;
* the audit records whether the input reports material *for* that explanation —
  it never says the explanation is supported, refuted, better or worse;
* no additional material is not a refutation, and additional material is not a
  confirmation;
* material is always *reported* material, never a verified fact;
* the sentence a screen quotes is the reader's own words or nothing;
* a boundary keeps its screen, and hostile input keeps its screen.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ned.app.cli import (
    captured_reading_of,
    render_epistemic_breakdown,
    screen_context,
    screen_quality,
)
from ned.app.core.analyzer import NedAnalyzer
from ned.app.ui import personality as p
from rich.console import Console

RULES = Path(__file__).resolve().parent.parent / "ned" / "app" / "rules" / "signals.json"

GOLDEN = (
    "她说喜欢我，但可能只是礼貌。",
    "她说喜欢我，但我觉得可能只是人好。",
    "他约我周末看电影，但可能只是无聊。",
    "他给我点了一杯奶茶，但可能只是顺手。",
    "他记得我爱吃什么，但可能只是习惯记这些。",
    "她说想和我做男女朋友，但我觉得她只是可怜我。",
)

#: Each golden case has its own flavour line; the table is the reviewed one.
GOLDEN_FLAVOUR = {
    "她说喜欢我，但可能只是礼貌。": "能解释一切的解释，本机构先放进观察名单。👍",
    "她说喜欢我，但我觉得可能只是人好。": "该理由本机构一天要用四十次，今天按规定回避，转第二科审查附件。👍",
    "他约我周末看电影，但可能只是无聊。": "补「可能」两个字，不算补材料。👍",
    "他给我点了一杯奶茶，但可能只是顺手。": "那件东西已经进卷；「顺手」是另一份说明。👍",
    "他记得我爱吃什么，但可能只是习惯记这些。": "习惯是另一份结论，不是已经交上来的材料。👍",
    "她说想和我做男女朋友，但我觉得她只是可怜我。": "悲观解释不享受免检通道。（该通道由本机构自行开设，现已关闭。）👍",
}

#: No reader explanation here, so there is nothing to audit.
WITHOUT_EXPLANATION = (
    "她夸我可爱，但她三天没回我消息。",
    "她主动找我聊了两个小时",
    "他今天夸我了",
    "我们昨天聊到凌晨三点",
)

#: An explanation with material on the other side of the ledger.
WITH_OTHER_MATERIAL = "她说喜欢我，但三天没回我，可能只是礼貌。"

#: The reader's own words, with nothing reported to explain.
READER_ONLY = ("可能只是人好", "我是不是想太多了")

#: A self-worth conclusion. It never reaches the comedy audit: it keeps its
#: existing serious screen.
SELF_WORTH = "她说喜欢我，但我根本不值得被喜欢"

#: The other reader shape, which deliberately stays out of this audit.
READER_NEGATIVE = "他三天没回我，我觉得他不想理我。"

#: Wording that would mean NED judged the explanation itself.
FORBIDDEN_VOCABULARY = (
    "支持该解释",
    "支持这个解释",
    "有材料支持",
    "没有支持它的材料",
    "反驳",
    "更可信",
    "更不可信",
    "为假",
    "一定是错的",
    "证明她说谎",
)

#: Wording that would turn reported material into a verified fact.
CERTIFICATION = ("已确认", "属实", "确实发生", "事实是", "她真的", "他真的")

#: Comfort NED is not allowed to hand out.
COMFORT = ("别难过", "你值得更好的", "会好的", "也许其实喜欢你", "相信自己")

R1_POSITIVE = ("她说想和我做男女朋友", "她想和我做男女朋友", "他说愿意和我做男女朋友")
R1_HARD_NEGATIVE = (
    "我们只是男女朋友吗",
    "怎么做男女朋友",
    "关于男女朋友的讨论",
    "她不想和我做男女朋友",
    "他没说要和我做男女朋友",
    "她想和我做朋友",
)
R2_POSITIVE = (
    "我觉得她只是可怜我",
    "我认为他只是顺手",
    "我感觉她只是习惯记这些",
    "我觉得可能只是人好",
)
R2_HARD_NEGATIVE = (
    "她觉得我可怜",
    "他说我只是可怜",
    "可怜的人很多",
    "礼貌很重要",
    "我觉得他这样做不太好",
    # a third-person subject may not borrow the first-person frame
    "他感觉我只是顺手",
    "大家都感觉她只是心软",
    "她感觉我只是家教好",
)

BOUNDARY = ("她说我们还是做朋友吧", "他说我们还是保持距离吧", "他说我很好 但我们不合适")
HOSTILE = ("她说你他妈有病吧", "她怒骂我")


@pytest.fixture(scope="module")
def analyzer() -> NedAnalyzer:
    return NedAnalyzer()


@pytest.fixture(scope="module")
def rules() -> dict[str, dict[str, object]]:
    pack = json.loads(RULES.read_text(encoding="utf-8"))
    return {rule["id"]: rule for rule in pack["signals"]}


def families(result: object) -> set[str]:
    return {span.signal_type.value for span in result.evidence}  # type: ignore[attr-defined]


def audit_of(analyzer: NedAnalyzer, text: str) -> object | None:
    return analyzer.analyze_text(text, mode="normal").interpretation_audit


def first_screen_text(analyzer: NedAnalyzer, text: str) -> str:
    result = analyzer.analyze_text(text, mode="normal")
    situation, basis, language = screen_context(result)
    screen = p.first_screen(
        situation,
        result.mode,
        language,
        basis=basis,
        reading=captured_reading_of(result),
        rule=p.primary_positive_rule(result.evidence),
    )
    return "\n".join((screen.title, *screen.lines, screen.reality))


def breakdown_text(analyzer: NedAnalyzer, text: str) -> str:
    result = analyzer.analyze_text(text, mode="normal")
    audit = result.interpretation_audit
    if audit is None:
        return ""
    return "\n".join(f"{label}: {value}" for label, value in p.audit_breakdown_rows(audit))


def shown_card(analyzer: NedAnalyzer, text: str) -> str:
    """What the CLI actually prints for the audit card, gate included."""

    result = analyzer.analyze_text(text, mode="normal")
    situation, _basis, _language = screen_context(result)
    out = Console(width=96, force_terminal=False, highlight=False)
    with out.capture() as capture:
        render_epistemic_breakdown(result, situation, out)
    return capture.get()


def situation_of(analyzer: NedAnalyzer, text: str) -> str:
    result = analyzer.analyze_text(text, mode="normal")
    return screen_context(result)[0]


# --------------------------------------------------------------------------- #
# the six golden cases
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", GOLDEN)
def test_a_golden_case_reaches_the_audit(analyzer: NedAnalyzer, text: str) -> None:
    assert audit_of(analyzer, text) is not None, text
    assert situation_of(analyzer, text) == p.SITUATION_EXPLANATION_AUDIT, text
    assert "ALTERNATIVE EXPLANATION AUDIT" in first_screen_text(analyzer, text), text


@pytest.mark.parametrize("text", GOLDEN)
def test_a_golden_case_records_material_and_a_reading(analyzer: NedAnalyzer, text: str) -> None:
    audit = audit_of(analyzer, text)
    assert audit is not None
    assert audit.material, text
    assert audit.reading, text
    assert audit.reading in text, text


@pytest.mark.parametrize("text", GOLDEN)
def test_a_golden_case_has_no_additional_material(analyzer: NedAnalyzer, text: str) -> None:
    audit = audit_of(analyzer, text)
    assert audit is not None
    assert audit.other_material == [], text
    assert audit.material_status == "no_additional_material", text


@pytest.mark.parametrize("text", GOLDEN)
def test_the_relation_is_never_assessed(analyzer: NedAnalyzer, text: str) -> None:
    audit = audit_of(analyzer, text)
    assert audit is not None
    assert audit.relation_assessed is False, text


@pytest.mark.parametrize("text", GOLDEN)
def test_the_screen_carries_the_family_flavour(analyzer: NedAnalyzer, text: str) -> None:
    assert GOLDEN_FLAVOUR[text] in first_screen_text(analyzer, text), text


@pytest.mark.parametrize("text", GOLDEN)
def test_the_quote_is_the_readers_own_words(analyzer: NedAnalyzer, text: str) -> None:
    """Quote fidelity: the audit quotes what the reader wrote, or nothing."""

    audit = audit_of(analyzer, text)
    assert audit is not None
    assert audit.reading in text
    assert audit.reading == audit.reading.strip()
    assert "你：" not in first_screen_text(analyzer, text)


@pytest.mark.parametrize("text", GOLDEN)
def test_the_audit_screen_still_shows_an_evidence_quality(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    situation, _basis, language = screen_context(result)
    assert screen_quality(situation, result, language), text


# --------------------------------------------------------------------------- #
# the audit is optional: no explanation means no audit
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", WITHOUT_EXPLANATION)
def test_no_reader_explanation_means_no_audit(analyzer: NedAnalyzer, text: str) -> None:
    assert audit_of(analyzer, text) is None, text
    assert situation_of(analyzer, text) != p.SITUATION_EXPLANATION_AUDIT, text
    assert breakdown_text(analyzer, text) == "", text


@pytest.mark.parametrize("text", READER_ONLY)
def test_an_explanation_with_nothing_to_explain_is_not_audited(
    analyzer: NedAnalyzer, text: str
) -> None:
    assert audit_of(analyzer, text) is None, text
    assert situation_of(analyzer, text) == p.SITUATION_SELF_DISCOUNT_ONLY, text


# --------------------------------------------------------------------------- #
# the two wordings, and what they may not become
# --------------------------------------------------------------------------- #


def test_additional_material_is_recorded_without_a_judgement(analyzer: NedAnalyzer) -> None:
    audit = audit_of(analyzer, WITH_OTHER_MATERIAL)
    assert audit is not None
    assert audit.other_material, "expected material beyond the explained material"
    assert audit.material_status == "additional_material_present"
    text = breakdown_text(analyzer, WITH_OTHER_MATERIAL)
    assert "输入还有其他材料" in text
    assert "不作判断" in text


def test_missing_material_is_not_a_refutation(analyzer: NedAnalyzer) -> None:
    text = breakdown_text(analyzer, GOLDEN[0])
    assert "当前输入没有为该解释另外提交材料。" in text
    for word in ("因此", "所以这个解释", "为假", "不成立"):
        assert word not in text, word


def test_present_material_is_not_a_confirmation(analyzer: NedAnalyzer) -> None:
    text = breakdown_text(analyzer, WITH_OTHER_MATERIAL)
    for word in ("因此", "所以这个解释成立", "更可信"):
        assert word not in text, word


@pytest.mark.parametrize("text", (*GOLDEN, WITH_OTHER_MATERIAL))
def test_the_audit_never_judges_the_explanation(analyzer: NedAnalyzer, text: str) -> None:
    blob = first_screen_text(analyzer, text) + breakdown_text(analyzer, text)
    for word in FORBIDDEN_VOCABULARY:
        assert word not in blob, (text, word)


@pytest.mark.parametrize("text", (*GOLDEN, WITH_OTHER_MATERIAL))
def test_material_is_never_certified_as_reality(analyzer: NedAnalyzer, text: str) -> None:
    blob = first_screen_text(analyzer, text) + breakdown_text(analyzer, text)
    for word in CERTIFICATION:
        assert word not in blob, (text, word)
    assert "输入报告" in blob or "卷宗" in blob, text


@pytest.mark.parametrize("text", (*GOLDEN, WITH_OTHER_MATERIAL, SELF_WORTH, READER_NEGATIVE))
def test_the_audit_never_comforts(analyzer: NedAnalyzer, text: str) -> None:
    blob = first_screen_text(analyzer, text) + breakdown_text(analyzer, text)
    for word in COMFORT:
        assert word not in blob, (text, word)


# --------------------------------------------------------------------------- #
# symmetry: the two reader shapes share one standard
# --------------------------------------------------------------------------- #


def test_every_audited_explanation_gets_the_same_structure(analyzer: NedAnalyzer) -> None:
    """Epistemic symmetry, not string symmetry: one window, one form.

    Every audited explanation is a self-discount of positive material, and each
    one gets the same fields, the same five breakdown rows and the same status
    vocabulary: no reason word earns a different standard.
    """

    shapes = []
    for text in GOLDEN:
        audit = audit_of(analyzer, text)
        assert audit is not None
        rows = p.audit_breakdown_rows(audit)
        shapes.append(
            (
                tuple(audit.model_dump().keys()),
                audit.material_status,
                audit.relation_assessed,
                tuple(label for label, _ in rows),
            )
        )
    assert len(set(shapes)) == 1, shapes


def test_the_discounts_material_is_the_positive_side(analyzer: NedAnalyzer) -> None:
    """The audit reads material existence by polarity, and never judges it."""

    result = analyzer.analyze_text(GOLDEN[0], mode="normal")
    audit = result.interpretation_audit
    assert audit is not None
    positive = [span for span in result.evidence if span.polarity == "positive"]
    assert audit.material == [span.text for span in positive]


# --------------------------------------------------------------------------- #
# fix 1: a self-worth conclusion is not comedy material
# --------------------------------------------------------------------------- #


def test_a_self_worth_conclusion_never_reaches_the_audit(analyzer: NedAnalyzer) -> None:
    assert audit_of(analyzer, SELF_WORTH) is None
    assert situation_of(analyzer, SELF_WORTH) != p.SITUATION_EXPLANATION_AUDIT
    assert breakdown_text(analyzer, SELF_WORTH) == ""


def test_a_negative_conclusion_keeps_its_serious_path(analyzer: NedAnalyzer) -> None:
    """The existing reader-conclusion shape is untouched by Stage 1."""

    result = analyzer.analyze_text(READER_NEGATIVE, mode="normal")
    assert result.interpretation_audit is None
    assert "self_negative_belief" in families(result)
    assert situation_of(analyzer, READER_NEGATIVE) != p.SITUATION_EXPLANATION_AUDIT


@pytest.mark.parametrize("text", (SELF_WORTH, READER_NEGATIVE))
def test_the_unaudited_shapes_show_no_audit_copy(analyzer: NedAnalyzer, text: str) -> None:
    blob = first_screen_text(analyzer, text)
    assert "ALTERNATIVE EXPLANATION AUDIT" not in blob, text
    for key, lines in p.AUDIT_FLAVOURS.items():
        for line in lines:
            assert line not in blob, (text, key)


# --------------------------------------------------------------------------- #
# fix 2: the breakdown reports the input, not somebody else's example
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", GOLDEN)
def test_the_material_column_is_the_input_itself(analyzer: NedAnalyzer, text: str) -> None:
    """Volume layer: material is the actual fragment, never a family example."""

    audit = audit_of(analyzer, text)
    assert audit is not None
    assert audit.material, text
    for fragment in audit.material:
        assert fragment in text, (text, fragment)
        assert fragment == fragment.strip()


@pytest.mark.parametrize("text", GOLDEN)
def test_the_breakdown_material_column_matches_the_audit(analyzer: NedAnalyzer, text: str) -> None:
    audit = audit_of(analyzer, text)
    assert audit is not None
    rows = dict(p.audit_breakdown_rows(audit))
    assert rows[p.AUDIT_COPY["material_label"]] == "；".join(audit.material)


@pytest.mark.parametrize(
    ("text", "misleading_example"),
    (
        ("他约我周末看电影，但可能只是无聊。", "约我吃饭"),
        ("他记得我爱吃什么，但可能只是习惯记这些。", "让我早点睡"),
        ("他给我点了一杯奶茶，但可能只是顺手。", "送我东西"),
    ),
)
def test_no_other_family_example_appears_in_the_breakdown(
    analyzer: NedAnalyzer, text: str, misleading_example: str
) -> None:
    """The defect the review found: a label's own example standing in for material."""

    blob = breakdown_text(analyzer, text)
    assert misleading_example not in blob, (text, misleading_example)


# --------------------------------------------------------------------------- #
# fix 3: the flavour lines imply no evidence category
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# pre-commit fix A: a fragment must be complete and readable
# --------------------------------------------------------------------------- #


def ends_its_clause(text: str, fragment: str) -> bool:
    """A fragment that stops mid-clause has been cut, not quoted."""

    start = text.find(fragment)
    if start < 0:
        return False
    after = text[start + len(fragment) : start + len(fragment) + 1]
    return after == "" or after in p.CLAUSE_SEPARATORS


def test_case_5_material_is_complete_and_readable(analyzer: NedAnalyzer) -> None:
    """The defect: "记得我爱" — a material fragment with no meaning left."""

    audit = audit_of(analyzer, GOLDEN[4])
    assert audit is not None
    assert audit.material == ["记得我爱吃什么"], audit.material
    assert audit.material[0] in GOLDEN[4]
    assert ends_its_clause(GOLDEN[4], audit.material[0])


@pytest.mark.parametrize("text", (*GOLDEN, WITH_OTHER_MATERIAL))
def test_every_fragment_is_complete_and_readable(analyzer: NedAnalyzer, text: str) -> None:
    audit = audit_of(analyzer, text)
    assert audit is not None
    for fragment in (*audit.material, *audit.other_material):
        assert fragment in text, (text, fragment)
        assert fragment == fragment.strip(), (text, fragment)
        assert ends_its_clause(text, fragment), (text, fragment)
    assert ends_its_clause(text, audit.reading), (text, audit.reading)


@pytest.mark.parametrize("text", (*GOLDEN, WITH_OTHER_MATERIAL))
def test_the_same_fragment_is_never_material_twice(analyzer: NedAnalyzer, text: str) -> None:
    audit = audit_of(analyzer, text)
    assert audit is not None
    assert len(set(audit.material)) == len(audit.material), audit.material


# --------------------------------------------------------------------------- #
# pre-commit fix B: the quote is complete in the data itself
# --------------------------------------------------------------------------- #


def test_case_6_reading_is_the_complete_quote(analyzer: NedAnalyzer) -> None:
    """The defect: the payload held "我觉得她只是可怜" and the UI completed it."""

    audit = audit_of(analyzer, GOLDEN[5])
    assert audit is not None
    assert audit.reading == "我觉得她只是可怜我", audit.reading
    assert audit.reading in GOLDEN[5]


@pytest.mark.parametrize("text", GOLDEN)
def test_the_reading_needs_no_display_repair(analyzer: NedAnalyzer, text: str) -> None:
    """One quote, not two: the payload already holds what the card shows."""

    result = analyzer.analyze_text(text, mode="normal")
    audit = result.interpretation_audit
    assert audit is not None
    assert audit.reading == captured_reading_of(result), (audit.reading, text)
    rows = dict(p.audit_breakdown_rows(audit))
    assert rows[p.AUDIT_COPY["reading_label"]] == audit.reading, rows


# --------------------------------------------------------------------------- #
# pre-commit fix C: the card is displayed only under the audit screen
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", GOLDEN)
def test_the_audit_screen_shows_the_card(analyzer: NedAnalyzer, text: str) -> None:
    assert "Epistemic Breakdown" in shown_card(analyzer, text), text


def test_the_mixed_input_keeps_its_screen_and_hides_the_card(analyzer: NedAnalyzer) -> None:
    """Positive material + latency + an explanation is Stage 2's subject."""

    result = analyzer.analyze_text(WITH_OTHER_MATERIAL, mode="normal")
    assert result.interpretation_audit is not None
    situation = situation_of(analyzer, WITH_OTHER_MATERIAL)
    assert situation == p.SITUATION_STARTED_AGAIN, situation
    assert "Epistemic Breakdown" not in shown_card(analyzer, WITH_OTHER_MATERIAL)


@pytest.mark.parametrize(
    "text",
    (
        "她说我们还是做朋友吧，但我觉得她只是可怜我",
        "她说你他妈有病吧，但我觉得她只是可怜我",
    ),
)
def test_no_card_outside_the_audit_screen(analyzer: NedAnalyzer, text: str) -> None:
    situation = situation_of(analyzer, text)
    assert situation != p.SITUATION_EXPLANATION_AUDIT, situation
    assert "Epistemic Breakdown" not in shown_card(analyzer, text)


#: Words that would tell the reader what material settles their explanation.
CATEGORY_HINTS = ("成本", "时间", "频率", "次数", "模式", "重复", "次数")


@pytest.mark.parametrize("text", GOLDEN)
def test_no_flavour_line_names_an_evidence_category(analyzer: NedAnalyzer, text: str) -> None:
    blob = first_screen_text(analyzer, text)
    for hint in CATEGORY_HINTS:
        assert hint not in blob, (text, hint)


def test_the_gift_and_habit_lines_are_reviewed_copy() -> None:
    """Pinned: these two were rewritten, and the rewrite is what ships."""

    assert p.AUDIT_FLAVOURS["顺手"] == (
        "「顺手」已入档，附件：0。",
        "那件东西已经进卷；「顺手」是另一份说明。👍",
    )
    assert p.AUDIT_FLAVOURS["习惯"] == (
        "「习惯」已入档，附件：0。",
        "习惯是另一份结论，不是已经交上来的材料。👍",
    )


# --------------------------------------------------------------------------- #
# R1 / R2: the two approved wording completions, with their hard negatives
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", R1_POSITIVE)
def test_r1_recognises_the_ordinary_offer(analyzer: NedAnalyzer, text: str) -> None:
    assert "commitment_offer" in families(analyzer.analyze_text(text, mode="normal")), text


@pytest.mark.parametrize("text", R1_HARD_NEGATIVE)
def test_r1_hard_negatives(analyzer: NedAnalyzer, text: str) -> None:
    assert "commitment_offer" not in families(analyzer.analyze_text(text, mode="normal")), text


@pytest.mark.parametrize("text", R2_POSITIVE)
def test_r2_recognises_the_first_person_frame(analyzer: NedAnalyzer, text: str) -> None:
    assert "self_discount" in families(analyzer.analyze_text(text, mode="normal")), text


@pytest.mark.parametrize("text", R2_HARD_NEGATIVE)
def test_r2_hard_negatives(analyzer: NedAnalyzer, text: str) -> None:
    assert "self_discount" not in families(analyzer.analyze_text(text, mode="normal")), text


def test_r2_needs_the_first_person(rules: dict[str, dict[str, object]]) -> None:
    """A door, not a wall: only explicit first-person frames count."""

    joined = " ".join(rules["zh.self_discount"]["patterns"])  # type: ignore[arg-type]
    assert "我觉得|我认为|我感觉" in joined
    assert "我感觉|感觉" not in joined.replace("我觉得|我认为|我感觉", "")
    assert '"只是"' not in joined


# --------------------------------------------------------------------------- #
# boundary and hostile keep their behaviour
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", BOUNDARY)
def test_a_boundary_keeps_its_screen(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text
    assert situation_of(analyzer, text) in p.BOUNDARY_SITUATIONS, text


def test_a_boundary_outranks_the_audit(analyzer: NedAnalyzer) -> None:
    """An explanation may not push a stated boundary off its own screen."""

    text = "她说我们还是做朋友吧，但我觉得她只是可怜我"
    assert situation_of(analyzer, text) in p.BOUNDARY_SITUATIONS or (
        situation_of(analyzer, text) != p.SITUATION_EXPLANATION_AUDIT
    )


@pytest.mark.parametrize("text", HOSTILE)
def test_hostile_input_keeps_its_screen(analyzer: NedAnalyzer, text: str) -> None:
    assert situation_of(analyzer, text) == p.SITUATION_HOSTILE, text
    assert audit_of(analyzer, text) is None, text


@pytest.mark.parametrize("text", (*BOUNDARY, *HOSTILE))
def test_boundary_and_hostile_screens_carry_no_audit_copy(analyzer: NedAnalyzer, text: str) -> None:
    blob = first_screen_text(analyzer, text)
    for key, lines in p.AUDIT_FLAVOURS.items():
        for line in lines:
            assert line not in blob, (text, key)
    assert "ALTERNATIVE EXPLANATION AUDIT" not in blob, text
