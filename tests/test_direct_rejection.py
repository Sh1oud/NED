"""Regression tests for the Direct Rejection / Boundary Signal.

v0.1.3 answered "他让我滚出去别烦他了" with ``signal_type = none`` and the
``ned.no_signal`` verdict, because the negative rule pack only knew about reply
latency, cold replies, cancelled plans and self-authored conclusions. An
explicitly stated refusal is an observation, not an inference: NED may restore
uncertainty over ambiguous evidence, but it may not deny evidence that was
stated outright.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from ned.app.core import parser
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import SignalType
from ned.app.core.rules import RuleBook

REPORTED_REFUSAL = "他让我滚出去别烦他了"
NEUTRAL = "今天开会开了三个小时，回来路上买了瓶水"

#: Direct imperatives, reported speech and the one-word forms.
REJECTION_TEXTS = [
    "他让我滚出去别烦他了",
    "别烦我",
    "不要再联系我",
    "别来找我",
    "我不想和你说话",
    "离我远点",
    "滚",
    "滚出去",
    "别再给我发消息",
    "别再打扰我",
    "她叫我以后不要再联系她",
    "对方明确说不想再和我说话",
    "他说以后不要再找他了",
    "请你以后不要出现在我面前",
    "别管我了",
]

#: Joking, game talk, discussing the phrase, ordinary uses of the same
#: characters, and sentences that deny or question the wording. None of these is
#: a boundary signal.
NOT_REJECTION_TEXTS = [
    "我朋友开玩笑说滚蛋哈哈",
    "游戏里队友让我滚出去守点",
    "我在讨论“别烦我”这句话是什么意思",
    "锅里的水滚烫，我先把火关了",
    "快点滚去睡觉，明天还要上班",
    "翻滚的云很好看",
    "今天开会开了三个小时，回来路上买了瓶水",
    "他没有让我滚",
    "我从来没说过别烦我",
    "没人让我滚",
    "他是不是想让我滚？",
    "他让我滚了吗？",
]

ENGLISH_REJECTION = "He told me to leave him alone and never contact him again"
ENGLISH_NOT_REJECTION = "My friend was joking when he said get lost, lol"
ENGLISH_DENIED = "He never told me to leave him alone"
ENGLISH_QUESTION = "Did she tell you to leave me alone?"

BOUNDARY_RULES = ("zh.direct_rejection", "en.direct_rejection")


def boundary_spans(analyzer: NedAnalyzer, text: str) -> list[str]:
    return [
        span.rule_id
        for span in parser.detect(text, analyzer.book)
        if span.rule_id in BOUNDARY_RULES
    ]


@pytest.mark.parametrize("text", REJECTION_TEXTS)
def test_explicit_rejection_is_detected(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.signal_type != SignalType.NONE, f"{text!r} was classified as no signal"
    assert result.signal_type == SignalType.DIRECT_REJECTION
    assert result.verdict.code != "ned.no_signal"
    assert result.verdict.code == "ned.direct_rejection"
    assert result.signal_strength >= 80


def test_the_reported_case_is_no_longer_a_no_signal(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(REPORTED_REFUSAL, mode="normal")
    assert result.signal_type == SignalType.DIRECT_REJECTION
    assert result.signal_label == "明确拒绝 / 边界表达"
    assert result.verdict.code == "ned.direct_rejection"
    assert result.verdict.severity == "warning"
    assert result.raw_interpretation.strip()
    assert result.language == "zh"

    span = next(span for span in result.evidence if span.rule_id == "zh.direct_rejection")
    assert span.polarity == "negative"
    assert span.base_strength >= 90
    assert span.information_content >= 80
    assert span.matched_keywords, "the matched wording must stay traceable to the rule"
    # The boundary is read where it was said, not stretched over the sentence.
    assert span.text in REPORTED_REFUSAL


def test_boundary_evidence_is_far_above_the_no_signal_baseline(analyzer: NedAnalyzer) -> None:
    rejection = analyzer.analyze_text(REPORTED_REFUSAL, mode="normal")
    neutral = analyzer.analyze_text(NEUTRAL, mode="normal")
    assert neutral.signal_type == SignalType.NONE
    assert neutral.signal_strength == 0.0
    assert rejection.signal_strength > neutral.signal_strength + 50


@pytest.mark.parametrize("text", NOT_REJECTION_TEXTS)
def test_ordinary_uses_of_the_same_words_are_not_boundaries(
    analyzer: NedAnalyzer, text: str
) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.signal_type != SignalType.DIRECT_REJECTION, f"{text!r} was over-read"
    assert result.verdict.code != "ned.direct_rejection"
    assert boundary_spans(analyzer, text) == []
    assert result.signal_strength < 80


def test_context_exclusions_suppress_the_rule(book: RuleBook) -> None:
    for text in (
        "我朋友开玩笑说滚蛋哈哈",
        "游戏里队友让我滚出去守点",
        "我在讨论“别烦我”这句话是什么意思",
        "他没有让我滚",
        "我从来没说过别烦我",
        "他是不是想让我滚？",
    ):
        found = {span.rule_id for span in parser.detect(text, book)}
        assert "zh.direct_rejection" not in found, text


@pytest.mark.parametrize(
    "text",
    [
        "我没心情，别烦我",
        "别再联系我好吗？",
        "她说让我滚，我很难受",
        "请你以后不要出现在我面前",
    ],
)
def test_unrelated_words_do_not_switch_a_real_boundary_off(
    analyzer: NedAnalyzer, text: str
) -> None:
    """The negation and question guards must not cost a real refusal.

    "我没心情，别烦我" carries an unrelated 没, and "别再联系我好吗？" is a
    politely softened refusal: both are still boundaries.
    """

    result = analyzer.analyze_text(text, mode="normal")
    assert result.signal_type == SignalType.DIRECT_REJECTION
    assert result.verdict.code == "ned.direct_rejection"


@pytest.mark.parametrize("mode", ["normal", "scientific", "extreme"])
def test_a_stated_boundary_is_never_explained_away(analyzer: NedAnalyzer, mode: str) -> None:
    """No mode may turn an explicit refusal into a fuzzy signal."""

    result = analyzer.analyze_text("不要再联系我", mode=mode)  # type: ignore[arg-type]
    assert result.verdict.code == "ned.direct_rejection"
    assert result.alternative_explanations == [], "the boundary was offered an escape route"
    assert result.negative_evidence_amplification < 20
    assert "边界" in result.reality_check
    notes = " ".join(result.mode_notes)
    assert "explicit boundary" in notes
    assert "equally not a measurement" not in notes


MIXED = "她说喜欢我，然后让我以后别再联系她了"


@pytest.mark.parametrize("mode", ["normal", "scientific", "extreme"])
def test_positive_evidence_does_not_buy_the_boundary_an_escape(
    analyzer: NedAnalyzer, mode: str
) -> None:
    """Good news in the same message must not soften the refusal."""

    result = analyzer.analyze_text(MIXED, mode=mode)  # type: ignore[arg-type]
    assert result.verdict.code == "ned.direct_rejection"
    assert not result.verdict.code.startswith("ped.")
    assert "边界" in result.reality_check
    assert boundary_spans(analyzer, MIXED)
    # The asymmetry NED did detect is still reported, just not as the headline.
    assert result.asymmetry is not None
    assert result.asymmetry_reality_check.strip()


def test_a_boundary_outranks_the_asymmetry_headline(analyzer: NedAnalyzer) -> None:
    """A stated refusal is not weak negative evidence being amplified.

    Since the comparability gate landed, such a pair does not even reach a
    severity band: an explicit boundary is a different evidence class, so NED
    declines the comparison instead of scoring the boundary as overreach.
    """

    result = analyzer.analyze_text(MIXED, mode="extreme")
    assert result.breakdown.asymmetry_score is None
    assert result.asymmetry is not None
    assert result.asymmetry.comparison_applicable is False
    assert result.asymmetry.comparison_reason == "explicit_boundary_not_comparable"
    assert result.asymmetry.asymmetry_label == "NOT DIRECTLY COMPARABLE"
    assert result.verdict.code == "ned.direct_rejection"
    assert "weak negative evidence" not in result.verdict.text


def test_neds_own_capacity_verdict_still_outranks_a_boundary(analyzer: NedAnalyzer) -> None:
    """Documented precedence for the one case a boundary does not headline.

    When NED has run out of explanations the chaos verdict still wins, because
    that sentence is about NED and not about the refusal. The refusal itself
    must survive unharmed: present in the evidence, present in the reality
    check, not de-weighted, and with no escape hypothesis attached to it.
    """

    text = "我们结婚吧，然后她让我滚出去"
    history = ["我们结婚吧", "我们已经结婚了"]
    result = analyzer.analyze_text(text, mode="extreme", history=history)
    assert result.verdict.code == "ned.capacity_exhausted"
    assert result.breakdown.escape_capacity >= 0.95

    # 1. the refusal is still a first-class piece of evidence
    spans = [span for span in result.evidence if span.rule_id == "zh.direct_rejection"]
    assert len(spans) == 1, "the refusal must survive in the evidence list"
    span = spans[0]
    assert span.label == "明确拒绝 / 边界表达"
    assert span.polarity == "negative"

    # 2. it is not de-weighted: full weight, full information, counted in full
    assert span.base_strength == 96.0
    assert span.information_content == 90.0
    assert span.weight == span.base_strength
    assert result.breakdown.negative_mass == 96.0
    assert result.breakdown.negative_information == 90.0
    assert result.negative_evidence_amplification < 20

    # 3. the reality check shown is the boundary one, not a generic dismissal
    assert "边界" in result.reality_check
    assert "不对这条证据降权" in result.reality_check
    assert "不构成关于态度的证据" not in result.reality_check

    # 4. no semantic escape is generated for the refusal: the hypothesis set is
    #    exactly the one produced without the refusal in the input, and no
    #    hypothesis re-interprets the refusal wording.
    without = analyzer.analyze_text("我们结婚吧", mode="extreme", history=history)
    assert result.alternative_explanations, "the positive overload still produces escapes"
    assert [item.hypothesis for item in result.alternative_explanations] == [
        item.hypothesis for item in without.alternative_explanations
    ], "the refusal added an escape hypothesis"
    assert not any(
        token in item.hypothesis
        for item in result.alternative_explanations
        for token in ("明确拒绝", "边界表达", "让我滚", "滚出去", "别烦")
    ), "an escape hypothesis re-interpreted the refusal"


def test_boundary_reality_check_claims_no_attribution(analyzer: NedAnalyzer) -> None:
    """NED detects that a boundary was stated, not who stated it.

    A boundary the user set themselves is still reported as a boundary signal,
    so the reality check must not assert whose choice it was.
    """

    result = analyzer.analyze_text("我让她别再来找我了", mode="normal")
    assert result.signal_type == SignalType.DIRECT_REJECTION
    assert result.verdict.code == "ned.direct_rejection"
    assert "对方的选择" not in result.reality_check
    assert "你的价值" not in result.reality_check
    assert "边界" in result.reality_check


def test_boundary_rule_mirrors_the_latency_rule(book: RuleBook) -> None:
    """The latency rule's asymmetry must not be copied onto a stated boundary."""

    latency = next(rule for rule in book.signals if rule.id == "zh.response_latency")
    for rule_id in BOUNDARY_RULES:
        rule = next(item for item in book.signals if item.id == rule_id)
        assert rule.signal_type == SignalType.DIRECT_REJECTION
        assert rule.polarity == "negative"
        assert rule.weight >= 90
        assert rule.information_content > latency.information_content
        assert rule.information_content >= 0.8 * rule.weight
        assert rule.label_for("zh") == "明确拒绝 / 边界表达"
        for pattern in rule.patterns + rule.exclude:
            assert parser.compile_pattern(pattern)


def test_english_boundary_is_detected_and_jokes_are_not(analyzer: NedAnalyzer) -> None:
    rejection = analyzer.analyze_text(ENGLISH_REJECTION, mode="normal")
    assert rejection.language == "en"
    assert rejection.signal_type == SignalType.DIRECT_REJECTION
    assert rejection.verdict.code == "ned.direct_rejection"

    for text in (ENGLISH_NOT_REJECTION, ENGLISH_DENIED, ENGLISH_QUESTION):
        result = analyzer.analyze_text(text, mode="normal")
        assert result.signal_type != SignalType.DIRECT_REJECTION, text
        assert result.verdict.code != "ned.direct_rejection", text


def test_api_reports_the_boundary(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"text": REPORTED_REFUSAL, "mode": "normal"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["signal_type"] == "direct_rejection"
    assert payload["signal_label"] == "明确拒绝 / 边界表达"
    assert payload["verdict"]["code"] == "ned.direct_rejection"
    assert payload["verdict"]["code"] != "ned.no_signal"
    assert payload["signal_strength"] >= 80
    assert any(item["rule_id"] == "zh.direct_rejection" for item in payload["evidence"])
    assert "cannot determine whether someone likes you" in payload["disclaimer"]


def test_boundary_signal_type_is_exposed_to_the_api(client: TestClient) -> None:
    payload = client.get("/api/modes").json()
    assert payload, "the API must stay reachable with the new signal type in place"
    assert client.get("/api/health").json()["status"] == "ok"


#: Wording that would present the amplified reading as NED's own finding.
CERTAINTY_WORDS = ("说明", "证明", "已经确定", "可以断定")

#: Wording that attributes the reading to the reader's own mind instead.
SUBJECTIVE_MARKERS = ("我是不是开始觉得", "可能", "觉得", "让我觉得", "脑内放大后的版本")

#: Extreme conclusions the reading may contain, but only as the content of that
#: attribution, never as an assertion of its own.
EXTREME_CLAIMS = ("已经没有任何余地", "已经结束", "彻底没有余地")


@pytest.mark.parametrize("mode", ["normal", "scientific", "extreme"])
def test_amplified_reading_is_framed_as_the_users_overreading(
    analyzer: NedAnalyzer, mode: str
) -> None:
    """NEA displays the inflated interpretation under test, not a conclusion.

    The reading may carry an extreme conclusion, but only inside a subjective
    frame: as a bare assertion it would read as NED's own finding.
    """

    result = analyzer.analyze_text(REPORTED_REFUSAL, mode=mode)  # type: ignore[arg-type]
    amplified = result.irrational_amplification
    assert amplified.strip(), "the NEA panel needs a reading to frame"

    for word in CERTAINTY_WORDS:
        assert word not in amplified, f"{word!r} reads as NED's own conclusion: {amplified}"

    marker_index = min(
        (amplified.index(marker) for marker in SUBJECTIVE_MARKERS if marker in amplified),
        default=None,
    )
    assert marker_index is not None, f"the reading is not attributed to the reader: {amplified}"
    for claim in EXTREME_CLAIMS:
        if claim in amplified:
            assert amplified.index(claim) > marker_index, (
                f"{claim!r} is asserted instead of attributed: {amplified}"
            )

    assert result.verdict.code == "ned.direct_rejection"


def test_the_extreme_claim_stays_inside_the_subjective_frame(analyzer: NedAnalyzer) -> None:
    """Pin the requested wording: the feeling is the frame, the claim is its content."""

    result = analyzer.analyze_text(REPORTED_REFUSAL, mode="normal")
    amplified = result.irrational_amplification
    assert amplified == "我是不是开始觉得，这段关系已经彻底没有余地了？"
    assert amplified.startswith("我是不是开始觉得")
    assert result.verdict.code == "ned.direct_rejection"


def test_english_amplified_reading_avoids_certainty_claims(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(ENGLISH_REJECTION, mode="normal")
    amplified = result.irrational_amplification.lower()
    for word in ("means", "proves", "definitely", "certainly", "it is over"):
        assert word not in amplified, f"{word!r} in {amplified!r}"
    assert "am i starting to feel" in amplified, f"the reading is not attributed: {amplified}"


def test_reality_check_keeps_respecting_the_boundary(analyzer: NedAnalyzer) -> None:
    """The boundary is respected, not de-weighted and not read as a verdict on you."""

    result = analyzer.analyze_text(REPORTED_REFUSAL, mode="normal")
    check = result.reality_check
    assert "尊重" in check, "the reality check must say the boundary deserves respect"
    assert "不对这条证据降权" in check
    assert "不足以推断" in check
    assert "不好" in check
    assert result.verdict.code == "ned.direct_rejection"


# --------------------------------------------------------------------------- #
# CG-7: a hedged claim is an inference, not a stated boundary
# --------------------------------------------------------------------------- #

#: The reader's own hedged reading. The modal (可能/也许/…/我觉得) marks an
#: inference, so the input does not report that a boundary was stated. NED may
#: restore uncertainty here; it may not report an explicit refusal or an explicit
#: "let's be friends".
MODAL_CLAIMS = (
    # the rejection wording the review opened with
    "我可能被拒绝了",
    "我也许被拒绝了",
    "我或许被拒绝了",
    "我大概被拒绝了",
    "我好像被拒绝了",
    "我应该被拒绝了吧",
    "我觉得我可能被拒绝了",
    "她可能拒绝了我",
    "他大概拒绝了我",
    "我觉得她可能拒绝了我",
    # the same structure in the rest of the family (closure audit)
    "她可能想说我们还是做朋友吧",
    "他好像是想说做朋友吧",
    "他大概是只想做朋友",
    "她也许想保持点距离",
    "她可能想让我别再找她了",
    "他大概说过别再给我发消息",
    "她可能不想和我说话了",
    "她可能说过以后不要再联系我了",
    "他可能说过不要再出现在我面前",
    "他大概是想离我远点",
    "她可能不再和我联系了",
    "他可能想让我滚",
    "他可能是想滚了",
    "我觉得她想做朋友吧",
    "我感觉他不想和我说话了",
)

#: The same wording without the modal reports something that happened. Every one
#: of these must stay a boundary, including the ones whose modal sits in another
#: clause and the ones where the modal belongs to a different predicate.
FACTUAL_BOUNDARIES = (
    "我表白被拒了",
    "我表白被拒绝了",
    "她直接拒绝了我",
    "他明确拒绝了我",
    "她昨天拒绝了我",
    "她说我们还是做朋友吧",
    "她说我们不合适",
    "她说以后别联系了",
    "我可能想多了，但我表白被拒了",
    "他可能生气了但让我滚了",
    "她可能不喜欢我但也让我做朋友吧",
    "我可能想多了，但她明确让我别联系她",
)

#: The family's judgement wording keeps its judgement framing: "我觉得我们不合适"
#: is a boundary, so the judgement guard carries the uncertainty markers only.
JUDGEMENT_BOUNDARIES = (
    "我觉得我们不合适",
    "我感觉我们不合适",
    "她说我们不合适",
    "他明确说我们不合适",
)


def modal_guards(book: RuleBook) -> list[str]:
    rule = next(item for item in book.signals if item.id == "zh.direct_rejection")
    return [pattern for pattern in rule.exclude if "可能|也许" in pattern]


def test_the_family_carries_exactly_two_modal_guards(book: RuleBook) -> None:
    """Closure: one behaviour guard and one judgement guard, no third copy.

    The narrow guard the review started with was absorbed into the behaviour
    guard, so the same modal vocabulary is not maintained in several excludes.
    """

    guards = modal_guards(book)
    assert len(guards) == 2, guards
    behaviour = next(pattern for pattern in guards if "做朋友" in pattern)
    judgement = next(pattern for pattern in guards if "不合(适|来)" in pattern)
    for token in ("被拒", "被绝", "拒绝了我"):
        assert token in behaviour, token
    assert "我觉得|我感觉|我认为" not in judgement
    for pattern in guards:
        assert parser.compile_pattern(pattern)


@pytest.mark.parametrize("text", MODAL_CLAIMS)
def test_a_modal_claim_is_not_a_boundary(analyzer: NedAnalyzer, text: str) -> None:
    """An uncertain inference may not be shown as an explicit boundary.

    The defect: "我可能被拒绝了" reached the boundary screen, whose evidence line
    read 明确拒绝 / 边界表达 and whose quality read 明确. The closure audit found the
    same structure across the rest of the family.
    """

    result = analyzer.analyze_text(text, mode="normal")
    assert result.signal_type != SignalType.DIRECT_REJECTION, text
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text
    assert "明确拒绝" not in result.reality_check, text
    assert "说出口的边界" not in result.reality_check, text


@pytest.mark.parametrize("text", FACTUAL_BOUNDARIES)
def test_a_factual_boundary_is_still_a_boundary(analyzer: NedAnalyzer, text: str) -> None:
    """The guards may not cost a real refusal, in any clause arrangement."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.signal_type == SignalType.DIRECT_REJECTION, text
    assert result.verdict.code == "ned.direct_rejection", text
    assert boundary_spans(analyzer, text), text


@pytest.mark.parametrize("text", JUDGEMENT_BOUNDARIES)
def test_the_judgement_wording_keeps_its_framing(analyzer: NedAnalyzer, text: str) -> None:
    """ "我觉得我们不合适" is a boundary; only a hedge around it is not."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text
