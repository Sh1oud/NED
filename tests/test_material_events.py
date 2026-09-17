"""PR-2 pins: bounded event recognition, and the state a reader is shown.

PR-0 (the RH-5 black-box pass) found that most ordinary inputs produced nothing at all: the
engine recognised no material and the report said "no classifiable signal", so a reader
could not tell "NED heard this and cannot sign a conclusion" from "NED did not hear this".

These tests pin the three states, the event families that fill the middle one, and the
properties that must not move: material is never evidence, a quote is never rewritten, an
explicit boundary keeps priority, and PR-1's polarity repair still holds.
"""

from __future__ import annotations

import pytest
from ned.app.cli import registered_materials_of, screen_context
from ned.app.core import events
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.rules import RuleBook
from ned.app.ui import personality as p

#: One representative input per event family.
FAMILY_CASES = (
    ("relationship_status", "我们在一起了"),
    ("relationship_status", "我们分手了"),
    ("relationship_status", "她说她只是把我当朋友"),
    ("relationship_status", "她说我们只是朋友"),
    ("contact_access", "她把我删了"),
    ("contact_access", "她把我拉黑了"),
    ("contact_access", "她说不想联系我了"),
    ("social_interaction", "她跟别的男生出去玩了"),
    ("memory_care_act", "她记得我生日"),
    ("reported_evaluation", "她说“你值得更好的人”"),
    ("reported_evaluation", "她说“你是个好人”"),
    ("reported_evaluation", "她说她对我没感觉"),
    ("reported_dismissal", "她说“你想多了”"),
    ("reported_dismissal", "她说“你误会了”"),
    ("reported_deferral", "她说“我还没准备好”"),
    ("reported_deferral", "她说“我考虑一下”"),
    ("reported_deferral", "她说她需要一点空间"),
    ("external_opposition", "她妈妈不同意我们在一起"),
    ("external_opposition", "她父母反对我们在一起"),
)

#: Inputs that must stay genuinely unrecognised: NED does not have to understand everything.
NOTHING_CASES = (
    "今天食堂的饭好难吃",
    "快递又丢件了",
    "她刚给我发了个“嗯”",
    "我家的猫今天不理我",
)


def material_kinds(analyzer: NedAnalyzer, text: str) -> list[str]:
    result = analyzer.analyze_text(text, mode="normal")
    return [item.material_kind for item in (result.materials or [])]


# --------------------------------------------------------------------------- #
# 1. bounded event families
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("kind", "text"), FAMILY_CASES)
def test_each_family_registers_its_material(analyzer: NedAnalyzer, kind: str, text: str) -> None:
    assert kind in material_kinds(analyzer, text), text


@pytest.mark.parametrize(("kind", "text"), FAMILY_CASES)
def test_registered_material_is_never_evidence(analyzer: NedAnalyzer, kind: str, text: str) -> None:
    """Material is what the input reports; evidence is what NED may weigh. Never the same."""

    result = analyzer.analyze_text(text, mode="normal")
    for item in result.materials or []:
        assert item.origin_rule_id.startswith(("zh.event.", "zh.material.")), item.origin_rule_id
        assert item.epistemic_status == "reported"
    if result.recognition == "material_registered":
        assert result.evidence == []
        assert result.verdict.code == "ned.no_signal"


@pytest.mark.parametrize(("kind", "text"), FAMILY_CASES)
def test_the_recorded_content_is_a_verbatim_slice(
    analyzer: NedAnalyzer, kind: str, text: str
) -> None:
    """A material never paraphrases, rewrites or normalises the reader's words."""

    result = analyzer.analyze_text(text, mode="normal")
    for item in result.materials or []:
        assert item.reported_content in text, item.reported_content
        assert item.start >= 0 and item.end <= len(text)
        assert text[item.start : item.end] == item.reported_content


@pytest.mark.parametrize("text", NOTHING_CASES)
def test_an_unrecognised_input_stays_unrecognised(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.recognition == "nothing_recognized", text
    assert result.materials == []


def test_the_pack_is_bounded_and_auditable() -> None:
    """Every rule declares its family, its material kind and why it cannot be signed alone."""

    rules = events.event_rules(RuleBook.load())
    assert len(rules) >= 8
    for rule in rules:
        assert rule.patterns
        assert rule.commitment_reason, rule.id
        assert rule.labels.get("zh") and rule.labels.get("en"), rule.id
    families = {rule.family for rule in rules}
    assert {
        "relationship_status",
        "contact_access",
        "social_interaction",
        "memory_care_act",
        "reported_evaluation",
        "reported_deferral",
    } <= families


# --------------------------------------------------------------------------- #
# 2. the state model
# --------------------------------------------------------------------------- #


def test_the_three_states_are_distinct(analyzer: NedAnalyzer) -> None:
    adjudicated = analyzer.analyze_text("她暂时不想谈恋爱", mode="normal")
    registered = analyzer.analyze_text("她记得我生日", mode="normal")
    nothing = analyzer.analyze_text("今天食堂的饭好难吃", mode="normal")

    assert adjudicated.recognition == "adjudicated"
    assert registered.recognition == "material_registered"
    assert nothing.recognition == "nothing_recognized"


def test_the_state_is_read_from_the_real_layers(analyzer: NedAnalyzer) -> None:
    """The state follows evidence and material, and nothing else."""

    for text in ("她说她讨厌我", "我们分手了", "她把我删了"):
        result = analyzer.analyze_text(text, mode="normal")
        assert result.materials, text
        assert not result.evidence, text
        assert result.recognition == "material_registered", text


def test_material_and_evidence_coexist_without_the_state_lying(analyzer: NedAnalyzer) -> None:
    """When a verdict was signed, the state says so even if material was also filed."""

    result = analyzer.analyze_text("她给我带了一份早餐", mode="normal")
    assert result.evidence
    assert result.materials
    assert result.recognition == "adjudicated"


def test_the_first_screen_no_longer_contradicts_the_registry(analyzer: NedAnalyzer) -> None:
    """PR-0's C4: the screen said "no signal" while the registry had already filed a record."""

    result = analyzer.analyze_text("她说她不喜欢我", mode="normal")
    situation, _basis, language = screen_context(result)
    assert situation == p.SITUATION_MATERIAL_ONLY
    screen = p.first_screen(
        situation, "normal", language, materials=registered_materials_of(result)
    )
    blob = " ".join([screen.title, *screen.lines, screen.reality])
    assert registered_materials_of(result) == ("她不喜欢我",)
    assert "她不喜欢我" in blob
    assert "不是本机构核实过的事实" in blob


def test_the_two_empty_states_use_different_words(analyzer: NedAnalyzer) -> None:
    registered = analyzer.analyze_text("她记得我生日", mode="normal")
    registered_screen = p.first_screen(
        p.SITUATION_MATERIAL_ONLY, "normal", "zh", materials=registered_materials_of(registered)
    )
    nothing_screen = p.first_screen(p.SITUATION_NO_SIGNAL, "normal", "zh")
    assert registered_screen.title != nothing_screen.title
    assert "已登记" in " ".join(registered_screen.lines)
    assert "没有识别到可登记的材料" in " ".join(nothing_screen.lines)


# --------------------------------------------------------------------------- #
# 3. synonym families: heard the same way
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("left", "right"),
    (
        ("她说她只想做朋友", "她说她只是把我当朋友"),
        ("她说我们只是朋友", "她说她只是把我当朋友"),
        ("她说不想联系我了", "她让我别再联系她了"),
        ("她说“你是个好人”", "她说“你值得更好的人”"),
        ("她说“我还没准备好”", "她说“我考虑一下”"),
    ),
)
def test_synonyms_share_one_family(analyzer: NedAnalyzer, left: str, right: str) -> None:
    """Two phrasings of one meaning must not differ in whether they were heard at all."""

    left_kinds = set(material_kinds(analyzer, left))
    right_kinds = set(material_kinds(analyzer, right))
    assert left_kinds and right_kinds, (left, left_kinds, right, right_kinds)
    assert left_kinds & right_kinds, (left, left_kinds, right, right_kinds)


def test_a_boundary_still_wins_over_its_material(analyzer: NedAnalyzer) -> None:
    """An explicit boundary keeps priority: material does not decide the screen."""

    for text in ("她说她只想做朋友", "她让我别再联系她了"):
        result = analyzer.analyze_text(text, mode="normal")
        assert result.verdict.code == "ned.direct_rejection", text
        assert result.recognition == "adjudicated", text
        assert result.materials, text


# --------------------------------------------------------------------------- #
# 4. PR-1's repair and the hard lines still hold
# --------------------------------------------------------------------------- #

BLOCKER_SHAPES = (
    "她暂时不想谈恋爱",
    "她说她暂时不想谈恋爱",
    "她说“我现在不想谈恋爱”",
    "她目前不想谈恋爱",
    "她短期内不想谈恋爱",
    "她坚决不想谈恋爱",
    "她说她目前不想谈恋爱",
    "她说她坚决不想谈恋爱",
    "她表示暂时不想谈恋爱",
    "她跟我说她暂时不想谈恋爱",
    "她妈妈不同意我们在一起",
    "她家里不同意我们在一起",
    "她父母反对我们在一起",
    "我妈妈不同意我们在一起",
    "她妈妈不赞成我们在一起",
    "她妈妈不支持我们在一起",
    "她暂时不想见我",
    "她暂时不想发展成恋爱关系",
    "她暂时只想做朋友",
)


@pytest.mark.parametrize("text", BLOCKER_SHAPES)
def test_pr1_shapes_stay_non_positive(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert not any(span.polarity == "positive" for span in result.evidence), text


@pytest.mark.parametrize(
    "text",
    (
        "她妈妈不同意我们在一起",
        "她家里不同意我们在一起",
        "她父母反对我们在一起",
        "我妈妈不同意我们在一起",
    ),
)
def test_third_party_resistance_is_still_not_her_boundary(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert not any(span.rule_id == "zh.direct_rejection" for span in result.evidence), text
    # PR-2 files it as third-party resistance, so the reader is told it was heard without
    # anybody pretending it was her own refusal.
    assert "external_opposition" in material_kinds(analyzer, text), text


def test_policy_a_and_the_positive_controls_are_untouched(analyzer: NedAnalyzer) -> None:
    assert analyzer.analyze_text("不要再联系我", mode="normal").verdict.code != (
        "ned.direct_rejection"
    )
    for text in ("她想和我谈恋爱", "她说想和我在一起", "她妈妈同意我们在一起"):
        result = analyzer.analyze_text(text, mode="normal")
        assert any(span.polarity == "positive" for span in result.evidence), text


def test_the_reader_is_never_told_an_item_they_did_not_mention(analyzer: NedAnalyzer) -> None:
    """The stock copy may joke, but it may not invent a fact about the reader's input.

    PR-2 removed the three worst offenders: the milk tea (any gift), the invented hour (any
    long chat) and the invented "mm" (any short reply).
    """

    for text in (
        "她给我带了一份早餐",
        "她主动找我聊天了，聊了半个小时",
        "她在群里回别人很快，回我很慢",
    ):
        result = analyzer.analyze_text(text, mode="normal")
        situation, basis, language = screen_context(result)
        screen = p.first_screen(
            situation,
            result.mode,
            language,
            basis=basis,
            materials=registered_materials_of(result),
            rule="",
        )
        blob = " ".join([screen.title, *screen.lines, screen.reality])
        for invented in ("奶茶", "凌晨三点", "聊了两个小时", "「嗯」"):
            assert invented not in blob, (text, invented, blob)
