"""Analyzer tests.

These are the behavioural tests that matter: the classic inputs, the three
modes, the escalation across turns, and the honesty guarantees (NED never claims
to know what anyone feels).
"""

from __future__ import annotations

import pytest
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import AnalyzeRequest, SignalType


def test_ordinary_positive_text(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("我想你了", mode="normal")
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
    normal = analyzer.analyze_text("我想你了", mode="normal")
    extreme = analyzer.analyze_text("我想你了", mode="extreme")
    assert extreme.positive_evidence_discount > normal.positive_evidence_discount
    assert len(extreme.alternative_explanations) >= len(normal.alternative_explanations)
    assert extreme.mode == "extreme"


def test_scientific_mode_uses_formal_verdict(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("我想你了", mode="scientific")
    assert result.verdict.code == "ned.scientific_insufficient_sample"
    assert "样本量" in result.verdict.text
    assert any("peer review" in note for note in result.mode_notes)


def test_evidence_strength_is_monotonic_in_the_wording(analyzer: NedAnalyzer) -> None:
    weak = analyzer.analyze_text("她夸我好看", mode="normal")
    medium = analyzer.analyze_text("我想你了", mode="normal")
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
    assert result.asymmetry.asymmetry_score >= 60
    assert result.verdict.code == "asymmetry.detected"
    assert result.asymmetry_reality_check.strip()
    assert result.breakdown.asymmetry_score is not None


def test_self_discount_plus_positive_evidence_is_an_asymmetry(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她主动找我聊了两个小时，但可能只是人好", mode="normal")
    assert result.asymmetry is not None
    assert result.asymmetry.negative is not None
    assert result.asymmetry.positive is not None


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
    first = analyzer.analyze_text("我想你了", mode="extreme", history=["我喜欢你"])
    second = analyzer.analyze_text("我想你了", mode="extreme", history=["我喜欢你"])
    assert first.model_dump(exclude={"generated_at"}) == second.model_dump(exclude={"generated_at"})


def test_every_report_carries_the_disclaimer(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("我喜欢你", mode="normal")
    assert "cannot determine whether someone likes you" in result.disclaimer
    assert result.engine.offline is True
    assert result.engine.provider == "local-rule"


def test_analyze_request_model_round_trips(analyzer: NedAnalyzer) -> None:
    request = AnalyzeRequest(text="我想你了", mode="extreme", history=["我也想你"])
    result = analyzer.analyze(request)
    assert result.input == "我想你了"
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
    "我想你了",
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
