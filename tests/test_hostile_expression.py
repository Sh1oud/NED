"""Regression tests for the Hostile Expression family.

Hostility is a family of its own, not a variant of direct_rejection: a boundary
sets a limit on interaction, while a hostile expression is an insulting or
aggressive act. Both may be present at once, and neither may swallow the other.

Core principle: hostility is evidence, but it is not mind-reading. NED may say
"this expression was clearly hostile"; it may not conclude that the relationship
is finished or that someone will always hate you.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from ned.app.core import parser
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import SignalType
from ned.app.core.rules import RuleBook

REPORTED_HOSTILITY = "她怒骂我"
HOSTILE_RULES = ("zh.hostile_expression", "en.hostile_expression")

#: A. hostile content addressed to the reader, B. reported hostile acts.
HOSTILE_TEXTS = [
    "她说去你妈的了",
    "去你妈的",
    "滚你妈的",
    "我操你妈的",
    "你有病吧",
    "你个傻逼",
    "你算什么东西",
    "闭嘴",
    "她怒骂我",
    "他辱骂我",
    "她骂了我一顿",
    "对方冲我破口大骂",
    "她对我恶语相向",
    "她说我是废物",
    "她羞辱我",
    "她说了难听话",
]

#: Joking, banter, game talk, media quotes, meta-discussion, negation, third
#: parties, and the reader's own characterisation of someone else.
NOT_HOSTILE_TEXTS = [
    "她开玩笑骂我笨蛋哈哈",
    "我们打游戏互相骂着玩",
    "电影里有人骂了一句“去你妈的”",
    "我在讨论“怒骂”这个词是什么意思",
    "我在读一本讲辱骂的书",
    "她骂我一句我就哭了，但她是开玩笑的",
    "别骂人行不行",
    "他被人骂了一顿",
    "我们互相调侃而已",
    "他是个混蛋",
    "这个游戏真是垃圾",
    "锅里的水滚烫，我先把火关了",
]

ENGLISH_HOSTILE = ["He insulted me", "She yelled at me", "Fuck you", "You are an idiot"]
ENGLISH_NOT_HOSTILE = [
    "We were trash talking in game",
    "My friend was joking when he called me an idiot, lol",
    "The movie line was fuck you",
    "I am discussing the phrase shut up",
]

MIXED = "去你妈的，别再联系我"


def hostiles(analyzer: NedAnalyzer, text: str) -> list[str]:
    return [
        span.rule_id for span in parser.detect(text, analyzer.book) if span.rule_id in HOSTILE_RULES
    ]


@pytest.mark.parametrize("text", HOSTILE_TEXTS)
def test_hostile_expression_is_detected(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.signal_type == SignalType.HOSTILE_EXPRESSION
    assert result.signal_type != SignalType.NONE
    assert result.verdict.code == "nea.hostile_expression_insufficient"
    assert result.verdict.code != "ned.no_signal"
    assert result.signal_strength >= 80


def test_the_reported_case_is_classified_with_its_own_label(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(REPORTED_HOSTILITY, mode="normal")
    assert result.signal_type == SignalType.HOSTILE_EXPRESSION
    assert result.signal_label == "敌意 / 辱骂表达"
    assert result.verdict.severity == "reject"

    span = next(span for span in result.evidence if span.rule_id == "zh.hostile_expression")
    assert span.polarity == "negative"
    assert span.matched_keywords
    assert span.text in REPORTED_HOSTILITY


def test_hostility_is_a_separate_family_from_direct_rejection(analyzer: NedAnalyzer) -> None:
    """An insult is not a boundary, and the boundary rule no longer claims it."""

    result = analyzer.analyze_text("滚你妈的", mode="normal")
    assert result.signal_type == SignalType.HOSTILE_EXPRESSION
    assert result.signal_type != SignalType.DIRECT_REJECTION
    assert not any(span.rule_id == "zh.direct_rejection" for span in result.evidence)


def test_hostility_carries_a_high_weight_and_a_lower_information_content(
    book: RuleBook,
) -> None:
    """Strong observation, weaker statement about the relationship's trajectory."""

    rule = next(item for item in book.signals if item.id == "zh.hostile_expression")
    boundary = next(item for item in book.signals if item.id == "zh.direct_rejection")
    assert rule.weight >= 85
    assert rule.information_content < rule.weight
    assert rule.information_content < boundary.information_content
    assert rule.amplified_interpretation["zh"] == "我是不是开始觉得，对方已经彻底否定我了？"
    for pattern in rule.patterns + rule.exclude:
        assert parser.compile_pattern(pattern)


@pytest.mark.parametrize("text", NOT_HOSTILE_TEXTS + ENGLISH_NOT_HOSTILE)
def test_contexts_that_are_not_hostility(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.signal_type != SignalType.HOSTILE_EXPRESSION, f"{text!r} was over-read"
    assert result.verdict.code != "nea.hostile_expression_insufficient"
    assert hostiles(analyzer, text) == []


@pytest.mark.parametrize("text", ENGLISH_HOSTILE)
def test_english_hostility_is_detected(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.language == "en"
    assert result.signal_type == SignalType.HOSTILE_EXPRESSION
    assert result.verdict.code == "nea.hostile_expression_insufficient"


def test_hostility_is_not_mind_reading(analyzer: NedAnalyzer) -> None:
    """NED reports the act, and refuses the conclusion about the person."""

    result = analyzer.analyze_text(REPORTED_HOSTILITY, mode="normal")
    text = result.verdict.text

    # it reports the input rather than certifying the event
    assert text.startswith("输入报告了明确的敌意或辱骂表达。")
    assert "按输入所述保留这条负向证据" in text
    assert "检测到明确的敌意" not in text

    # it names what the evidence can and cannot support
    assert "不是读心术" in text
    assert "不足以证明这段关系已经结束" in text
    assert "不足以证明对方永远恨你" in text

    assert result.irrational_amplification.startswith("我是不是开始觉得")
    assert "说明" not in result.irrational_amplification


def test_a_boundary_and_hostility_survive_side_by_side(analyzer: NedAnalyzer) -> None:
    """Both cues stay in the evidence, undiscounted, and the boundary headlines."""

    result = analyzer.analyze_text(MIXED, mode="normal")
    by_rule = {span.rule_id: span for span in result.evidence}

    boundary = by_rule.get("zh.direct_rejection")
    hostile = by_rule.get("zh.hostile_expression")
    assert boundary is not None, "the explicit boundary was swallowed"
    assert hostile is not None, "the hostile expression was swallowed"

    # neither cue is de-weighted
    assert boundary.base_strength == 96.0
    assert boundary.information_content == 90.0
    assert hostile.base_strength == 92.0
    assert hostile.information_content == 72.0
    assert result.breakdown.negative_mass > boundary.base_strength
    assert result.breakdown.negative_information > boundary.information_content

    assert result.verdict.code == "ned.direct_rejection"
    assert result.alternative_explanations == []
    assert "边界" in result.reality_check


def test_api_reports_hostility(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"text": REPORTED_HOSTILITY, "mode": "normal"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["signal_type"] == "hostile_expression"
    assert payload["signal_label"] == "敌意 / 辱骂表达"
    assert payload["verdict"]["code"] == "nea.hostile_expression_insufficient"
    assert payload["verdict"]["code"] != "ned.no_signal"
    assert payload["signal_strength"] >= 80
    assert payload["raw_interpretation"] == "输入报告了明确的敌意或辱骂表达。"
    assert any(item["rule_id"] == "zh.hostile_expression" for item in payload["evidence"])
    assert "cannot determine whether someone likes you" in payload["disclaimer"]


def test_hostility_copy_reports_rather_than_verifies(analyzer: NedAnalyzer) -> None:
    """NED relays what the input says; it does not certify that it happened."""

    result = analyzer.analyze_text(REPORTED_HOSTILITY, mode="normal")
    assert result.raw_interpretation == "输入报告了明确的敌意或辱骂表达。"
    assert "对方做出了" not in result.raw_interpretation

    assert result.reality_check.startswith("输入报告了一次明确的敌意或辱骂表达。")
    assert "按输入所述保留这条证据" in result.reality_check
    assert "不对其进行语义降权" in result.reality_check
    assert "不足以概括对方对你的全部态度" in result.reality_check
    assert "不足以宣告这段关系的结局" in result.reality_check

    english = analyzer.analyze_text("He insulted me", mode="normal")
    assert (
        english.raw_interpretation == "The input reports a clearly hostile or abusive expression."
    )
    assert english.reality_check.startswith(
        "The input reports a clearly hostile or abusive expression."
    )
    assert "preserves that evidence as stated" in english.reality_check
    assert "does not determine how the relationship ends" in english.reality_check
