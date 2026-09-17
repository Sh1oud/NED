"""Positive-signal precision firewall.

NED is allowed to answer "I did not understand that". It is not allowed to answer
the opposite of what was written. These tests pin the guards that stop the
positive families from reading a negation, a termination, an existing state, a
non-target speaker or a quoted phrase as evidence of affection.

The guards live in ``signals.json`` as ``exclude`` patterns. The engine drops a
pattern match only when an exclusion region **overlaps** it (``parser.py``), which
is what makes the guards span-local: a negated clause at one end of a sentence
cannot swallow a genuine positive at the other end. Several tests below exist
purely to keep that property.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from ned.app.core.analyzer import NedAnalyzer

RULES = Path(__file__).resolve().parent.parent / "ned" / "app" / "rules" / "signals.json"

#: The families this firewall defends, and the patterns they carry. These lists are
#: pinned on purpose, so any coverage change is a deliberate, reviewable edit: a
#: precision round may add guards, and a later coverage round must update the pin.
FROZEN_PATTERNS: dict[str, list[str]] = {
    "zh.initiation": [
        "(她|他|对方)?主动[^。！？!?，,]{0,3}(找我|联系我|发消息|约我|来|加我)",
        "主动找我",
        "先找我",
        "主动约我",
        "主动发消息",
        "她先发",
    ],
    "zh.commitment_offer": [
        "(想|要|愿意|希望)?和我做男女朋友",
        "做我(男|女)?朋友",
        "当我的?(男|女)朋友",
        "我们在一起(吧)?",
        "在一起吧",
        "处对象",
        "交往吧",
        "你愿意(和我在一?起|做我)",
        # PR-1 (relationship-intent polarity): the two affirmative shapes PR-0 showed were
        # missing. Both carry a positional guard so they only fire when the phrase ends the
        # proposition, and both are subject to the polarity layer.
        "(想|要|愿意|希望)(和|跟|与)(我|你|您)在一起(?=$|[。！？!?，,；;、 ]|了|吧|吗)",
        "要不要(和|跟|与)?(我|你|您)?在一起(?=$|[。！？!?，,；;、 ]|了|吧|吗)",
    ],
    "zh.care": [
        "记得我(爱|喜欢|不吃|不能吃|胃|过敏|怕|讨厌)",
        "关心我",
        "让我(早点睡|多穿|注意身体|别熬夜)",
        "多喝热水",
        "照顾好自己",
        "问我(吃没|冷不冷|累不累|怎么样)",
        "注意安全",
    ],
    "zh.gift": [
        "给我(点|订|叫)(了)?[^。！？!?，,]{0,4}"
        "(外卖|奶茶|咖啡|饭|吃的|宵夜|水果|花|蛋糕|东西|零食)",
        "送我(礼物|东西|花)",
        "给我带(了)?",
        "给我买",
        "请我吃饭",
        "帮我",
    ],
    "zh.daily_goodnight": ["每天(都)?(说)?晚安", "每天都聊", "晚安", "早安"],
}

#: Inputs that used to produce positive evidence while saying the opposite.
NEGATED_INITIATION = (
    "他从来不主动找我",
    "他从不主动联系我",
    "他没有主动约我",
    "他没主动找过我",
    "他从来没有主动给我发消息",
    "他并未主动联系我",
    "不是他主动找的我",
    "他从来不主动约我",
    "他不是很主动找我",
    "他不主动找我了",
    "他不再主动找我了",
    "他最近已经不主动联系我了",
    "他现在不主动找我了",
    "以前会主动找我，现在不会了",
    "我在研究“主动找我”这个说法",
)

GENUINE_INITIATION = (
    "他今天主动找我聊天",
    "他主动约我周末看电影",
    "她主动联系我了",
    "他主动来我家找我了",
    "她先发消息给我的",
)

EXISTING_STATE = (
    "我们在一起半年了",
    "我们在一起两年多了",
    "我们在一起三个月了，他最近有点冷淡",
    "我们在一起了",
    "电影里的台词是：我们在一起吧",
)

GENUINE_OFFER = (
    "做我女朋友吧",
    "我们在一起吧",
    "你愿意和我在一起吗",
    "我们在一起吧，这次我是认真的",
)

NON_TARGET_ACTOR = (
    "我妈让我早点睡",
    "我爸问我吃饭没有",
    "我妈妈让我多穿点",
    "医生让我多喝热水",
    "老师让我早点睡",
    "老板给我买了饭",
    "同事帮我带了咖啡",
    "我朋友让我别熬夜",
    "室友帮我带了东西",
    "我哥让我多喝热水",
    "护士让我多喝水",
    "闺蜜让我早点睡",
    "医生让我注意安全",
)

GENUINE_CARE = (
    "她让我早点睡",
    "他让我别熬夜",
    "她让我多喝热水",
    "她关心我",
    "他给我买了礼物",
    "他帮我搬家",
    "她让我注意安全",
    "他每天早上都跟我说早安",
)


def families(result: Any) -> set[str]:
    return {span.signal_type.value for span in result.evidence}


@pytest.fixture(scope="module")
def analyzer() -> NedAnalyzer:
    return NedAnalyzer()


@pytest.fixture(scope="module")
def rules() -> dict[str, dict[str, Any]]:
    pack = json.loads(RULES.read_text(encoding="utf-8"))
    return {rule["id"]: rule for rule in pack["signals"]}


# --------------------------------------------------------------------------- #
# the firewall is data, and it is only data
# --------------------------------------------------------------------------- #


def test_the_firewall_adds_guards_and_no_coverage(rules: dict[str, dict[str, Any]]) -> None:
    """A precision round may not smuggle in new patterns."""

    for rule_id, expected in FROZEN_PATTERNS.items():
        assert rules[rule_id]["patterns"] == expected, rule_id
        assert rules[rule_id]["exclude"], f"{rule_id} has no guard"


def test_the_rule_pack_still_holds_every_signal(rules: dict[str, dict[str, Any]]) -> None:
    assert len(rules) == 38


def test_the_guards_are_regions_not_bare_words(rules: dict[str, dict[str, Any]]) -> None:
    """A guard must contain the phrase it guards, or it could veto a whole input."""

    for rule_id in ("zh.initiation", "zh.commitment_offer"):
        for pattern in rules[rule_id]["exclude"]:
            assert "主动" in pattern or "在一起" in pattern or "和我做男女朋友" in pattern, (
                rule_id,
                pattern,
            )
    for rule_id in ("zh.care", "zh.gift", "zh.daily_goodnight"):
        guards = rules[rule_id]["exclude"]
        assert any(
            actor in pattern for pattern in guards for actor in ("我妈", "医生", "同事", "朋友")
        ), rule_id
        assert any("从不" in pattern for pattern in guards), rule_id


# --------------------------------------------------------------------------- #
# initiation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", NEGATED_INITIATION)
def test_a_negated_initiation_is_not_evidence(analyzer: NedAnalyzer, text: str) -> None:
    assert "initiation" not in families(analyzer.analyze_text(text, mode="normal")), text


@pytest.mark.parametrize("text", GENUINE_INITIATION)
def test_genuine_initiation_still_fires(analyzer: NedAnalyzer, text: str) -> None:
    assert "initiation" in families(analyzer.analyze_text(text, mode="normal")), text


def test_a_negation_does_not_swallow_a_contrastive_second_clause(analyzer: NedAnalyzer) -> None:
    """The reported risk: the guard must be span-local, not a whole-input veto."""

    result = analyzer.analyze_text("他以前从来不主动找我，但今天主动约我了", mode="normal")
    assert "initiation" in families(result)
    assert "主动约我" in result.raw_interpretation or result.signal_label


def test_a_hedged_first_clause_does_not_swallow_the_second(analyzer: NedAnalyzer) -> None:
    assert "initiation" in families(
        analyzer.analyze_text("他说他不是很主动，但他今天主动找我了", mode="normal")
    )


def test_the_writers_own_initiative_is_not_the_other_persons(analyzer: NedAnalyzer) -> None:
    """“今天我主动约了他” is the reader acting, not evidence about the other person."""

    assert "initiation" not in families(
        analyzer.analyze_text("他不主动，但今天我主动约了他", mode="normal")
    )


def test_a_double_negative_is_not_over_blocked(analyzer: NedAnalyzer) -> None:
    """“他不是不主动找我” says he does take initiative; the guard must not fire."""

    assert "initiation" in families(analyzer.analyze_text("他不是不主动找我", mode="normal"))
    assert "initiation" in families(analyzer.analyze_text("他并非不主动找我", mode="normal"))


# --------------------------------------------------------------------------- #
# commitment: a state is not an offer
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", EXISTING_STATE)
def test_an_existing_state_is_not_an_offer(analyzer: NedAnalyzer, text: str) -> None:
    assert "commitment_offer" not in families(analyzer.analyze_text(text, mode="normal")), text


@pytest.mark.parametrize("text", GENUINE_OFFER)
def test_a_genuine_offer_still_fires(analyzer: NedAnalyzer, text: str) -> None:
    assert "commitment_offer" in families(analyzer.analyze_text(text, mode="normal")), text


def test_a_third_party_relationship_never_enters_our_evidence(analyzer: NedAnalyzer) -> None:
    for text in ("她说她朋友在一起三个月了", "他朋友跟女朋友在一起半年了", "他们已经在一起了"):
        assert "commitment_offer" not in families(analyzer.analyze_text(text, mode="normal")), text


# --------------------------------------------------------------------------- #
# care: the actor has to be the person being analysed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", NON_TARGET_ACTOR)
def test_care_from_someone_else_is_not_romantic_evidence(analyzer: NedAnalyzer, text: str) -> None:
    assert "care" not in families(analyzer.analyze_text(text, mode="normal")), text


@pytest.mark.parametrize("text", GENUINE_CARE)
def test_genuine_care_still_fires(analyzer: NedAnalyzer, text: str) -> None:
    assert "care" in families(analyzer.analyze_text(text, mode="normal")), text


def test_a_relative_in_one_clause_does_not_poison_the_next(analyzer: NedAnalyzer) -> None:
    """The reported risk: the actor guard must be clause-local."""

    for text in (
        "我妈让我早点睡，她也让我早点睡",
        "我妈昨天让我早点睡，但今天他让我早点睡",
        "他说他妈妈不管他，他让我早点睡",
    ):
        assert "care" in families(analyzer.analyze_text(text, mode="normal")), text


def test_a_negated_or_cooling_care_sentence_is_not_evidence(analyzer: NedAnalyzer) -> None:
    for text in ("我妈让我早点睡，他从来不让我早点睡", "医生让我多喝热水"):
        assert "care" not in families(analyzer.analyze_text(text, mode="normal")), text


# --------------------------------------------------------------------------- #
# the firewall must not disturb anything else
# --------------------------------------------------------------------------- #


def test_the_demo_cases_are_untouched(analyzer: NedAnalyzer) -> None:
    """Still-correct positives keep their evidence, so Personality is unaffected."""

    expected = {
        "她主动找我聊了两个小时": "sustained_interaction",
        "她说喜欢我": "explicit_affection",
        "她让我早点睡": "care",
        "他主动约我周末看电影": "initiation",
        "我们在一起吧": "commitment_offer",
    }
    for text, family in expected.items():
        assert family in families(analyzer.analyze_text(text, mode="normal")), text


def test_blocked_inputs_become_unsupported_not_inverted(analyzer: NedAnalyzer) -> None:
    """The firewall's only allowed outcome is silence."""

    for text in ("他从来不主动找我", "我们在一起半年了", "我妈让我早点睡"):
        result = analyzer.analyze_text(text, mode="normal")
        assert not any(span.polarity == "positive" for span in result.evidence), text
