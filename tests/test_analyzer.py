"""Analyzer tests.

These are the behavioural tests that matter: the classic inputs, the three
modes, the escalation across turns, and the honesty guarantees (NED never claims
to know what anyone feels).
"""

from __future__ import annotations

import pytest
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import AnalyzeRequest, SignalType
from ned.app.core.rules import RuleBook


def test_ordinary_positive_text(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她对我说“我想你了”", mode="normal")
    assert result.signal_type == SignalType.MISSING_YOU
    assert 40 <= result.signal_strength <= 70
    assert result.alternative_explanations, "PED must offer alternatives"
    assert result.verdict.code == "ped.ren_hao"
    assert "人好" in result.verdict.text
    assert result.reality_check.strip()
    assert result.language == "zh"


def test_explicit_affection(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("我喜欢你", mode="normal")
    assert result.signal_type == SignalType.EXPLICIT_AFFECTION
    assert result.signal_strength > 70
    assert result.positive_evidence_discount >= 35
    assert result.ned_reaching_level > 0


def test_very_strong_affection_reaches(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(
        "我说的是男女之间的喜欢，我就是喜欢你，做我男朋友吧", mode="extreme"
    )
    assert result.signal_strength > 85
    assert result.ned_reaching_level >= 80
    assert result.reaching_label == "NED is currently reaching."
    assert result.verdict.code == "ned.extreme_insufficient_sample"
    assert "样本量" in result.verdict.text
    assert any("capacity" in note or "reaching" in note for note in result.mode_notes)


def test_five_minutes_without_a_reply_is_rejected(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("消息发出去五分钟没回复", mode="normal")
    assert result.signal_type == SignalType.RESPONSE_LATENCY
    assert result.negative_evidence_amplification > 80
    assert result.verdict.code == "nea.latency_insufficient"
    assert "不构成证据" in result.verdict.text or "not evidence" in result.verdict.text
    assert result.observed_evidence
    assert result.irrational_amplification
    assert "5" in result.reality_check
    # No positive evidence means nothing for PED to discount, and NED says so.
    assert result.alternative_explanations == []
    assert result.ned_reaching_level < 20


def test_negative_conclusion_is_flagged_not_endorsed(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她不喜欢我，根本不在乎我", mode="normal")
    assert result.signal_type == SignalType.SELF_NEGATIVE_BELIEF
    assert result.negative_evidence_amplification > 70
    assert result.verdict.severity == "reject"


def test_neutral_text_produces_no_signal(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("今天开会开了三个小时，回来路上买了瓶水", mode="normal")
    assert result.signal_type == SignalType.NONE
    assert result.signal_strength == 0.0
    assert result.verdict.code == "ned.no_signal"
    assert result.alternative_explanations == []
    assert result.negative_evidence_amplification == 0.0


def test_self_discount_alone_is_recognised(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("可能只是人好", mode="normal")
    assert result.signal_type == SignalType.SELF_DISCOUNT
    assert result.verdict.code == "ned.self_discount_noted"


def test_extreme_mode_is_more_skeptical_than_normal(analyzer: NedAnalyzer) -> None:
    normal = analyzer.analyze_text("她对我说“我想你了”", mode="normal")
    extreme = analyzer.analyze_text("她对我说“我想你了”", mode="extreme")
    assert extreme.positive_evidence_discount > normal.positive_evidence_discount
    assert len(extreme.alternative_explanations) >= len(normal.alternative_explanations)
    assert extreme.mode == "extreme"


def test_scientific_mode_uses_formal_verdict(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她对我说“我想你了”", mode="scientific")
    assert result.verdict.code == "ned.scientific_insufficient_sample"
    assert "样本量" in result.verdict.text
    assert any("peer review" in note for note in result.mode_notes)


def test_evidence_strength_is_monotonic_in_the_wording(analyzer: NedAnalyzer) -> None:
    weak = analyzer.analyze_text("她夸我好看", mode="normal")
    medium = analyzer.analyze_text("她对我说“我想你了”", mode="normal")
    strong = analyzer.analyze_text("我喜欢你", mode="normal")
    strongest = analyzer.analyze_text("我们结婚吧", mode="normal")
    assert (
        weak.signal_strength
        < medium.signal_strength
        < strong.signal_strength
        < strongest.signal_strength
    )


def test_escape_capacity_escalates_across_turns(analyzer: NedAnalyzer) -> None:
    """The signature demo: NED keeps explaining, and eventually gives up."""

    history = ["我喜欢你", "我想和你谈恋爱", "做我男朋友吧"]
    result = analyzer.analyze_text("我们已经结婚了", mode="extreme", history=history)
    assert result.breakdown.history_mass > 90
    assert result.breakdown.escape_capacity >= 0.95
    assert result.verdict.code == "ned.capacity_exhausted"
    assert "不礼貌" in result.verdict.text
    assert result.ned_reaching_level == 100.0
    assert result.reaching_label == "人好。👍"


def test_without_history_the_same_input_stops_short(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("我们已经结婚了", mode="extreme")
    assert result.verdict.code != "ned.capacity_exhausted"
    assert result.ned_reaching_level < 100
    assert any(
        "法律关系" in item.hypothesis or "legal" in item.hypothesis
        for item in result.alternative_explanations
    )


def test_marriage_evidence_gets_the_family_law_escape(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她说想和我结婚", mode="extreme")
    hypotheses = " ".join(item.hypothesis for item in result.alternative_explanations)
    assert "法律关系" in hypotheses


def test_insistence_triggers_the_capacity_warning(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她说她就是喜欢我，说得很清楚了", mode="normal")
    notes = " ".join(result.mode_notes)
    hypotheses = " ".join(item.hypothesis for item in result.alternative_explanations)
    assert "capacity" in (notes + hypotheses)


def test_easter_eggs_are_reported_but_do_not_change_the_verdict(analyzer: NedAnalyzer) -> None:
    with_egg = analyzer.analyze_text("她说她喜欢我，人好", mode="normal")
    assert any(egg.id == "egg.ren_hao" for egg in with_egg.easter_eggs)
    assert with_egg.verdict.code in {"ped.ren_hao", "ped.friendly_unexcluded"}


def test_english_input_works(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("I love you", mode="scientific")
    assert result.language == "en"
    assert result.signal_type == SignalType.EXPRESSED_LOVE
    assert result.verdict.code == "ned.scientific_insufficient_sample"
    assert "sample" in result.verdict.text.lower()
    assert "measurement" in result.reality_check.lower()


def test_english_latency_input_works(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("She left me on read for 5 minutes", mode="normal")
    assert result.language == "en"
    assert result.signal_type == SignalType.RESPONSE_LATENCY
    assert result.verdict.code == "nea.latency_insufficient"
    assert "not evidence" in result.verdict.text


def test_mixed_input_builds_an_asymmetry_report(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(
        "她主动找我聊了两个小时，但消息发出去五分钟没回复，我觉得她不想理我", mode="normal"
    )
    assert result.asymmetry is not None
    reading = result.asymmetry.user_interpretation
    assert reading.status == "partial_basis"  # a conclusion on one side only
    assert reading.negative_self_conclusion_present is True
    assert reading.double_standard is False
    assert result.asymmetry_reality_check.strip()
    assert result.asymmetry.evidence_profile.comparable is True


def test_self_discount_plus_positive_evidence_is_user_language(analyzer: NedAnalyzer) -> None:
    """A self-discount is the reader's wording: it never becomes negative evidence."""

    result = analyzer.analyze_text("她主动找我聊了两个小时，但可能只是人好", mode="normal")
    # there is no negative side at all, so there is no comparison to attach
    assert result.asymmetry is None
    discounts = [span for span in result.evidence if span.polarity == "self_discount"]
    assert discounts, "the discount is still reported as the reader's own language"
    assert discounts[0].signal_type.value == "self_discount"


def test_alternatives_are_labelled_as_hypotheses(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("我喜欢你", mode="extreme")
    assert result.alternative_explanations
    for explanation in result.alternative_explanations:
        assert explanation.note == "Alternative hypothesis, not a finding."
        assert explanation.source == "local-rule"
        assert 0 <= explanation.plausibility <= 100


def test_plausibility_falls_as_evidence_grows(analyzer: NedAnalyzer) -> None:
    weak = analyzer.analyze_text("她夸我一句", mode="normal")
    strong = analyzer.analyze_text("做我男朋友吧，我们结婚", mode="extreme")
    weak_mean = sum(item.plausibility for item in weak.alternative_explanations) / max(
        len(weak.alternative_explanations), 1
    )
    strong_mean = sum(item.plausibility for item in strong.alternative_explanations) / max(
        len(strong.alternative_explanations), 1
    )
    assert strong_mean < weak_mean


def test_top_k_limits_the_hypotheses(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("我喜欢你", mode="extreme", top_k=2)
    assert len(result.alternative_explanations) == 2


def test_analysis_is_deterministic(analyzer: NedAnalyzer) -> None:
    first = analyzer.analyze_text("她对我说“我想你了”", mode="extreme", history=["我喜欢你"])
    second = analyzer.analyze_text("她对我说“我想你了”", mode="extreme", history=["我喜欢你"])
    assert first.model_dump(exclude={"generated_at"}) == second.model_dump(exclude={"generated_at"})


def test_every_report_carries_the_disclaimer(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("我喜欢你", mode="normal")
    assert "cannot determine whether someone likes you" in result.disclaimer
    assert result.engine.offline is True
    assert result.engine.provider == "local-rule"


def test_analyze_request_model_round_trips(analyzer: NedAnalyzer) -> None:
    request = AnalyzeRequest(
        text="她对我说“我想你了”", mode="extreme", history=["她对我说“我想你”"]
    )
    result = analyzer.analyze(request)
    assert result.input == "她对我说“我想你了”"
    assert result.mode == "extreme"
    assert result.breakdown.history_mass > 0


def test_modes_and_examples_are_exposed(analyzer: NedAnalyzer) -> None:
    modes = analyzer.modes()
    assert {mode.id for mode in modes} == {"normal", "scientific", "extreme"}
    cases = analyzer.examples()
    assert len(cases) >= 8
    assert all(case.text for case in cases)


def test_every_example_case_analyses_without_error(analyzer: NedAnalyzer) -> None:
    for case in analyzer.examples():
        result = analyzer.analyze_text(case.text, mode=case.mode)  # type: ignore[arg-type]
        assert result.verdict.text.strip()
        assert result.reality_check.strip()


def test_no_output_claims_to_know_anyones_feelings(analyzer: NedAnalyzer) -> None:
    """Guard rail: NED's strongest claims must stay about evidence, not people."""

    forbidden = ("她喜欢你", "她不爱你", "对方喜欢你", "she loves you", "she likes you back")
    for text, mode in (
        ("我喜欢你", "normal"),
        ("我们已经结婚了", "extreme"),
        ("她主动找我聊了两个小时", "scientific"),
    ):
        result = analyzer.analyze_text(text, mode=mode)  # type: ignore[arg-type]
        blob = " ".join(
            [
                result.verdict.text,
                result.raw_interpretation,
                result.reality_check,
                *(item.hypothesis for item in result.alternative_explanations),
            ]
        ).lower()
        for phrase in forbidden:
            assert phrase.lower() not in blob, f"{phrase!r} leaked into a NED report"


@pytest.mark.parametrize("mode", ["normal", "scientific", "extreme"])
def test_all_modes_produce_complete_reports(analyzer: NedAnalyzer, mode: str) -> None:
    result = analyzer.analyze_text("她主动找我聊了两个小时", mode=mode)  # type: ignore[arg-type]
    assert result.mode == mode
    assert result.verdict.text
    assert result.reaching_label
    assert 0 <= result.positive_evidence_discount <= 100
    assert 0 <= result.ned_reaching_level <= 100
    assert result.mode_notes
    assert result.engine.offline


#: Inputs that must never reach the catch-all verdict: one per signal family and
#: polarity, including the self-discount path.
DETECTED_SIGNAL_INPUTS = (
    "她对我说“我想你了”",
    "我喜欢你",
    "她主动找我聊了两个小时",
    "消息发出去五分钟没回复",
    "她不喜欢我，根本不在乎我",
    "她就回了一个嗯",
    "她临时说有事，改天吧",
    "他让我滚出去别烦他了",
    "她怒骂我",
    "可能只是人好",
)


def test_cold_reply_is_acknowledged_and_rejected(analyzer: NedAnalyzer) -> None:
    """A cold reply is evidence of something, so the verdict may not deny it."""

    result = analyzer.analyze_text("她就回了一个嗯", mode="normal")
    assert result.signal_type == SignalType.COLD_REPLY
    assert result.signal_strength == 45.0
    assert result.verdict.code == "nea.cold_reply_insufficient"
    assert result.verdict.severity == "reject"
    assert result.verdict.code != "ned.no_signal"
    assert "不足以证明" in result.verdict.text
    assert "这段关系已经结束" in result.verdict.text


def test_cancelled_plan_is_acknowledged_and_rejected(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她临时说有事，改天吧", mode="normal")
    assert result.signal_type == SignalType.PLAN_CANCELLED
    assert result.signal_strength == 42.0
    assert result.verdict.code == "nea.plan_cancelled_insufficient"
    assert result.verdict.severity == "reject"
    assert result.verdict.code != "ned.no_signal"
    assert "不足以证明" in result.verdict.text
    assert "根本不想见你" in result.verdict.text


def test_the_new_verdicts_ship_english_copy(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("She replied with just one word", mode="normal")
    assert result.language == "en"
    assert result.verdict.code == "nea.cold_reply_insufficient"
    assert result.verdict.text.startswith("A cold or minimal reply was detected")


def test_a_detected_signal_never_gets_the_no_signal_verdict(analyzer: NedAnalyzer) -> None:
    """ned.no_signal is reserved for inputs where nothing was detected.

    No exception: every negative signal family owns a verdict of its own now
    (response_latency, cold_reply, plan_cancelled, self_negative_belief,
    direct_rejection), the self-discount path has ned.self_discount_noted, and
    every positive signal reaches the ped.* rules.
    """

    for text in DETECTED_SIGNAL_INPUTS:
        result = analyzer.analyze_text(text, mode="normal")
        assert result.evidence, f"{text!r} produced no evidence"
        assert result.signal_type != SignalType.NONE, text
        assert result.verdict.code != "ned.no_signal", (
            f"{text!r} detected {result.signal_type.value} but got ned.no_signal"
        )


@pytest.mark.parametrize("mode", ["normal", "scientific", "extreme"])
def test_the_invariant_holds_for_every_shipped_example(analyzer: NedAnalyzer, mode: str) -> None:
    for case in analyzer.examples():
        result = analyzer.analyze_text(case.text, mode=mode)  # type: ignore[arg-type]
        if result.signal_type == SignalType.NONE:
            assert not result.evidence, case.id
            continue
        assert result.verdict.code != "ned.no_signal", (case.id, mode)


def test_no_signal_is_still_used_when_nothing_is_detected(analyzer: NedAnalyzer) -> None:
    """The catch-all must stay reachable, or the invariant would be vacuous."""

    result = analyzer.analyze_text("今天开会开了三个小时，回来路上买了瓶水", mode="normal")
    assert result.signal_type == SignalType.NONE
    assert result.evidence == []
    assert result.verdict.code == "ned.no_signal"


def test_no_signal_ships_bilingual_copy(analyzer: NedAnalyzer) -> None:
    """A truly empty input still reaches the catch-all, in both languages."""

    chinese = analyzer.analyze_text("今天开会开了三个小时，回来路上买了瓶水", mode="normal")
    english = analyzer.analyze_text("I bought a bottle of water on the way home", mode="normal")

    assert chinese.language == "zh"
    assert english.language == "en"
    for result in (chinese, english):
        assert result.signal_type == SignalType.NONE
        assert result.evidence == []
        assert result.verdict.code == "ned.no_signal"

    assert chinese.verdict.text == "未检测到明显情感证据。NED 无事可做。👍"
    assert english.verdict.text == "No clear emotional evidence detected. NED stands down. 👍"


# --------------------------------------------------------------------------- #
# BATCH 1: ownership — somebody else's words are not the reader's stance
# --------------------------------------------------------------------------- #

#: The reader's own discount. These are the reason the family exists, and none of
#: them may be lost while closing the attribution frames below.
READER_DISCOUNTS = (
    "我想太多了",
    "我是不是想太多了",
    "我觉得我想太多了",
    "可能只是人好",
    "我觉得可能只是人好",
    "别自作多情",
    "她只是把我当朋友",
    "她可能只是客气",
    "我随口一说",
    # she is the receiver of the reader's words here, not the author of the discount
    "我跟她说我想太多了",
)

#: The reader's own negative conclusion, including the reader's own report of it.
READER_CONCLUSIONS = (
    "她不喜欢我",
    "我觉得她不喜欢我",
    "我总觉得她不喜欢我",
    "她讨厌我",
    "她不想理我",
    "她嫌我烦",
    "她对我没兴趣",
    "她根本不在乎我",
    "我说她不喜欢我",
    "我和她说她不喜欢我",
)

#: Somebody else's words, advice or report. Each of these was filed as the reader's
#: own stance before this batch: the guard knew only the 说/讲/告诉/表示 frame, with
#: no requirement about who the subject was, so every advice and third-party frame
#: fell through.
NON_READER_FRAMES = (
    # advice and comfort, addressed to the reader
    "她让我别想太多",
    "她叫我别想太多",
    "她劝我别想太多",
    "她安慰我别想太多",
    "她提醒我别想太多",
    "她笑我想太多了",
    "她让我别自作多情",
    # third-party subjects
    "她妈妈让我别想太多",
    "我妈让我别想太多",
    "朋友都让我别想太多",
    "她闺蜜让我别想太多",
    # reported speech, direct and indirect
    "她说我想太多了",
    "她告诉我别想太多",
    "她说可能只是人好",
    "她说“我想太多了”",
    "她说她只是把我当朋友",
    "她说她不喜欢我",
    "她说她讨厌我",
    "她说她嫌我烦",
    "她说她不想理我",
    "她说她对我没兴趣",
    "她说她根本不在乎我",
    "她朋友说她不喜欢我",
    "他说她讨厌我",
    "她说“她不喜欢我”",
    "她让我别觉得她不喜欢我",
)

#: Registered residual for a later batch: the discount lexicon does not cover
#: 善良 / 就是 / 被动形式, and "她说讨厌我" needs a family that does not exist yet.
#: This batch must leave them exactly as they were.
UNTOUCHED_RESIDUALS = ("她说讨厌我",)

#: Registered residual: negation is a different frame from attribution.
NEGATION_RESIDUALS = ("我没想太多", "我没有想太多")


def ownership_guards(book: RuleBook, rule_id: str) -> list[str]:
    rule = next(item for item in book.signals if item.id == rule_id)
    return list(rule.exclude)


@pytest.mark.parametrize("text", READER_DISCOUNTS)
def test_the_readers_own_discount_stays_the_readers(analyzer: NedAnalyzer, text: str) -> None:
    """自我降权的含义不变：读者自己主动降权的那句话。"""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.signal_type == SignalType.SELF_DISCOUNT, text
    assert result.verdict.code == "ned.self_discount_noted", text


@pytest.mark.parametrize("text", READER_CONCLUSIONS)
def test_the_readers_own_conclusion_stays_the_readers(analyzer: NedAnalyzer, text: str) -> None:
    """读者自己得出的结论仍然是读者的结论，不是对方已核实的事实。"""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.signal_type == SignalType.SELF_NEGATIVE_BELIEF, text
    assert result.verdict.code == "nea.negative_conclusion", text


@pytest.mark.parametrize("text", NON_READER_FRAMES)
def test_somebody_elses_words_are_not_the_readers_stance(analyzer: NedAnalyzer, text: str) -> None:
    """别人说的、劝的、转述的话，不能改写成读者自己的立场。

    The defect: both families read a bare phrase or a bare attitude predicate, so
    "她让我别想太多" was reported as the reader's own discount and "她说她不喜欢我"
    as the reader's own conclusion. The result here is silence, not another verdict:
    this batch removes an attribution, it does not add a reading.
    """

    result = analyzer.analyze_text(text, mode="normal")
    types = {span.signal_type for span in result.evidence}
    assert SignalType.SELF_DISCOUNT not in types, text
    assert SignalType.SELF_NEGATIVE_BELIEF not in types, text
    assert result.verdict.code not in {"ned.self_discount_noted", "nea.negative_conclusion"}, text


#: The firewall's own contract: only closed-class material may precede a
#: reader-owned trigger, so an arbitrary named third party or an arbitrary
#: reporting verb cannot be admitted by construction.
FIREWALL_FRAMES = (
    "\u8001\u5e08\u8ba9",
    "\u5c0f\u738b\u8bf4",
    "\u6211\u5988\u8ba9",
    "\u5979\u8f6c\u8ff0\u8bf4",
    "\u7fa4\u91cc\u6709\u4eba\u8bf4",
    "\u7f51\u53cb\u8bf4",
)
FIREWALL_READERS = (
    "\u6211",
    "\u6211\u89c9\u5f97",
    "\u6211\u662f\u4e0d\u662f",
    "\u6211\u4e0d\u4e00\u5b9a",
    "\u53ef\u80fd",
    "\u522b",
    "\u4f46\u6211\u89c9\u5f97",
    "\u6211\u672c\u6765\u89c9\u5f97",
    "\u6211\u8ddf\u5979\u5988\u5988\u8bf4",
)


@pytest.mark.parametrize("rule_id", ["zh.self_discount", "zh.self_negative_belief"])
def test_reader_owned_families_decide_ownership_outside_the_rule_pack(
    book: RuleBook, rule_id: str
) -> None:
    """Ownership is the firewall's job, so the families carry no exclude list.

    A regex guard has to name either the people ("\u5979|\u4ed6|\u670b\u53cb") or the
    reporting verbs it knows, and both are open classes: "\u8001\u5e08\u8ba9\u6211\u522b\u60f3\u592a\u591a" and
    "\u5c0f\u738b\u63d0\u4e86\u4e00\u53e5\u5979\u4e0d\u559c\u6b22\u6211" walk straight through. The closure now lives in
    one place that answers a single question about the clause, not in a word list.
    """

    assert ownership_guards(book, rule_id) == [], rule_id


def test_the_firewall_admits_only_closed_class_prefixes() -> None:
    """Anyone's name and any reporting verb are frames by construction."""

    from ned.app.core import attribution

    assert frozenset({"self_discount", "self_negative_belief"}) == attribution.READER_OWNED_TYPES
    tail = "\u60f3\u592a\u591a\u4e86"
    for frame in FIREWALL_FRAMES:
        assert not attribution.reader_owned(frame + tail, len(frame)), frame
    for reader in FIREWALL_READERS:
        assert attribution.reader_owned(reader + tail, len(reader)), reader


#: An arbitrary named third party: never enumerated anywhere in the codebase.
ARBITRARY_THIRD_PARTIES = (
    "\u8001\u5e08\u8ba9\u6211\u522b\u60f3\u592a\u591a",
    "\u5ba4\u53cb\u53eb\u6211\u522b\u60f3\u592a\u591a",
    "\u8001\u677f\u529d\u6211\u522b\u60f3\u592a\u591a",
    "\u533b\u751f\u63d0\u9192\u6211\u522b\u60f3\u592a\u591a",
    "\u5c0f\u738b\u8bf4\u6211\u60f3\u591a\u4e86",
    "\u963f\u6770\u7b11\u6211\u60f3\u592a\u591a\u4e86",
    "\u5976\u5976\u8bf4\u6211\u60f3\u592a\u591a\u4e86",
    "\u7fa4\u4e3b\u8bf4\u6211\u60f3\u591a\u4e86",
    "\u8001\u5e08\u8bf4\u5979\u4e0d\u559c\u6b22\u6211",
    "\u5ba4\u53cb\u8bf4\u5979\u8ba8\u538c\u6211",
    "\u5c0f\u738b\u544a\u8bc9\u6211\u5979\u5acc\u6211\u70e6",
    "\u5979\u59d0\u59d0\u8bf4\u5979\u4e0d\u60f3\u7406\u6211",
    "\u7fa4\u91cc\u6709\u4eba\u8bf4\u5979\u5bf9\u6211\u6ca1\u5174\u8da3",
    "\u7f51\u53cb\u8bf4\u5979\u6839\u672c\u4e0d\u5728\u4e4e\u6211",
    "\u90bb\u5c45\u8bf4\u5979\u4e0d\u559c\u6b22\u6211",
)

#: The reader speaking to somebody: the receiver may be anybody at all.
COMPOUND_RECEIVERS = (
    "\u6211\u8ddf\u5979\u5988\u5988\u8bf4\u6211\u60f3\u592a\u591a\u4e86",
    "\u6211\u8ddf\u5979\u670b\u53cb\u8bf4\u6211\u60f3\u591a\u4e86",
    "\u6211\u548c\u5979\u59d0\u59d0\u8bf4\u6211\u522b\u81ea\u4f5c\u591a\u60c5\u4e86",
    "\u6211\u5bf9\u5ba4\u53cb\u8bf4\u6211\u60f3\u592a\u591a\u4e86",
    "\u6211\u5411\u8001\u5e08\u8bf4\u6211\u89c9\u5f97\u5979\u4e0d\u559c\u6b22\u6211",
    "\u6211\u8ddf\u5c0f\u738b\u8bf4\u5979\u8ba8\u538c\u6211",
    "\u6211\u548c\u670b\u53cb\u8bf4\u5979\u4e0d\u559c\u6b22\u6211",
)

#: Natural reporting verbs that no list in the rule pack mentions.
REPORTING_FRAMES = (
    "\u5979\u8f6c\u8ff0\u8bf4\u6211\u60f3\u592a\u591a\u4e86",
    "\u5979\u8f6c\u544a\u6211\u522b\u60f3\u592a\u591a",
    "\u5c0f\u738b\u63d0\u4e86\u4e00\u53e5\u5979\u4e0d\u559c\u6b22\u6211",
    "\u5979\u53d1\u6d88\u606f\u8bf4\u6211\u60f3\u591a\u4e86",
    "\u5979\u56de\u6211\u8bf4\u6211\u60f3\u592a\u591a",
    "\u5979\u8ddf\u522b\u4eba\u8bb2\u6211\u603b\u662f\u60f3\u592a\u591a",
    "\u5979\u5f53\u9762\u8bf4\u6211\u60f3\u592a\u591a\u4e86",
)


@pytest.mark.parametrize("text", ARBITRARY_THIRD_PARTIES)
def test_an_arbitrary_named_third_party_is_a_frame(analyzer: NedAnalyzer, text: str) -> None:
    """The guard never needs to know who the person is."""

    result = analyzer.analyze_text(text, mode="normal")
    types = {span.signal_type for span in result.evidence}
    assert SignalType.SELF_DISCOUNT not in types, text
    assert SignalType.SELF_NEGATIVE_BELIEF not in types, text


@pytest.mark.parametrize("text", COMPOUND_RECEIVERS)
def test_the_reader_may_speak_to_anybody(analyzer: NedAnalyzer, text: str) -> None:
    """A receiver that looks like a third party is still only a receiver."""

    result = analyzer.analyze_text(text, mode="normal")
    types = {span.signal_type for span in result.evidence}
    assert types & {SignalType.SELF_DISCOUNT, SignalType.SELF_NEGATIVE_BELIEF}, text


@pytest.mark.parametrize("text", REPORTING_FRAMES)
def test_a_reporting_verb_nobody_listed_is_still_a_frame(analyzer: NedAnalyzer, text: str) -> None:
    """转述 / 转告 / 提了一句 / 发消息说: the closure is structural, not lexical."""

    result = analyzer.analyze_text(text, mode="normal")
    types = {span.signal_type for span in result.evidence}
    assert SignalType.SELF_DISCOUNT not in types, text
    assert SignalType.SELF_NEGATIVE_BELIEF not in types, text


@pytest.mark.parametrize("text", UNTOUCHED_RESIDUALS)
def test_registered_residuals_are_untouched(analyzer: NedAnalyzer, text: str) -> None:
    """这些属于后续批次：本批不碰，也不得顺手改。"""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.no_signal", text


@pytest.mark.parametrize("text", NEGATION_RESIDUALS)
def test_negation_framing_is_untouched(analyzer: NedAnalyzer, text: str) -> None:
    """否定与归属是两个框架：本批只管归属，否定留给后续批次。"""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.signal_type == SignalType.SELF_DISCOUNT, text


#: Unknown reporting predicates: never enumerated anywhere, and never admitted.
#: The closure must not depend on knowing these verbs.
UNKNOWN_REPORTING_PREDICATES = (
    "\u5979\u5600\u5495\u6211\u60f3\u591a\u4e86",
    "\u5979\u5410\u69fd\u6211\u60f3\u592a\u591a\u4e86",
    "\u5979\u5ff5\u53e8\u6211\u522b\u81ea\u4f5c\u591a\u60c5",
    "\u5979\u62b1\u6028\u6211\u60f3\u592a\u591a",
    "\u5979\u56de\u4e86\u53e5\u6211\u60f3\u591a\u4e86",
    "\u5979\u8bc4\u4ef7\u6211\u60f3\u592a\u591a",
    "\u5979\u65ad\u8a00\u5979\u4e0d\u559c\u6b22\u6211",
    "\u5979\u58f0\u79f0\u5979\u4e0d\u559c\u6b22\u6211",
    "\u5979\u627f\u8ba4\u5979\u8ba8\u538c\u6211",
    "\u5979\u5f3a\u8c03\u5979\u5bf9\u6211\u6ca1\u5174\u8da3",
    "\u5979\u8865\u4e86\u4e00\u53e5\u5979\u6839\u672c\u4e0d\u5728\u4e4e\u6211",
    "\u5979\u5199\u4e86\u4e00\u53e5\u6211\u60f3\u591a\u4e86",
    "\u5979\u5600\u5495\uff1a\u201c\u4f60\u60f3\u592a\u591a\u4e86\u201d",
    "\u5979\u8bf4\u4e86\u4e00\u53e5\uff1a\u201c\u4f60\u522b\u81ea\u4f5c\u591a\u60c5\u201d",
    "\u5979\u56de\u6211\uff1a\u201c\u4f60\u60f3\u591a\u4e86\u201d",
    "\u5979\u5199\u9053\uff1a\u201c\u5979\u4e0d\u559c\u6b22\u4f60\u201d",
)

#: Reader-owned shapes that must survive the closure, including the one where the
#: reader is only the object of a preposition.
CLOSURE_SURVIVORS = (
    "\u6211\u8ddf\u5979\u8bf4\u6211\u60f3\u592a\u591a\u4e86",
    "\u6211\u8ddf\u5979\u5988\u5988\u8bf4\u6211\u60f3\u591a\u4e86",
    "\u6211\u5bf9\u5ba4\u53cb\u8bf4\u6211\u60f3\u592a\u591a\u4e86",
    "\u6211\u5411\u8001\u5e08\u8bf4\u6211\u89c9\u5f97\u5979\u4e0d\u559c\u6b22\u6211",
    "\u6211\u8ddf\u5c0f\u738b\u8bf4\u5979\u8ba8\u538c\u6211",
    "\u6211\u672c\u6765\u89c9\u5f97\u53ef\u80fd\u53ea\u662f\u4eba\u597d",
    "\u5979\u5bf9\u6211\u597d\u53ef\u80fd\u53ea\u662f\u51fa\u4e8e\u793c\u8c8c",
    "\u5979\u53ef\u80fd\u53ea\u662f\u5ba2\u6c14",
    "\u5979\u53ea\u662f\u628a\u6211\u5f53\u670b\u53cb",
)


@pytest.mark.parametrize("text", UNKNOWN_REPORTING_PREDICATES)
def test_an_unknown_reporting_predicate_is_still_a_frame(analyzer: NedAnalyzer, text: str) -> None:
    """嘀咕 / 吐槽 / 断言 / 承认 / 补了一句: no list knows these, and none is needed.

    The earlier firewalls decided a described subject was reader-owned when no *known*
    reporting verb followed it, so every verb nobody had listed walked through. The
    branch now accepts only two positive shapes — closed-class material, or the reader
    as the object of a preposition — which an unknown content word can never satisfy.
    """

    result = analyzer.analyze_text(text, mode="normal")
    types = {span.signal_type for span in result.evidence}
    assert SignalType.SELF_DISCOUNT not in types, text
    assert SignalType.SELF_NEGATIVE_BELIEF not in types, text


@pytest.mark.parametrize("text", CLOSURE_SURVIVORS)
def test_the_closure_keeps_the_reader_owned_shapes(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    types = {span.signal_type for span in result.evidence}
    assert types & {SignalType.SELF_DISCOUNT, SignalType.SELF_NEGATIVE_BELIEF}, text


def test_the_described_subject_branch_names_no_reporting_verb() -> None:
    """The closure is structural: there is no reporting-verb list left to grow."""

    from ned.app.core import attribution

    assert not hasattr(attribution, "REPORT_VERBS")
    assert attribution._reader_is_a_prepositional_object("\u5bf9\u6211\u597d") is True
    assert attribution._reader_is_a_prepositional_object("\u8ddf\u6211\u8bf4\u6211") is False
