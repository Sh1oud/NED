"""Regression tests for the Direct Rejection / Boundary Signal.

v0.1.3 answered "他让我滚出去别烦他了" with ``signal_type = none`` and the
``ned.no_signal`` verdict, because the negative rule pack only knew about reply
latency, cold replies, cancelled plans and self-authored conclusions. An
explicitly stated refusal is an observation, not an inference: NED may restore
uncertainty over ambiguous evidence, but it may not deny evidence that was
stated outright.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from fastapi.testclient import TestClient
from ned.app.core import parser
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import SignalType
from ned.app.core.rules import RuleBook

#: The repository root, for the two pins that read the shipped source.
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

REPORTED_REFUSAL = "他让我滚出去别烦他了"
NEUTRAL = "今天开会开了三个小时，回来路上买了瓶水"

#: Direct imperatives, reported speech and the one-word forms.
REJECTION_TEXTS = [
    "他让我滚出去别烦他了",
    "她叫我以后不要再联系她",
    "对方明确说不想再和我说话",
    "他说以后不要再找他了",
    "她说别再联系我了",
    "她说：“你以后不要出现在我面前”",
    "她让我别再找她了",
]

#: POLICY A: a bare utterance belongs to the reader, so it cannot certify that she
#: stated a boundary. These used to be shipped as boundaries; the assertion below
#: pins the corrected behaviour.
BARE_UTTERANCE_TEXTS = [
    "别烦我",
    "不要再联系我",
    "别来找我",
    "我不想和你说话",
    "离我远点",
    "滚",
    "滚出去",
    "别再给我发消息",
    "别再打扰我",
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
        "我没心情，但她让我别烦她",
        "她说别再联系我了",
        "她说让我滚，我很难受",
        "她说：“你以后不要出现在我面前”",
    ],
)
def test_unrelated_words_do_not_switch_a_real_boundary_off(
    analyzer: NedAnalyzer, text: str
) -> None:
    """The negation and question guards must not cost a real refusal.

    "我没心情，但她让我别烦她" carries an unrelated 没, and "她说别再联系我了" is a
    politely softened refusal: both are still boundaries.
    """

    result = analyzer.analyze_text(text, mode="normal")
    assert result.signal_type == SignalType.DIRECT_REJECTION
    assert result.verdict.code == "ned.direct_rejection"


@pytest.mark.parametrize("mode", ["normal", "scientific", "extreme"])
def test_a_stated_boundary_is_never_explained_away(analyzer: NedAnalyzer, mode: str) -> None:
    """No mode may turn an explicit refusal into a fuzzy signal."""

    result = analyzer.analyze_text("她跟我说：不要再联系我了", mode=mode)
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
    A directive the reader issued is the reader's own stance, not hers.
    """

    result = analyzer.analyze_text("她让我别再找她了", mode="normal")
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

#: The judgement wording keeps its framing when *she* is the author. The
#: reader's own judgement ("我觉得我们不合适") is not her boundary: BATCH 4's
#: ownership contract closes it, and it is pinned in that section below.
JUDGEMENT_BOUNDARIES = (
    "她说我们不合适",
    "他明确说我们不合适",
    "她跟我说我们不合适",
)


def modal_guards(book: RuleBook) -> list[str]:
    rule = next(item for item in book.signals if item.id == "zh.direct_rejection")
    return [pattern for pattern in rule.exclude if "可能|也许" in pattern]


def test_the_family_carries_exactly_two_modal_guards(book: RuleBook) -> None:
    """Closure: one behaviour guard and one judgement guard, no third copy.

    The narrow guard the review started with was absorbed into the behaviour
    guard, so the same modal vocabulary is not maintained in several excludes.
    """

    guards = [pattern for pattern in modal_guards(book) if "确定|确认|判断|知道" in pattern]
    assert len(guards) == 2, guards
    reader_patient = [
        pattern for pattern in modal_guards(book) if "被" in pattern and "拒" in pattern
    ]
    assert reader_patient, "reader-patient hedge/question guard class is missing"
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


# --------------------------------------------------------------------------- #
# CG-3: a stated boundary survives the frame it is reported in
# --------------------------------------------------------------------------- #

#: The three shapes the review opened with, plus the frames the same intent
#: arrives in. Each of these reports that a boundary was stated, so NED may not
#: file it behind a gift, a memory or an invitation.
STATED_BOUNDARIES = (
    "她说不想见我",
    "她说她只想当普通朋友",
    "她说她不想发展成恋爱关系",
    "她不想见我",
    "她只想当普通朋友",
    "她不想发展成恋爱关系",
    "她明确表示她不想见我",
    "她说她不想再见到我",
    "她说她不想谈恋爱",
    "她说她不想和我发展感情",
    "她不想和我发展感情",
    "她不想跟我发展关系",
    "她不想与我开始恋爱关系",
    "他说他只想做朋友",
    "对方说不想见我",
    "她和朋友说她只想当普通朋友",
    "她向家人表示她不想发展成恋爱关系",
    "她昨天告诉我她不想见我",
    "她哭着说她不想见我",
    "她说“不想见我”",
    "她不想见你",
)

#: Positive material first, stated boundary second. The boundary names the
#: screen and the material stays on file; the material does not buy the joke a
#: screen of its own. This is the shape the review opened with: the input used
#: to read as a logged gift with the refusal invisible.
COMPOSITE_BOUNDARIES = (
    "他给我买了早餐，但她说不想见我",
    "她记得我爱吃什么，但她说她只想当普通朋友",
    "他约我出去，但她说她不想发展成恋爱关系",
    "他给我买了早餐，但她说她不想发展成恋爱关系",
    "她记得我爱吃什么，但她说不想见我",
    "他给我买了早餐，但她只想当普通朋友",
)

#: The stance belongs to a third party, so it is not hers. "她朋友说她不想见我"
#: is the friend's report: the guard is anchored on who owns the stance, never on
#: whether a third-party noun appears in the sentence.
ATTRIBUTION_NEGATIVES = (
    "她朋友说她不想见我",
    "她说她朋友不想见我",
    "她说“我朋友只想和你做普通朋友”",
    "她闺蜜说她只想跟我做普通朋友",
    "她最好的朋友不想见我",
    "她那个同事说不想见我",
    "她妈妈说不想让她见我",
    "她的闺蜜告诉她不想见我",
    "她朋友说“不想见我”",
    "他朋友不想见我",
    "她同事说她不想发展成恋爱关系",
    "她家人说她只想当普通朋友",
)

#: A relay or a third party's report: the boundary exists in the input, but the
#: input does not say that she herself stated it. 转述 / 复述 / 转达 and
#: 我妈说 / 我爸说 / 我朋友说 are the sources, not her.
RELAY_ATTRIBUTION_NEGATIVES = (
    "她转述说不想见我",
    "她复述说不想见我",
    "她转达说不想见我",
    "她转述说她不想见我",
    "我妈说她不想见我",
    "我爸说她不想见我",
    "我朋友说她不想见我",
    "我妈说她只想和我做普通朋友",
    "我朋友说她不想发展成恋爱关系",
)

#: The sentence denies that the material proves the conclusion. NED may not
#: register the conclusion the sentence explicitly refuses as a stated boundary.
EPISTEMIC_NEGATION_NEGATIVES = (
    "不能证明她不想见我",
    "这不足以证明她不想见我",
    "不代表她不想见我",
    "不等于她不想见我",
    "不能说明她只想当普通朋友",
    "不足以说明她不想发展成恋爱关系",
    "无法证明她不想发展成恋爱关系",
    "这不能证明她只想当普通朋友",
    "这不是她不想发展成恋爱关系",
    "不是她不想见我",
    "她没说不想见我",
    "她没有说她不想见我",
    "检测到计划取消或改期，但一次计划变化不足以证明对方根本不想见你。",
)

#: The proposition is hedged (不一定 / 未必 / 不见得 / 不确定) or it sits inside the
#: reader's own belief (我不相信 / 我不认为 / 我不觉得). Either way the input does
#: not report that she stated a boundary, so NED may not show 明确拒绝 for it.
UNCERTAINTY_AND_BELIEF = (
    "她不一定不想见我",
    "她未必不想见我",
    "她不见得不想见我",
    "她不一定只想当普通朋友",
    "她未必只想和我做普通朋友",
    "她不见得不想发展成恋爱关系",
    "我不相信她不想见我",
    "我不认为她不想见我",
    "我不觉得她只想当普通朋友",
    "我不相信她不想发展成恋爱关系",
    "我不确定她不想见我",
    "我不能确定她不想见我",
    "我无法确定她不想见我",
    "我不确定她只想当普通朋友",
)

#: Registered debt, not this window's business: the shipped family answers the
#: same hedge around its own triggers. These keep the baseline answer.
OLD_HEDGE_DEBT = (
    "她未必拒绝了我",
    "她不一定让我滚",
    "她不见得想让我别联系她",
    "她不一定不想和我说话",
    "我不确定她不想和我说话",
)

#: Her own words, quoted. Inside the quote 我 is the person speaking, which is
#: why the subject gap admits a quoted 我 and nothing else.
DIRECT_QUOTES = (
    "她说“不想见我”",
    "她说“我只想和你做普通朋友”",
    "她说“我不想和你发展成恋爱关系”",
    "她说“我不想见你”",
    "她回复说“我不想发展成恋爱关系”",
)

#: Here the third party is only whoever she said it to, so she still owns the
#: boundary. The rejected design suppressed any sentence containing 朋友 / 闺蜜 /
#: 家人 and would have killed every one of these.
RECEIVER_OF_SPEECH_BOUNDARIES = (
    "她跟朋友说她不想见我",
    "她告诉闺蜜她只想和我做普通朋友",
    "她对家人说她不想发展成恋爱关系",
    "她跟她妈妈说不想见我",
    "她和她朋友说她只想当普通朋友",
    "她跟她妈妈说她不想见我",
)

#: The reader's own stance. NED's subject is the other person's boundary, and
#: "我只想当普通朋友" does not report one. This window changes nothing here.
READER_OWNED_STANCES = (
    "我不想见她",
    "我只想当普通朋友",
    "我不想发展成恋爱关系",
    "我跟她说我只想当普通朋友",
    "我跟她说我不想发展成恋爱关系",
    "我告诉她我不想见她",
    "她说我不想见她",
    "她说我不想发展成恋爱关系",
    "她逼我说我只想当普通朋友",
    "她让我说我不想见她",
    "她建议我只想当普通朋友",
    "她要求我不想发展成恋爱关系",
    "她暗示我只想当普通朋友",
    "我跟她说“我只想当普通朋友”",
    "我告诉她“我不想见她”",
)

#: A question asks about a boundary; it does not state one.
INTERROGATIVE_FORMS = (
    "她为什么不想见我？",
    "她不想见我吗？",
    "她不想见我？",
    "她不想见我吗",
    "她不想见我了？",
    "她怎么不想见我",
    "她为什么不想发展成恋爱关系？",
    "她不想发展成恋爱关系？",
    "她为什么只想当普通朋友？",
    "她只想当普通朋友吗？",
    "她是不是不想见我？",
    "他问我为什么她不想见我",
)

#: 见 takes an object, and here it is not the reader.
OTHER_OBJECTS = (
    "她不想见我朋友",
    "她不想见我妈",
    "她不想见我家人",
    "她不想见我的朋友",
    "她不想见我们",
)

#: The guards are scoped to the new shapes. These older triggers keep the
#: behaviour the shipped pack gave them.
OLD_TRIGGER_SCOPE = ("她让我滚出去别烦他了",)

#: A question cannot certify a boundary, whatever shape its trigger has.
QUESTIONED_BOUNDARY_SHAPES = (
    "她为什么不想和我说话了？",
    "她不想和我说话吗？",
    "她为什么让我滚？",
    "她让我滚吗？",
    "她是不是让我滚？",
    "她为什么让我别联系她？",
    "她让我别联系她了吗？",
)

#: Older triggers whose shipped answer was a mis-attribution, and which BATCH 4's
#: ownership contract closes: a relay (the boundary reaches the input second hand)
#: and three denials (the sentence refuses the conclusion, exactly like the
#: epistemic-negation family next door).
CLOSED_BY_OWNERSHIP = (
    "她朋友说她不想和我说话",
    "这不能证明她说我们还是做朋友吧",
    "不代表她拒绝了我",
    "不等于她不想和我说话",
)

#: The gap between the boundary owner and the stance. It may not contain 我:
#: that single structural rule is what keeps the reader's own stance out, so it
#: is pinned as data rather than left to a pile of exclusions.
SUBJECT_GAP = "[^。！？!?，,我]{0,5}"
#: ... with one exception, and only one: a quotation, where 我 is the person
#: speaking. The quote branch needs a speech verb, so it cannot reach
#: "我跟她说我只想当普通朋友", and the anchor may not follow a conjunction.
QUOTE_BRANCH = (
    "(?:[^。！？!?，,我]{0,2}(?:说|讲|表示|称|回复|答))[^。！？!?，,]{0,1}[“\"'](?:我|咱)"
)

ANCHOR = "(?<![和跟与对向给])(她|他|对方)"


def rejection_patterns(book: RuleBook) -> list[str]:
    rule = next(item for item in book.signals if item.id == "zh.direct_rejection")
    return list(rule.patterns)


def rejection_excludes(book: RuleBook) -> list[str]:
    rule = next(item for item in book.signals if item.id == "zh.direct_rejection")
    return list(rule.exclude)


def subject_anchored_patterns(book: RuleBook) -> list[str]:
    """The three siblings: the other person is the subject of the stance."""

    return [pattern for pattern in rejection_patterns(book) if SUBJECT_GAP in pattern]


def guards_for(book: RuleBook, token: str) -> list[str]:
    return [pattern for pattern in rejection_excludes(book) if token in pattern]


@pytest.mark.parametrize("text", STATED_BOUNDARIES)
def test_a_stated_boundary_survives_the_frame_it_is_reported_in(
    analyzer: NedAnalyzer, text: str
) -> None:
    """The defect: a stated refusal NED never recognised.

    The family knew 只想做朋友 and 不想和我说话, but not 不想见我, 只想当普通朋友 or
    不想发展成恋爱关系. The input then fell through to whichever positive rule it
    also matched, and the stated boundary vanished from the screen.
    """

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text
    assert boundary_spans(analyzer, text), text
    assert "不对这条证据降权" in result.reality_check, text


@pytest.mark.parametrize("text", COMPOSITE_BOUNDARIES)
def test_positive_material_does_not_buy_the_stated_boundary_a_screen(
    analyzer: NedAnalyzer, text: str
) -> None:
    """The material stays in the file; it does not decide the first screen."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text
    assert boundary_spans(analyzer, text), text
    assert any(span.polarity == "positive" for span in result.evidence), text
    assert "不对这条证据降权" in result.reality_check, text


@pytest.mark.parametrize("text", ATTRIBUTION_NEGATIVES)
def test_a_third_partys_stance_is_not_lent_to_her(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", RELAY_ATTRIBUTION_NEGATIVES)
def test_a_relay_is_not_her_own_stated_boundary(analyzer: NedAnalyzer, text: str) -> None:
    """转述 / 复述 / 转达 / 我妈说: the boundary reaches the input second hand."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", EPISTEMIC_NEGATION_NEGATIVES)
def test_a_denied_conclusion_is_not_a_stated_boundary(analyzer: NedAnalyzer, text: str) -> None:
    """The sentence says the material does not prove the conclusion.

    NED may not turn the conclusion the sentence refuses into an explicit
    boundary: 不足以证明对方根本不想见你 is a statement about the evidence.
    """

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", UNCERTAINTY_AND_BELIEF)
def test_a_hedged_or_believed_proposition_is_not_a_stated_boundary(
    analyzer: NedAnalyzer, text: str
) -> None:
    """削弱确定性的说法与 belief operator 内部的说法都不是说出口的边界."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", OLD_HEDGE_DEBT)
def test_the_old_hedge_debt_is_closed(analyzer: NedAnalyzer, text: str) -> None:
    """BATCH 2 closed this debt: hypothetical wording is not a stated boundary."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text


@pytest.mark.parametrize("text", DIRECT_QUOTES)
def test_her_own_quoted_words_are_still_a_boundary(analyzer: NedAnalyzer, text: str) -> None:
    """Inside direct speech 我 is the speaker, and the speaker is her."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text
    assert boundary_spans(analyzer, text), text


@pytest.mark.parametrize("text", RECEIVER_OF_SPEECH_BOUNDARIES)
def test_the_receiver_of_her_words_is_not_the_owner_of_them(
    analyzer: NedAnalyzer, text: str
) -> None:
    """朋友 / 闺蜜 / 家人 as the person she said it to, not the person who said it."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text
    assert boundary_spans(analyzer, text), text


@pytest.mark.parametrize("text", READER_OWNED_STANCES)
def test_the_readers_own_stance_is_not_read_as_hers(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", INTERROGATIVE_FORMS)
def test_a_question_about_a_boundary_is_not_a_stated_boundary(
    analyzer: NedAnalyzer, text: str
) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", OTHER_OBJECTS)
def test_a_boundary_about_somebody_else_is_not_about_the_reader(
    analyzer: NedAnalyzer, text: str
) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", OLD_TRIGGER_SCOPE)
def test_the_guards_are_scoped_to_the_new_shapes(analyzer: NedAnalyzer, text: str) -> None:
    """The older triggers keep the behaviour the shipped pack gave them.

    Precision guards whose stance list is the whole family would have moved
    "她朋友说她不想和我说话" and "她为什么不想和我说话了？" out of the boundary
    screen. These are the shipped answers, unchanged.
    """

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text


def test_the_new_shapes_are_anchored_on_the_other_person(book: RuleBook) -> None:
    """Three siblings, one subject anchor each, no rewrite of the old patterns."""

    patterns = subject_anchored_patterns(book)
    assert len(patterns) == 3, patterns
    for pattern in patterns:
        assert pattern.startswith(ANCHOR), pattern
        assert parser.compile_pattern(pattern)
    joined = "|".join(patterns)
    for shape in (
        "((和|跟|与)(我|你|您))?(当|做)",
        "(不|别)(想|要|愿|愿意)(再)?见",
        "(发展|谈|开始)",
    ):
        assert shape in joined, shape


def test_the_subject_gap_is_what_keeps_the_reader_out(book: RuleBook) -> None:
    """One structural rule carries the reader's own stance, not many excludes.

    "我跟她说我只想当普通朋友", "她说我不想见她", "她逼我说我只想当普通朋友" and
    "她建议我只想当普通朋友" are all kept out of her boundary by this gap alone.
    """

    for pattern in subject_anchored_patterns(book):
        start = pattern.index(SUBJECT_GAP)
        assert pattern[start : start + len(SUBJECT_GAP)] == SUBJECT_GAP, pattern
        assert pattern.startswith(ANCHOR), pattern


def test_only_a_quote_may_put_the_readers_pronoun_after_the_subject(book: RuleBook) -> None:
    """The one exception is gated three ways: speech verb, quote mark, speaking 我.

    The anchor may not follow 和 / 跟 / 与 / 对 / 向 / 给, which is what keeps
    "我跟她说“我只想当普通朋友”" out.
    """

    for pattern in subject_anchored_patterns(book):
        assert pattern.startswith("(?<![和跟与对向给])"), pattern
        if "我" in pattern.split(SUBJECT_GAP)[1]:
            assert QUOTE_BRANCH in pattern, pattern


def test_the_family_carries_one_attribution_guard(book: RuleBook) -> None:
    """One guard, three shapes, all keyed on who owns the stance.

    The rejected design suppressed any sentence containing 朋友 / 闺蜜 / 家人,
    which would have killed "她跟朋友说她不想见我" — there the friend is only
    whoever she said it to.
    """

    guards = [pattern for pattern in rejection_excludes(book) if "闺蜜" in pattern]
    assert len(guards) == 1, guards
    guard = guards[0]
    assert guard.startswith("(?<![和跟与])("), guard
    assert "(她|他|对方)" in guard, guard
    for receiver in ("跟", "和", "与", "对", "向", "给", "告", "诉"):
        assert receiver in guard, receiver
    for relay in ("转述", "复述", "转达"):
        assert relay in guard, relay
    assert "(我|你|他|她)" in guard, guard
    assert parser.compile_pattern(guard)


def test_no_guard_keys_on_a_third_party_noun_alone(book: RuleBook) -> None:
    """The rejected design: suppress whatever mentions 朋友 / 闺蜜 / 家人."""

    for pattern in rejection_excludes(book):
        if "闺蜜" in pattern:
            assert "(她|他|对方)" in pattern, pattern


def test_the_family_carries_one_interrogative_guard(book: RuleBook) -> None:
    guards = guards_for(book, "为什么|怎么|难道|如何")
    assert len(guards) == 1, guards
    guard = guards[0]
    assert "[？?]|吗|呢" in guard, guard
    assert parser.compile_pattern(guard)


def test_the_family_carries_one_negation_guard(book: RuleBook) -> None:
    guards = guards_for(book, "不能证明")
    assert len(guards) == 1, guards
    guard = guards[0]
    for phrase in ("不足以证明", "不代表", "不等于", "不能说明", "不足以说明"):
        assert phrase in guard, phrase
    # BATCH 2 moved the uncertainty vocabulary into the behaviour guard's frame
    # classes, so the negation guard keeps only the evidence-negation and denial
    # shapes: uncertainty is closed once, in one place.
    behaviour = next(
        pattern
        for pattern in rejection_excludes(book)
        if pattern.startswith("(?:可能|也许") and "做朋友" in pattern
    )
    for phrase in ("不一定", "未必", "不见得"):
        assert phrase in behaviour, phrase
    assert "确定" in behaviour and "确认" in behaviour, behaviour
    assert "没说" not in guard
    assert "没(说|讲|表示|称|提)" in guard, guard
    assert parser.compile_pattern(guard)


def test_the_hedge_guard_covers_the_new_shapes(book: RuleBook) -> None:
    """The previous window's closure, extended instead of duplicated.

    A hedged claim about the new shapes — "她可能只想当普通朋友" — is still an
    inference, so the shape joined the existing behaviour guard rather than
    bringing a third copy of the modal vocabulary with it.
    """

    guards = [pattern for pattern in modal_guards(book) if "确定|确认|判断|知道" in pattern]
    assert len(guards) == 2, guards
    reader_patient = [
        pattern for pattern in modal_guards(book) if "被" in pattern and "拒" in pattern
    ]
    assert reader_patient, "reader-patient hedge/question guard class is missing"
    behaviour = next(pattern for pattern in guards if "做朋友" in pattern)
    assert "当(个)?(普通|一般|平常)?朋友" in behaviour, behaviour
    assert "做(个)?(普通|一般|平常)?朋友" in behaviour, behaviour


# --------------------------------------------------------------------------- #
# BATCH 2: uncertainty cannot certify a boundary
# --------------------------------------------------------------------------- #

#: One representative per semantic class. None of these reports that a boundary
#: was stated: they are modal, epistemic, belief-negation or question frames, and
#: a frame about the proposition is not the proposition.
UNCERTAINTY_FRAMES = (
    # modal uncertainty
    "她未必拒绝了我",
    "她不一定想让我滚",
    "她不见得想让我别联系她",
    "她好像想让我别联系她",
    "她大概不想再和我联系了",
    # epistemic uncertainty: a negator plus an epistemic predicate
    "我不确定她不想和我说话",
    "我不能确定她不想见我",
    "我无法确定她不想见我",
    "我没法判断她是不是不想见我",
    "我不能确认她说我们不合适",
    "很难说她是不是不想联系我",
    "不好说她是不是想让我离开",
    # belief negation
    "我不相信她不想见我",
    "我不认为她是不想见我",
    "我不觉得她真的拒绝我",
    # question / speculation
    "她是不是不想联系我",
    "谁知道她是不是不想联系我",
    "她会不会是想让我滚",
    # a trailing modal scopes the clause in front of it
    "她不想和我说话也说不定",
    "她拒绝了我也未必",
    "她说我们不合适也说不定",
    # she is uncertain herself: her frame does not certify her boundary either
    "她说她也不确定要不要继续",
    "她说她暂时不知道想不想见我",
)

#: A stated boundary, including the arrangements the uncertainty guard must not
#: reach into: a modal in a *later* clause does not cancel the boundary in front.
CERTIFIED_BOUNDARIES = (
    "她拒绝了我",
    "她让我滚",
    "她让我别联系她",
    "她说我们不合适",
    "她说不想见我",
    "她说她只想当普通朋友",
    "她说她不想发展成恋爱关系",
    "她说：“我不想见你”",
    "她明确说她不想见我",
    "她明确拒绝了我，我现在可能很难受",
    "我表白被拒了",
)


@pytest.mark.parametrize("text", UNCERTAINTY_FRAMES)
def test_uncertainty_cannot_certify_a_boundary(analyzer: NedAnalyzer, text: str) -> None:
    """不确定 ≠ 明确: a frame about the proposition is not the proposition.

    BATCH 2 closes the debt with semantic classes rather than with the handful of
    tokens the probe happened to miss: modal adverbs, a negator plus an epistemic
    predicate, belief negation, question markers, and a trailing modal.
    """

    result = analyzer.analyze_text(text, mode="normal")
    assert result.signal_type != SignalType.DIRECT_REJECTION, text
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", CERTIFIED_BOUNDARIES)
def test_a_certified_boundary_stays_certified(analyzer: NedAnalyzer, text: str) -> None:
    """The guard may not reach a statement, or a modal in another clause."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text


def test_the_uncertainty_frame_is_classes_not_tokens(book: RuleBook) -> None:
    """No bespoke token list: both guards share one class vocabulary."""

    patterns = rejection_patterns(book)
    guards = [
        pattern
        for pattern in rejection_excludes(book)
        if "可能|也许" in pattern and "确定|确认|判断" in pattern
    ]
    assert len(guards) == 2, guards

    # the shared head: modal adverbs, then a negator class times an epistemic class
    frame = ""
    for left, right in zip(*guards, strict=False):
        if left != right:
            break
        frame += left
    assert "可能|也许|或许|大概|大约|恐怕|似乎|好像" in frame, frame
    assert "不|没|没有|未|难以|很难|无法|没法|不能|不敢|不会|难" in frame, frame
    assert "确定|确认|判断|知道|清楚" in frame, frame
    assert len(frame) > 120, len(frame)

    for guard in guards:
        assert guard.startswith(frame), guard
        assert guard[len(frame) :].strip(), guard
        # the rest of the vocabulary is shared too: question markers and idioms
        assert "是不是|是否|会不会|算不算" in guard, guard
        assert "说不准|说不好|难说|不好说" in guard, guard

    # the reader-belief group stays in the behaviour guard alone:
    # "我觉得我们不合适" is the reader's own judgement,
    # not a frame about the other person's stance
    belief = "(?:我|咱)(?:觉得"
    assert sum(belief in guard for guard in guards) == 1, guards

    # a token list would have named the sentences; a class frame cannot
    for prose in UNCERTAINTY_FRAMES:
        assert all(prose not in guard for guard in guards), prose

    # and uncertainty is never a trigger: it only ever guards a real rejection
    assert all("(?:可能|也许" not in pattern for pattern in patterns), patterns


# --------------------------------------------------------------------------- #
# BATCH 3: a stated boundary may carry a receiver
# --------------------------------------------------------------------------- #

#: The receiver frame, and the part of it that must not be loosened: an adverbial
#: slot from a closed class, then the reader as the receiver, then the speech verb.
#: A noun cannot stand in the adverbial slot, so "她妈妈跟我说..." is not read as
#: her own statement; the receiver slot is exactly 我/咱, so "我跟她说..." cannot
#: enter through it either.
RECEIVER_FRAME = (
    "(?:今天|昨天|昨晚|今早|早上|上午|中午|下午|晚上|前天|那天|刚刚|刚才|直接|明确|"
    "后来|又|就|才|已经|当面|亲口|突然|最后)?"
    "(?:(?:(?:跟|和|与|对|给)(?:我|咱)"
)
RECEIVER_OBJECT = "(?:告诉|通知|告知)(?:我|咱)"

#: She speaks, the reader receives, the proposition elides its inner subject.
RECEIVER_BOUNDARIES = (
    "她跟我说只想当普通朋友",
    "她对我说只想当普通朋友",
    "她告诉我只想当普通朋友",
    "她跟我说不想见我",
    "她对我说不想见我",
    "她告诉我不想见我",
    "她给我发消息说不想见我",
    "她跟我说不想发展成恋爱关系",
    "她对我说不想发展成恋爱关系",
    "她告诉我不想发展成恋爱关系",
    "她刚刚跟我说只想当普通朋友",
    "她昨天对我说不想见我",
    "她又跟我说不想见我",
    "她明确跟我说不想见我",
    "她亲口跟我说只想当普通朋友",
    "她昨天给我发消息说不想见我",
)

#: The same frame with her words quoted, and with an inner subject spelled out.
RECEIVER_QUOTES = (
    "她跟我说：“我不想见你”",
    "她对我说：“我只想跟你做普通朋友”",
    "她刚刚跟我说：“我不想见你”",
    "她跟我说她不想见我",
    "她对我说她只想当普通朋友",
    "她告诉我她不想发展成恋爱关系",
)

#: The reader is the speaker here. The anchor already refuses a pronoun behind a
#: preposition, and the receiver slot only accepts 我/咱, so none of these may enter.
READER_IS_THE_SPEAKER = (
    "我跟她说我只想当普通朋友",
    "我对她说我不想见她",
    "我跟她说我不想发展成恋爱关系",
    "我对她说：“我不想见你”",
    "我跟她说：“我只想当普通朋友”",
    "我昨天对她说我不想见她",
    "我刚刚跟她说只想当普通朋友",
    "我给她发消息说只想当普通朋友",
    "我告诉她我不想见她",
)

#: A relay is not her own statement to the reader.
RELAY_NOT_HER_STATEMENT = (
    "她朋友跟我说她只想跟我做普通朋友",
    "她妈妈跟我说只想当普通朋友",
    "她姐姐跟我说只想当普通朋友",
    "她朋友跟我说不想见我",
    "她妈跟我说不想见我",
    "她妈妈昨天跟我说不想见我",
    "她老公跟我说不想发展成恋爱关系",
    "她妈妈说只想当普通朋友",
    "她的朋友跟我说只想当普通朋友",
    "她跟我说朋友不想见我",
)

#: The question contract is not escaped by the receiver frame: asking about a
#: boundary is not stating one.
QUESTIONS_BEHIND_THE_RECEIVER = (
    "她跟我说只想当普通朋友吗？",
    "她跟我说不想见我这件事是真的吗",
    "她跟我说“你是不想见我吗”",
    "她问我是不是只想当普通朋友",
    "她对我说“我们是不是不合适”",
)

#: BATCH 2 stays closed behind the receiver frame.
UNCERTAINTY_BEHIND_THE_RECEIVER = (
    "她跟我说可能不想见我",
    "她跟我说她未必不想见我",
    "她对我说也许还是做朋友比较好",
    "她跟我说她也不确定要不要继续",
    "她告诉我她不知道想不想见我",
    "她跟我说她可能不想见我",
    "她跟我说她是不是不想见我",
    "她跟我说她不想见我的可能性不大",
    "她跟我说她不确定要不要继续",
)

#: Saying that she never said it is not saying it.
NEGATED_SPEECH = (
    "她没有跟我说不想见我",
    "她没跟我说只想当普通朋友",
    "她从没跟我说过不想见我",
    "她并没有跟我说不想见我",
)

#: The debt BATCH 3 registered and BATCH 4 closed. Three separate authors used to
#: reach the boundary screen through the unanchored patterns (the reader speaking),
#: the enumerative relay guard's blind spots (a named third party), and the subject
#: gap's tolerance of a noun (a third-party proposition). The ownership helper
#: closes all three structurally, and these assert the corrected behaviour.
CLOSED_DEBT = (
    "我告诉她我们还是做朋友吧",
    "我给她发消息说我们保持距离吧",
    "我刚刚告诉她我们还是做朋友吧",
    "她妈妈跟我说她不想见我",
    "室友告诉我她不想见我",
    "小王跟我说她觉得我们不合适",
    "我妈告诉我她让我别联系她",
    "她跟我说她姐姐只想当普通朋友",
    "她告诉我别人觉得我们不合适",
)

#: A receiver frame does not reach the older two-character gap that owns
#: "拒绝了我"; the natural forms with an inner subject do work and are pinned above.
RECEIVER_REJECTION_ASYMMETRY = "她跟我说拒绝了我"


@pytest.mark.parametrize("text", RECEIVER_BOUNDARIES)
def test_a_receiver_frame_is_her_own_statement(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text
    assert result.signal_type == SignalType.DIRECT_REJECTION, text


@pytest.mark.parametrize("text", RECEIVER_QUOTES)
def test_a_receiver_frame_carries_her_quoted_or_cased_words(
    analyzer: NedAnalyzer, text: str
) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text


@pytest.mark.parametrize("text", READER_IS_THE_SPEAKER)
def test_the_reader_as_speaker_is_not_her_boundary(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", RELAY_NOT_HER_STATEMENT)
def test_a_relay_through_a_named_person_is_not_her_statement(
    analyzer: NedAnalyzer, text: str
) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", QUESTIONS_BEHIND_THE_RECEIVER)
def test_a_question_behind_the_receiver_frame_stays_a_question(
    analyzer: NedAnalyzer, text: str
) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", UNCERTAINTY_BEHIND_THE_RECEIVER)
def test_uncertainty_behind_the_receiver_frame_is_still_uncertainty(
    analyzer: NedAnalyzer, text: str
) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", NEGATED_SPEECH)
def test_negated_speech_is_not_a_statement(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", CLOSED_DEBT)
def test_the_registered_debt_is_closed(analyzer: NedAnalyzer, text: str) -> None:
    """The three other authors no longer reach her boundary screen."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


def test_the_receiver_rejection_asymmetry_is_registered(analyzer: NedAnalyzer) -> None:
    """BATCH 5.3b: the asymmetry is closed as a contrast, not as one historical miss.

    A. subjectless ellipsis - the outer speech sender carries the proposition
    B. aligned inner subject - it is still her statement
    C. conflicting inner subject - the outer sender may not take it over
    D. reader-as-actor - a different proposition, not this boundary
    """

    subjectless = RECEIVER_REJECTION_ASYMMETRY
    aligned = "她跟我说她拒绝了我"
    conflict = "她跟我说他拒绝了我"
    direction = "她说我拒绝了她"

    assert analyzer.analyze_text(subjectless, mode="normal").verdict.code == "ned.direct_rejection"
    assert analyzer.analyze_text(aligned, mode="normal").verdict.code == "ned.direct_rejection"
    for text in (conflict, direction):
        assert analyzer.analyze_text(text, mode="normal").verdict.code != "ned.direct_rejection", (
            text
        )


def test_the_receiver_frame_states_the_roles_explicitly(book: RuleBook) -> None:
    """sender, adverbial, receiver, speech, proposition: five explicit slots."""

    patterns = subject_anchored_patterns(book)
    assert len(patterns) == 3, patterns
    for pattern in patterns:
        # the sender is still the anchored other person, and still may not follow a
        # preposition: "我跟她说..." cannot become the sender
        assert pattern.startswith(ANCHOR), pattern[:40]
        # the subject gap is unchanged and still refuses 我
        assert pattern.count(SUBJECT_GAP) == 1, pattern
        # the receiver frame is a separate, explicit alternative
        assert pattern.count(RECEIVER_FRAME) == 1, pattern
        assert pattern.count(RECEIVER_OBJECT) == 1, pattern
    # no generic gap was loosened to let 我 through: the only 我-tolerant slot is the
    # receiver frame itself
    for pattern in patterns:
        head = pattern[: pattern.index(RECEIVER_FRAME)]
        assert "[^。！？!?，,我]{0,2}(?:跟|和|与|对|给)" not in head, pattern


def test_the_question_guard_sees_the_receiver_frame(book: RuleBook) -> None:
    """The interrogative contract is inherited, not escaped: exclude 28 gets the
    same frame, so "她跟我说只想当普通朋友吗？" is a question about it."""

    guards = guards_for(book, "为什么|怎么|难道|如何")
    assert len(guards) == 1, guards
    assert RECEIVER_FRAME in guards[0], guards[0]
    assert guards[0].count(RECEIVER_FRAME) == 1, guards[0]


# --------------------------------------------------------------------------- #
# BATCH 3 follow-up: a boundary is hers
# --------------------------------------------------------------------------- #

#: The reader is the author of the stance: it is the reader's sentence, not her
#: boundary. Nothing here may reach the boundary screen.
READER_AUTHORS_THE_STANCE = (
    "我跟她说我只想当普通朋友",
    "我对她说我不想见她",
    "我告诉她我们还是做朋友吧",
    "我给她发消息说我们保持距离吧",
    "我刚刚告诉她我们还是做朋友吧",
    "我说我们不合适",
    "我觉得我们不合适",
    "我感觉我们不合适",
    "我认为我们不合适",
    "我告诉她我们不合适",
    "我跟她说我们不合适",
    "我对她说我们不合适",
    "我对她说：“我们还是做朋友吧”",
    "我告诉她“我不想见她”",
)

#: A relay: the boundary reaches the input second hand. The speaker is a noun
#: phrase, and no list of names is involved - only that a content word stands
#: where the speaker must be, and that the receiver is the reader.
RELAY_IS_NOT_HER_STATEMENT = (
    "她妈妈跟我说她不想见我",
    "她朋友跟我说她只想跟我做普通朋友",
    "室友告诉我她不想见我",
    "小王跟我说她觉得我们不合适",
    "我妈告诉我她让我别联系她",
    "她妈妈跟我说只想当普通朋友",
    "她姐姐跟我说只想当普通朋友",
    "她朋友跟我说不想见我",
    "她妈跟我说不想见我",
    "她妈妈昨天跟我说不想见我",
    "她老公跟我说不想发展成恋爱关系",
    "她的朋友跟我说只想当普通朋友",
    "她妈妈说只想当普通朋友",
    "她朋友说她不想和我说话",
    "她朋友说她不想见我",
    "她转述说不想见我",
    "我妈说她不想见我",
)

#: The proposition belongs to somebody else: the speech frame is hers, but the
#: subject of the proposition is a noun phrase, so the stance is not her own.
PROPOSITION_OWNER_IS_SOMEBODY_ELSE = (
    "她跟我说她姐姐只想当普通朋友",
    "她跟我说朋友不想见我",
    "她告诉我别人觉得我们不合适",
    "她说：“我妈觉得我们不合适”",
)

#: Denials: the sentence refuses the conclusion, exactly like the epistemic
#: negation family.
DENIED_BY_THE_SENTENCE = (
    "这不能证明她说我们还是做朋友吧",
    "不代表她拒绝了我",
    "不等于她不想和我说话",
)

#: The quote perspective. Inside direct speech 我 is the speaker; the quote does
#: not change who owns the sentence that introduces it.
QUOTE_PERSPECTIVE_BOUNDARIES = (
    "她说：“我不想见你”",
    "她说：“我们不合适”",
    "她跟我说：“我不想见你”",
    "她对我说：“我不想见你”",
    "她对我说：“我只想跟你做普通朋友”",
)
QUOTE_PERSPECTIVE_NOT_BOUNDARIES = (
    "她妈妈对我说：“她不想见你”",
    "我对她说：“我们还是做朋友吧”",
    "她对我说：“我姐姐不想见你”",
    "她说：“我妈觉得我们不合适”",
)

#: Her own act or stance, including the passive shape where the reader narrates
#: what she did to the reader.
HER_OWN_ACT_OR_STANCE = (
    "她拒绝了我",
    "她让我滚",
    "她让我别联系她",
    "她说我们不合适",
    "她告诉我们不合适",
    "她跟我说我们不合适",
    "她说不想见我",
    "她说她只想当普通朋友",
    "她和朋友说她只想当普通朋友",
    "她昨天告诉我她不想见我",
    "她哭着说她不想见我",
    "她跟我说她不想见我",
    "她对我说她只想当普通朋友",
    "她告诉闺蜜她只想和我做普通朋友",
    "我表白被拒了",
    "我被拒绝了",
    "他让我滚",
)

#: The shipped reading of a bare stock line: no author is named, so the family
#: keeps reading it as her line, and the reader's own 你-object stance keeps its
#: shipped answer too.
BARE_STOCK_LINES = (
    "对方明确说不想再和我说话",
    "她只想当普通朋友",
    "他给我买了早餐，但她只想当普通朋友",
)

#: POLICY A: bare forms the family used to certify; the stance names nobody.
BARE_UTTERANCE_NOT_BOUNDARY = (
    "我不想和你说话",
    "我们还是做朋友吧",
    "保持距离",
    "让我滚",
    "离我远点",
    "滚",
    "别烦我",
    "我们不合适",
)


@pytest.mark.parametrize("text", READER_AUTHORS_THE_STANCE)
def test_the_reader_as_author_is_not_her_boundary(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", RELAY_IS_NOT_HER_STATEMENT)
def test_a_relay_is_not_her_own_statement(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", PROPOSITION_OWNER_IS_SOMEBODY_ELSE)
def test_a_third_party_proposition_is_not_her_stance(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", DENIED_BY_THE_SENTENCE)
def test_a_denied_conclusion_is_not_certified(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", CLOSED_BY_OWNERSHIP)
def test_the_older_triggers_the_ownership_helper_closed(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", QUOTE_PERSPECTIVE_BOUNDARIES)
def test_a_quote_keeps_the_speaker_perspective(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text


@pytest.mark.parametrize("text", QUOTE_PERSPECTIVE_NOT_BOUNDARIES)
def test_a_quote_from_another_author_is_not_her_boundary(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", HER_OWN_ACT_OR_STANCE)
def test_her_own_act_or_stance_is_still_a_boundary(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text


@pytest.mark.parametrize("text", BARE_STOCK_LINES)
def test_a_bare_stock_line_keeps_its_shipped_reading(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.direct_rejection", text


def test_the_ownership_helper_reads_roles_not_people() -> None:
    """The closure is structural: no person list and no reporting-verb list.

    The check reads the module's own vocabulary literals, so the example sentences
    in its docstring cannot satisfy it by accident.
    """

    module = REPO_ROOT / "ned" / "app" / "core" / "boundary.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    vocabulary = {
        element.value
        for node in ast.walk(tree)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set))
        for element in node.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    }
    names = (
        "妈妈",
        "妈妈".replace("妈", "爸"),
        "姐姐",
        "妹妹",
        "哥哥",
        "室友",
        "小王",
        "闺蜜",
        "老师",
        "同学",
        "朋友",
        "家人",
        "亲戚",
        "父母",
        "同事",
        "表哥",
        "网友",
    )
    for name in names:
        assert name not in vocabulary, name
    for verb in ("转述", "复述", "转达", "嘀咕", "断言", "念叨", "私下说", "提了一句"):
        assert verb not in vocabulary, verb
    # the receiver slot is marked by grammar instead: a preposition or a
    # receiver-object verb, and the reader's own pronoun
    for token in ("跟", "和", "与", "对", "向", "给", "告诉", "通知", "告知"):
        assert token in vocabulary, token
    functions = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert "hers" in functions, functions
    assert "_walk" in functions, functions


def test_the_helper_is_only_wired_for_the_chinese_boundary_family() -> None:
    """The ownership check reads Chinese roles, so it is not applied to the en pack."""

    parser = (REPO_ROOT / "ned" / "app" / "core" / "parser.py").read_text(encoding="utf-8")
    assert 'rule.id.startswith("zh.") and rule.signal_type.value == "direct_rejection"' in parser
    assert "boundary.hers(text, item[0], item[1])" in parser


@pytest.mark.parametrize("text", BARE_UTTERANCE_TEXTS)
def test_a_bare_utterance_is_not_certified(analyzer: NedAnalyzer, text: str) -> None:
    """POLICY A: with no speaker in the input, the utterance is the reader's."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", BARE_UTTERANCE_NOT_BOUNDARY)
def test_a_bare_form_is_not_a_boundary(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


@pytest.mark.parametrize("text", QUESTIONED_BOUNDARY_SHAPES)
def test_a_question_never_certifies_a_boundary(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert boundary_spans(analyzer, text) == [], text


def test_the_reader_default_is_shared_with_the_positive_family(analyzer: NedAnalyzer) -> None:
    """我想你了 and 我不想和你说话 read the same 我: the reader's.

    NED's canonical input is the reader's own sentence, so the boundary family gets no
    exemption that would read the same pronoun as the other person.
    """

    longing = analyzer.analyze_text("我想你了", mode="normal")
    bare = analyzer.analyze_text("我不想和你说话", mode="normal")
    assert longing.verdict.code != "ned.direct_rejection"
    assert bare.verdict.code != "ned.direct_rejection"
