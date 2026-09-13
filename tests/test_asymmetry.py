"""Evidence Asymmetry Detector tests."""

from __future__ import annotations

from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import AsymmetryEvent, AsymmetryRequest

POSITIVE = "她主动找我聊了两个小时"
NEGATIVE = "五分钟没回复"


def test_canonical_pair_produces_a_high_score(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    assert result.positive is not None
    assert result.negative is not None
    assert result.asymmetry_score >= 75
    assert result.asymmetry_label == "EXTREME"
    assert result.positive_threshold == "EXTREMELY HIGH"
    assert result.negative_threshold == "EXTREMELY LOW"


def test_canonical_pair_weights_favour_the_negative_reading(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    assert result.positive is not None
    assert result.negative is not None
    assert result.negative.weight > result.positive.weight * 3
    assert result.positive.information_content > result.negative.information_content


def test_reality_check_compares_the_two_descriptions(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    assert "2" in result.reality_check
    assert "5" in result.reality_check
    assert result.reality_check.strip()


def test_sub_scores_are_exposed_and_bounded(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    assert set(result.sub_scores) == {"weight_gap", "information_gap", "categorical"}
    for value in result.sub_scores.values():
        assert 0.0 <= value <= 1.0


def test_verdict_fires_on_the_asymmetry_rule(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    assert result.verdict.code == "asymmetry.detected"
    assert result.verdict.severity == "chaos"


def test_balanced_evidence_scores_low(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(
        positive_text="她主动找我聊了两个小时",
        negative_text="她跟我说她最近很忙，要加班到很晚",
    )
    assert result.asymmetry_score < 60
    assert result.verdict.code != "asymmetry.detected"


def test_milder_asymmetry_scores_lower_than_the_canonical_case(analyzer: NedAnalyzer) -> None:
    """The score must discriminate, not just fire."""

    canonical = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    milder = analyzer.asymmetry.compare(
        positive_text=POSITIVE, negative_text="她说临时有事，改天吧"
    )
    assert milder.positive is not None
    assert milder.negative is not None
    assert milder.asymmetry_score < canonical.asymmetry_score
    assert milder.asymmetry_label in {"MILD", "MODERATE", "SEVERE"}


def test_one_sided_input_is_reported_as_insufficient(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text="")
    assert result.negative is None
    assert result.asymmetry_label == "INSUFFICIENT_INPUT"
    assert result.asymmetry_score == 0.0
    assert result.sub_scores == {}
    assert "两份证据" in result.reality_check or "two pieces" in result.reality_check


def test_no_input_at_all_is_insufficient(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(positive_text="", negative_text="")
    assert result.positive is None
    assert result.negative is None
    assert result.verdict.code == "ned.no_signal"


def test_free_text_is_split_into_clauses(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.from_text("她主动找我聊了两个小时，但消息发出去五分钟没回复")
    assert result.positive is not None
    assert result.negative is not None
    assert result.positive.signal_type.value in {"initiation", "sustained_interaction"}
    assert result.asymmetry_score > 40


def test_free_text_with_one_side_reports_insufficient(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.from_text("她主动找我聊了两个小时")
    assert result.negative is None
    assert result.asymmetry_label == "INSUFFICIENT_INPUT"


def test_explicit_interpretations_change_the_weights(analyzer: NedAnalyzer) -> None:
    plain = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    discounted = analyzer.asymmetry.compare(
        positive_text=POSITIVE,
        negative_text=NEGATIVE,
        positive_interpretation="可能只是人好",
    )
    assert plain.positive is not None
    assert discounted.positive is not None
    assert discounted.positive.discount_applied > plain.positive.discount_applied


def test_events_request_labels_are_honoured(analyzer: NedAnalyzer) -> None:
    request = AsymmetryRequest(
        events=[
            AsymmetryEvent(text=POSITIVE, label="positive"),
            AsymmetryEvent(text=NEGATIVE, label="negative"),
        ]
    )
    result = analyzer.compare(request)
    assert result.positive is not None
    assert result.negative is not None
    assert result.asymmetry_score > 50


def test_events_request_auto_classifies(analyzer: NedAnalyzer) -> None:
    request = AsymmetryRequest(
        events=[AsymmetryEvent(text=POSITIVE), AsymmetryEvent(text=NEGATIVE)]
    )
    result = analyzer.compare(request)
    assert result.positive is not None
    assert result.negative is not None


def test_text_request_shape_works(analyzer: NedAnalyzer) -> None:
    request = AsymmetryRequest(text=f"{POSITIVE}，但{NEGATIVE}")
    result = analyzer.compare(request)
    assert result.asymmetry_score > 40


def test_self_discount_can_act_as_the_rejection_side(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text="可能只是人好")
    assert result.negative is not None
    assert result.negative.signal_type.value == "self_discount"
    assert result.negative.amplification_applied > 50


def test_english_pair_works(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(
        positive_text="She texted me first and we talked for two hours",
        negative_text="5 minutes without a reply",
    )
    assert result.positive is not None
    assert result.negative is not None
    assert result.asymmetry_score > 50


def test_asymmetry_result_is_deterministic(analyzer: NedAnalyzer) -> None:
    first = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    second = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    assert first.model_dump(exclude={"generated_at"}) == second.model_dump(exclude={"generated_at"})


def test_asymmetry_carries_the_disclaimer(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    assert "cannot determine whether someone likes you" in result.disclaimer
