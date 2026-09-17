"""Structured recall expansion: what the two families now recognise.

Phase 2B widened ``zh.sustained_interaction`` and ``zh.self_discount`` to the
language constructions ordinary people actually use — durations, endpoints,
habitual frequency, ranges; hedged alternative explanations and self-doubt — and
gave ``sustained_interaction`` the guards it never had.

Two rules of the phase are pinned here:
  * recognition may widen, strength may not (weights, information_content,
    salience, polarity and signal_type are frozen);
  * no other family may be expanded in the same pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from ned.app.core.analyzer import NedAnalyzer
from ned.app.ui import personality as p

RULES = Path(__file__).resolve().parent.parent / "ned" / "app" / "rules" / "signals.json"

#: The two families this phase owns, with the constructions it added. Pinned so a
#: later phase has to acknowledge the change here.
EXPANDED: dict[str, list[str]] = {
    "zh.sustained_interaction": [
        "聊(了)?(很久|好久|好一会儿)",
        "一聊就是[^。！？!?，,]{0,6}(小时|个?钟头)",
        "聊到([0-9一二三四五六七八九十两]{1,3}(点|点钟)|天亮|清晨|深夜)",
        "(每天|天天|每晚|经常|常常|时不时|总是|老是)[^。！？!?，,]{0,6}"
        "(找我聊|陪我聊|陪我聊天|聊天|来找我|聊到|聊很久)",
        "从[^。！？!?，,]{0,6}聊到[^。！？!?，,]{0,6}",
        "(聊|说|打电话)[^。！？!?，,]{0,3}(一整晚|一晚上|一整夜|一通宵|整晚|整夜)",
    ],
    "zh.self_discount": [
        "(可能|也许|或许|大概|会不会|是不是|别是|我觉得|我认为|我感觉)"
        "[^。！？!?，,]{0,3}只是"
        "[^。！？!?，,]{0,4}(人好|礼貌|客气|朋友|友善|同情|可怜|心软|习惯|顺手|无聊|寂寞|"
        "不好意思|愧疚|亏欠|责任|怕我|难过|为难|对谁都|对每个人|家教|性格|人家|有礼貌|心善)",
        "想(得)?(太|很|好)多(了)?",
    ],
}

FROZEN: dict[str, tuple[float, float, float | None]] = {
    "zh.sustained_interaction": (66.0, 74.0, 1.15),
    "zh.self_discount": (70.0, 20.0, None),
}

SI_POSITIVE = (
    "我们昨天聊了三个小时",
    "她陪我聊了一整晚",
    "昨天聊到凌晨三点",
    "最近每天晚上都来找我聊天",
    "他天天陪我聊天到很晚",
    "我们从晚上十点聊到凌晨两点",
    "一聊就是几个小时",
    "最近经常聊很久",
    "昨天一直聊到半夜",
    "我们聊了一晚上",
    "前天晚上聊到两点多",
    "她最近老是找我聊天",
    "每天晚上都要聊到很晚",
    "我们从八点聊到十一点",
    "他陪我聊了好久",
    "这周几乎每天都聊天",
    "我们经常聊到半夜",
    "她每天准时来找我聊天",
)

#: Allowed to stay unrecognised: no duration, endpoint or habit to hold on to.
SI_CONSERVATIVE = ("昨天一聊就停不下来",)

SI_NEGATIVE = (
    "我们开会聊了三个小时",
    "老师跟我聊了一下午论文",
    "医生跟我聊了很久病情",
    "客服跟我聊了半小时退款",
    "老板找我聊到晚上",
    "我妈跟我聊到半夜",
    "游戏里我们聊了三小时战术",
    "采访聊了一整个下午",
    "他们两个聊到凌晨",
    "电影里男女主聊了一晚上",
    "我们聊工作聊了三个小时",
    "我跟同事开会聊了很久",
    "昨天加班聊到十点",
    "上课的时候老师跟我聊了很久",
    "他跟所有人都聊到很晚",
    "销售跟我聊了半个小时",
    "我跟我妈每天晚上都聊天",
    "面试聊了一个小时",
    "开会一聊就是三个小时",
)

SD_POSITIVE = (
    "可能只是在同情我",
    "也许只是出于礼貌",
    "她可能只是心软",
    "可能只是习惯了",
    "也许只是怕我难过",
    "可能只是顺手",
    "会不会只是对谁都这样",
    "是不是我想多了",
    "我是不是想太多了",
    "可能是我想多了",
    "她可能只是不好意思",
    "也许只是出于客气",
    "可能只是可怜我",
    "她可能只是家教好",
    "也许只是习惯了有我",
    "可能只是出于责任",
    "可能只是无聊",
    "我是不是想得太多了",
    "会不会只是人家客气",
)

SD_NEGATIVE = (
    "她只是今天比较忙",
    "我只是随便问问",
    "只是天气不好",
    "他只是晚到了一会儿",
    "这只是电影台词",
    "我只是喜欢吃面",
    "她只是我同事",
    "她只是我朋友",
    "只是因为今天下雨",
    "我只是觉得这个功能很好笑",
    "她只是说今天有事",
    "我只是在开玩笑",
    "只是这条路有点堵",
    "她只是问我几点下班",
    "我只是想确认一下时间",
    "他只是在吐槽天气",
    "只是这个软件有点卡",
    "她只是我同学",
    "我只是随便看看",
    "我今天只是想早点睡",
)

CONTRASTIVE = (
    ("她以前很少找我聊天，但最近每天陪我聊到凌晨", "sustained_interaction"),
    ("昨天我们聊工作聊了三个小时，晚上她又主动陪我聊到凌晨", "sustained_interaction"),
    ("她说喜欢我，但我觉得可能只是出于礼貌", "self_discount"),
)


@pytest.fixture(scope="module")
def analyzer() -> NedAnalyzer:
    return NedAnalyzer()


@pytest.fixture(scope="module")
def rules() -> dict[str, dict[str, Any]]:
    pack = json.loads(RULES.read_text(encoding="utf-8"))
    return {rule["id"]: rule for rule in pack["signals"]}


def families(result: Any) -> set[str]:
    return {span.signal_type.value for span in result.evidence}


# --------------------------------------------------------------------------- #
# the phase's own rules
# --------------------------------------------------------------------------- #


def test_only_the_two_families_gained_patterns(rules: dict[str, dict[str, Any]]) -> None:
    """This round's two families, unchanged by the later Stage 1 wording patch."""

    for rule_id, added in EXPANDED.items():
        patterns = rules[rule_id]["patterns"]
        for construction in added:
            assert construction in patterns, (rule_id, construction)
    # v0.1.8 Stage 1 added exactly one pattern elsewhere, and only one
    assert "(想|要|愿意|希望)?和我做男女朋友" in rules["zh.commitment_offer"]["patterns"]
    # PR-1 added the two affirmative relationship-intent shapes (想和我在一起 /
    # 要不要在一起); the pack itself did not grow a rule.
    assert len(rules["zh.commitment_offer"]["patterns"]) == 10


def test_the_rule_pack_did_not_grow(rules: dict[str, dict[str, Any]]) -> None:
    assert len(rules) == 38


def test_recognition_widened_but_strength_did_not(rules: dict[str, dict[str, Any]]) -> None:
    for rule_id, (weight, information, salience) in FROZEN.items():
        rule = rules[rule_id]
        assert rule["weight"] == weight, rule_id
        assert rule["information_content"] == information, rule_id
        assert rule.get("salience") == salience, rule_id
        assert rule["polarity"] in ("positive", "self_discount"), rule_id


def test_sustained_interaction_is_still_only_interaction(rules: dict[str, dict[str, Any]]) -> None:
    """Widening the family may not turn it into affection."""

    rule = rules["zh.sustained_interaction"]
    assert rule["signal_type"] == "sustained_interaction"
    assert rule["polarity"] == "positive"


def test_self_discount_is_still_an_interpretation(rules: dict[str, dict[str, Any]]) -> None:
    rule = rules["zh.self_discount"]
    assert rule["signal_type"] == "self_discount"
    assert rule["polarity"] == "self_discount"


# --------------------------------------------------------------------------- #
# sustained_interaction
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", SI_POSITIVE)
def test_the_duration_endpoint_habit_and_range_constructions_are_recognised(
    analyzer: NedAnalyzer, text: str
) -> None:
    assert "sustained_interaction" in families(analyzer.analyze_text(text, mode="normal")), text


@pytest.mark.parametrize("text", SI_CONSERVATIVE)
def test_an_input_with_no_anchor_may_stay_unrecognised(analyzer: NedAnalyzer, text: str) -> None:
    """Conservatism is allowed; a wrong match is not."""

    result = analyzer.analyze_text(text, mode="normal")
    assert not any(span.polarity == "positive" for span in result.evidence), text


@pytest.mark.parametrize("text", SI_NEGATIVE)
def test_task_service_and_non_target_interactions_are_not_relationship_evidence(
    analyzer: NedAnalyzer, text: str
) -> None:
    assert "sustained_interaction" not in families(analyzer.analyze_text(text, mode="normal")), text


def test_a_task_clause_does_not_swallow_an_evening_clause(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(
        "昨天我们聊工作聊了三个小时，晚上她又主动陪我聊到凌晨", mode="normal"
    )
    assert "sustained_interaction" in families(result)


def test_a_role_mentioned_in_another_clause_does_not_poison_the_evidence(
    analyzer: NedAnalyzer,
) -> None:
    result = analyzer.analyze_text("朋友介绍我们认识的，后来我们聊到凌晨", mode="normal")
    assert "sustained_interaction" in families(result)


# --------------------------------------------------------------------------- #
# self_discount
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", SD_POSITIVE)
def test_the_hedged_explanation_and_self_doubt_constructions_are_recognised(
    analyzer: NedAnalyzer, text: str
) -> None:
    assert "self_discount" in families(analyzer.analyze_text(text, mode="normal")), text


@pytest.mark.parametrize("text", SD_NEGATIVE)
def test_plain_zhi_shi_is_not_a_discount(analyzer: NedAnalyzer, text: str) -> None:
    """Everyday uses of 只是, and role statements, must stay unsupported."""

    result = analyzer.analyze_text(text, mode="normal")
    assert not any(span.polarity == "self_discount" for span in result.evidence), text


def test_a_role_statement_is_not_forced_into_a_romantic_reading(analyzer: NedAnalyzer) -> None:
    """“她只是我朋友” is ambiguous; it must not be decided for the reader."""

    for text in ("她只是我朋友", "她只是我同事", "她只是我同学"):
        assert families(analyzer.analyze_text(text, mode="normal")) == set(), text


# --------------------------------------------------------------------------- #
# mixed cases: the two families together, and the existing layers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("text", "expected"), CONTRASTIVE)
def test_contrastive_clauses_keep_the_genuine_evidence(
    analyzer: NedAnalyzer, text: str, expected: str
) -> None:
    assert expected in families(analyzer.analyze_text(text, mode="normal")), text


def test_new_evidence_reaches_the_existing_personality_layer(analyzer: NedAnalyzer) -> None:
    """§6: a newly recognised interaction plus a discount must reach its screen."""

    result = analyzer.analyze_text("她每天陪我聊天到很晚，我觉得可能只是习惯了", mode="normal")
    assert {"sustained_interaction", "self_discount"} <= families(result)
    situation, basis, language = (
        p.resolve_situation(result.verdict.code),
        p.reading_basis_present(signal_types=[span.signal_type.value for span in result.evidence]),
        "zh",
    )
    situation = p.screen_situation(
        situation,
        self_discount="self_discount" in families(result),
        positive_evidence=any(span.polarity == "positive" for span in result.evidence),
    )
    assert situation == p.SITUATION_SELF_DISCOUNT_POSITIVE
    screen = p.first_screen(situation, "extreme", language, basis=basis)
    assert "NED：很好，你已经会用了。👍" in " ".join(screen.lines)


def test_generic_interaction_keeps_its_own_screen(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她每天陪我聊天到很晚", mode="normal")
    assert "sustained_interaction" in families(result)
    screen = p.first_screen(p.SITUATION_POSITIVE, "normal", "zh")
    blob = " ".join([screen.title, *screen.lines, screen.reality])
    assert "你已经会用了" not in blob
    assert screen.title == "POSITIVE EVIDENCE DETECTED"


def test_a_reader_positive_conclusion_is_not_a_discount(analyzer: NedAnalyzer) -> None:
    """§11: no discount basis, so no second-person self-service line."""

    result = analyzer.analyze_text("他每天陪我聊天到很晚，我觉得他是喜欢我的", mode="normal")
    assert "sustained_interaction" in families(result)
    assert "self_discount" not in families(result)
    basis = p.reading_basis_present(
        signal_types=[span.signal_type.value for span in result.evidence]
    )
    assert basis is False


def test_boundary_still_outranks_a_discount(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("我本来觉得可能只是人好，但她后来让我别再联系她", mode="normal")
    assert result.verdict.code == "ned.direct_rejection"
    assert p.resolve_situation(result.verdict.code) == p.SITUATION_BOUNDARY


def test_hostility_still_outranks_a_discount(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她骂了我，我还觉得可能只是心情不好", mode="normal")
    assert result.verdict.code == "nea.hostile_expression_insufficient"
    assert p.resolve_situation(result.verdict.code) == p.SITUATION_HOSTILE


def test_recognition_did_not_raise_the_headline_number(analyzer: NedAnalyzer) -> None:
    """A newly matched input uses the rule's own weight, not a boosted one."""

    result = analyzer.analyze_text("她陪我聊了一整晚", mode="normal")
    assert result.signal_strength == 66.0


def test_a_discount_still_carries_no_evidence_strength(analyzer: NedAnalyzer) -> None:
    """§10: self_discount is an interpretation, so it never adds to the reading."""

    discount = analyzer.analyze_text("可能只是在同情我", mode="normal")
    assert discount.signal_strength == 0.0
    assert [span.base_strength for span in discount.evidence] == [70.0]
