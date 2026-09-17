"""PR-1 regression pins: relationship-intent polarity, negation and boundary ownership.

PR-0 (RH-5 black-box pass) found that a refusal containing a relationship-intent phrase
could be signed as *positive* evidence, in three different ways:

  A. ownership/tokenisation -- 她暂时不想谈恋爱 was tokenised as "她" + content + ... so the
     boundary stop looking like hers and the inner 谈恋爱 was left standing;
  B. proposition polarity   -- 她妈妈不同意我们在一起 matched the literal 我们在一起 and
     nothing asked whether the proposition was negated or opposed;
  C. quote / bridge structure -- 她说“我现在不想谈恋爱” did not match the boundary rule at
     all, because the quoted-first-person branch only tolerated zero adverbs.

These tests pin the repaired behaviour, the positive controls that must keep working, the
hard lines that must not move, and the layer that decides each case.
"""

from __future__ import annotations

import pytest
from ned.app.core import polarity
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import SignalType
from ned.app.core.rules import RuleBook

#: Every refusal/resistance shape PR-0 filed, including the eight it added on top of RH-5.
BLOCKER_SHAPES = (
    # A: an adverb the tokenizer used to call "content"
    "她暂时不想谈恋爱",
    "她说她暂时不想谈恋爱",
    "她目前不想谈恋爱",
    "她短期内不想谈恋爱",
    "她坚决不想谈恋爱",
    "她说她目前不想谈恋爱",
    "她说她坚决不想谈恋爱",
    "她表示暂时不想谈恋爱",
    "她跟我说她暂时不想谈恋爱",
    # C: a quote with an adverb inside it
    "她说“我现在不想谈恋爱”",
    # B: an obstacle in front of the phrase
    "她妈妈不同意我们在一起",
    "她家里不同意我们在一起",
    "她父母反对我们在一起",
    "我妈妈不同意我们在一起",
    "她妈妈不赞成我们在一起",
    "她妈妈不支持我们在一起",
    # the same ownership defect reaching phrases that carry no positive substring
    "她暂时不想见我",
    "她暂时不想发展成恋爱关系",
    "她暂时只想做朋友",
)

#: Positive controls: a real offer must stay positive evidence.
POSITIVE_CONTROLS = (
    "她想和我谈恋爱",
    "她说想和我做男女朋友",
    "她妈妈同意我们在一起",
    "她说想和我在一起",
    "她问我要不要在一起",
    "她说我们在一起吧",
)

#: The refusal shapes that are attributed to her, so they must reach the boundary screen.
HER_REFUSALS = (
    "她不想谈恋爱",
    "她说她不想谈恋爱",
    "她说“我不想谈恋爱”",
    "她说她现在不想谈恋爱",
    "她说“我现在不想谈恋爱”",
    "她暂时不想谈恋爱",
    "她表示暂时不想谈恋爱",
)

#: Third-party resistance: never positive, and never dressed up as her own boundary.
THIRD_PARTY_RESISTANCE = (
    "她妈妈不同意我们在一起",
    "她家里不同意我们在一起",
    "她父母反对我们在一起",
    "我妈妈不同意我们在一起",
    "她妈妈不赞成我们在一起",
    "她妈妈不支持我们在一起",
)


def positive_families(analyzer: NedAnalyzer, text: str) -> set[str]:
    """The signal families the engine offers as positive evidence for ``text``."""

    result = analyzer.analyze_text(text, mode="normal")
    return {span.signal_type.value for span in result.evidence if span.polarity == "positive"}


def verdict_of(analyzer: NedAnalyzer, text: str) -> str:
    return analyzer.analyze_text(text, mode="normal").verdict.code


# --------------------------------------------------------------------------- #
# the three root causes, one test each
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", BLOCKER_SHAPES)
def test_no_refusal_is_signed_as_positive_evidence(analyzer: NedAnalyzer, text: str) -> None:
    """The whole blocker family: not one of them may be positive evidence."""

    assert "commitment_offer" not in positive_families(analyzer, text), text


@pytest.mark.parametrize("text", BLOCKER_SHAPES)
def test_no_refusal_reaches_a_positive_screen(analyzer: NedAnalyzer, text: str) -> None:
    """Positive screens are for positive evidence; none of these may show one."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ped.ren_hao", text
    assert result.verdict.code != "ped.launching", text
    assert result.verdict.code != "ned.reaching", text


def test_root_cause_a_adverb_keeps_the_stance_hers(analyzer: NedAnalyzer) -> None:
    """A temporal/degree adverb does not turn her refusal into somebody else's phrase."""

    for adverb in ("暂时", "目前", "短期内", "坚决", "现阶段", "一时", "眼下"):
        text = f"她{adverb}不想谈恋爱"
        assert verdict_of(analyzer, text) == "ned.direct_rejection", text


def test_root_cause_b_polarity_is_asked_separately_from_matching(analyzer: NedAnalyzer) -> None:
    """The clause decides polarity; the literal phrase only proposes a candidate."""

    affirmed = polarity.relationship_intent_polarity("我们在一起", 0, 4)
    negated = polarity.relationship_intent_polarity("她不想和我们在一起", 5, 9)
    opposed = polarity.relationship_intent_polarity("她妈妈不同意我们在一起", 5, 9)

    assert affirmed.positive and affirmed.reason == "affirmed"
    assert not negated.positive and negated.reason == "negated"
    assert not opposed.positive and opposed.reason == "opposed"
    assert opposed.opposition_subject == "third_party"


def test_root_cause_c_quotes_and_adverbs_do_not_decide(analyzer: NedAnalyzer) -> None:
    """A report marker, an adverb and a report verb must not change her refusal.

    Quoted speech and the colon both open reported speech (the ownership layer's own
    ``QUOTE_OPENERS`` already says so), so all of these are her refusal. The unquoted
    ``她说我不想谈恋爱`` is deliberately *not* in this list: with no report marker the 我 is
    the reader, so it is a report about the reader rather than her boundary (pinned in
    ``test_a_report_without_a_marker_keeps_the_reader_as_the_first_person``).
    """

    for text in (
        "她说“我不想谈恋爱”",
        "她说“我现在不想谈恋爱”",
        "她说她现在不想谈恋爱",
        "她说：我不想谈恋爱",
        "她说:我不想谈恋爱",
        "她跟我说：我不想谈恋爱",
        "她表示她暂时不想谈恋爱",
    ):
        assert verdict_of(analyzer, text) == "ned.direct_rejection", text


def test_a_report_without_a_marker_keeps_the_reader_as_the_first_person(
    analyzer: NedAnalyzer,
) -> None:
    """``她说我不想谈恋爱`` reads as "she said I don't want to date": not her boundary.

    It must still never be positive evidence -- the proposition is negated either way.
    """

    text = "她说我不想谈恋爱"
    assert verdict_of(analyzer, text) != "ned.direct_rejection"
    assert "commitment_offer" not in positive_families(analyzer, text)


# --------------------------------------------------------------------------- #
# polarity matrix
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    (
        ("她想和我在一起", True),
        ("她想和我谈恋爱", True),
        ("她妈妈同意我们在一起", True),
        ("她赞成我们在一起", True),
        ("她支持我们在一起", True),
        ("她不想和我在一起", False),
        ("她不想谈恋爱", False),
        ("她现在不想和我在一起", False),
        ("她暂时不想谈恋爱", False),
        ("她妈妈不同意我们在一起", False),
        ("她妈妈不赞成我们在一起", False),
        ("她妈妈不支持我们在一起", False),
        ("她父母反对我们在一起", False),
    ),
)
def test_agree_disagree_polarity_matrix(analyzer: NedAnalyzer, text: str, expected: bool) -> None:
    """同意/不同意, 赞成/不赞成, 支持/不支持, 想/不想, 现在不想 / 暂时不想."""

    assert ("commitment_offer" in positive_families(analyzer, text)) is expected, text


def test_the_layer_reports_its_reason(analyzer: NedAnalyzer) -> None:
    """Every guarded decision names the marker that decided it."""

    cases = (
        ("她暂时不想谈恋爱", "negated", "不"),
        ("她妈妈不同意我们在一起", "opposed", "不同意"),
        ("她父母反对我们在一起", "opposed", "反对"),
        ("她妈妈不赞成我们在一起", "opposed", "不赞成"),
        ("她妈妈不支持我们在一起", "opposed", "不支持"),
    )
    for text, reason, marker in cases:
        hit = _guard_hit(text, "zh.commitment_offer")
        if hit is None:
            # the phrase may not even reach the rule (no positive span at all) -- then the
            # guard is simply never needed, and the test asserts that outcome instead
            assert "commitment_offer" not in positive_families(analyzer, text), text
            continue
        assert hit.reason == reason, (text, hit)
        assert hit.marker == marker, (text, hit)


def _guard_hit(text: str, rule_id: str) -> polarity.IntentPolarity | None:
    """Ask the polarity layer about the rule's own match, even when the span was dropped."""

    from ned.app.core.parser import compile_pattern

    for rule in RuleBook.load().signals:
        if rule.id != rule_id:
            continue
        for pattern in rule.patterns:
            match = compile_pattern(pattern).search(text)
            if match:
                return polarity.relationship_intent_polarity(text, match.start(), match.end())
    return None


# --------------------------------------------------------------------------- #
# hard lines that must not move
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", POSITIVE_CONTROLS)
def test_positive_controls_stay_positive(analyzer: NedAnalyzer, text: str) -> None:
    assert "commitment_offer" in positive_families(analyzer, text), text


@pytest.mark.parametrize("text", HER_REFUSALS)
def test_her_own_refusals_stay_boundaries(analyzer: NedAnalyzer, text: str) -> None:
    assert verdict_of(analyzer, text) == "ned.direct_rejection", text


@pytest.mark.parametrize("text", THIRD_PARTY_RESISTANCE)
def test_third_party_resistance_is_neither_evidence_nor_her_boundary(
    analyzer: NedAnalyzer, text: str
) -> None:
    """A mother's objection is resistance, not a positivity and not her stated refusal."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code != "ned.direct_rejection", text
    assert not any(span.signal_type is SignalType.DIRECT_REJECTION for span in result.evidence), (
        text
    )
    assert "commitment_offer" not in positive_families(analyzer, text), text


def test_a_possessive_phrase_is_still_not_hers(analyzer: NedAnalyzer) -> None:
    """Fix A must not adopt somebody else's stance: 她的朋友… is still not hers."""

    for text in ("她的朋友不想谈恋爱", "她妈妈不想谈恋爱"):
        result = analyzer.analyze_text(text, mode="normal")
        assert result.verdict.code != "ned.direct_rejection", text
        assert "commitment_offer" not in positive_families(analyzer, text), text


def test_policy_a_bare_utterance_stays_reader_owned(analyzer: NedAnalyzer) -> None:
    """ "不要再联系我" names no speaker, so it is still not certified as her boundary."""

    for text in ("不要再联系我", "别烦我", "滚出去"):
        assert verdict_of(analyzer, text) != "ned.direct_rejection", text


def test_event_patient_and_reported_speech_are_untouched(analyzer: NedAnalyzer) -> None:
    """The passive reader and reported speech keep their shipped behaviour."""

    assert verdict_of(analyzer, "我表白被拒了") == "ned.direct_rejection"
    assert verdict_of(analyzer, "她说她不喜欢我") == "ned.no_signal"
    material = analyzer.analyze_text("她说她不喜欢我", mode="normal").materials
    assert material and material[0].reported_content == "她不喜欢我"
    assert "explicit_affection" in positive_families(analyzer, "她说她喜欢我")


def test_the_state_report_exclusion_still_holds(analyzer: NedAnalyzer) -> None:
    """ "我们在一起了" is a state report, not an offer: no positive evidence."""

    assert "commitment_offer" not in positive_families(analyzer, "我们在一起了")


def test_the_new_patterns_do_not_fire_on_an_activity(analyzer: NedAnalyzer) -> None:
    """ "想和我在一起工作" is an activity, not a relationship proposition."""

    assert "commitment_offer" not in positive_families(analyzer, "她想和我在一起工作")
    assert "commitment_offer" not in positive_families(analyzer, "她要和我在一起吃饭")
