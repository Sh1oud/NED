"""Evidence Asymmetry Detector tests."""

from __future__ import annotations

from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import AsymmetryEvent, AsymmetryRequest

POSITIVE = "她主动找我聊了两个小时"
NEGATIVE = "五分钟没回复"

#: The layer verdict that replaced the retired composite verdict.
NO_READING = "evidence.reading_not_present"


def test_canonical_pair_reports_three_layers(analyzer: NedAnalyzer) -> None:
    """The classic pair: an evidence difference and a policy difference only.

    Its legacy composite is still 81.8 (kept for compatibility), but nothing in
    the new layers claims anything about the reader's standard.
    """

    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    assert result.positive is not None
    assert result.negative is not None

    profile = result.evidence_profile
    assert profile.comparable is True
    assert profile.information_gap is not None and profile.information_gap > 0.8
    assert profile.raw_strength_gap is not None and profile.raw_strength_gap < 0.1

    treatment = result.ned_treatment
    assert treatment is not None
    assert treatment.positive_discount == 35.0
    assert treatment.prior_positive == 0.35
    assert treatment.treatment_gap is not None and treatment.treatment_gap > 0.6

    reading = result.user_interpretation
    assert reading.status == "not_present"
    assert reading.reading_present is False
    assert reading.double_standard is False
    assert reading.interpretive_score is None

    assert result.asymmetry_score_is_legacy is True
    assert result.verdict.code == NO_READING
    assert "不评估你的证据标准" in result.verdict.text


def test_canonical_pair_treatment_favours_the_negative_reading(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    assert result.ned_treatment is not None
    treated_positive = result.ned_treatment.positive_treated_weight
    treated_negative = result.ned_treatment.negative_treated_weight
    assert treated_positive is not None and treated_negative is not None
    assert treated_negative > treated_positive * 3
    assert (
        result.evidence_profile.positive_information > result.evidence_profile.negative_information
    )


def test_reality_check_compares_the_two_descriptions(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    assert "2" in result.reality_check
    assert "5" in result.reality_check
    assert result.reality_check.strip()


def test_the_legacy_sub_scores_are_still_exposed(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    assert set(result.sub_scores) == {"weight_gap", "information_gap", "categorical"}
    for value in result.sub_scores.values():
        assert 0.0 <= value <= 1.0
    # and they are marked as the legacy view rather than the contract
    assert result.asymmetry_score_is_legacy is True


def test_the_legacy_verdict_no_longer_fires(analyzer: NedAnalyzer) -> None:
    """``asymmetry.detected`` waits on a key the engine no longer supplies."""

    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    assert result.verdict.code != "asymmetry.detected"
    assert result.verdict.code == NO_READING


def test_an_unmatched_negative_side_is_reported_as_insufficient(analyzer: NedAnalyzer) -> None:
    """No negative rule matches, so no comparison happened at all.

    This used to report a score of 0.0, which reads as "compared, and the
    standards are symmetric". The two states are now separate: no comparison
    means no score.
    """

    result = analyzer.asymmetry.compare(
        positive_text="她主动找我聊了两个小时",
        negative_text="她跟我说她最近很忙，要加班到很晚",
    )
    assert result.negative is None
    assert result.comparison_applicable is False
    assert result.comparison_reason == "insufficient_input"
    assert result.asymmetry_score is None
    assert result.asymmetry_label == "INSUFFICIENT_INPUT"
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
    assert result.comparison_applicable is False
    assert result.comparison_reason == "insufficient_input"
    assert result.asymmetry_score is None
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


def test_an_interpretation_never_touches_evidence_or_policy(analyzer: NedAnalyzer) -> None:
    """A supplied reading belongs to the reader layer, and to nothing else."""

    plain = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=NEGATIVE)
    discounted = analyzer.asymmetry.compare(
        positive_text=POSITIVE,
        negative_text=NEGATIVE,
        positive_interpretation="可能只是人好",
    )
    assert plain.evidence_profile == discounted.evidence_profile, (
        "the reading must not move the evidence profile"
    )
    assert plain.ned_treatment == discounted.ned_treatment, (
        "the reading must not move NED's own policy"
    )
    assert plain.user_interpretation.status == "not_present"
    assert discounted.user_interpretation.status == "partial_basis"
    assert discounted.user_interpretation.positive_self_discount_present is True


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


def test_self_discount_is_the_readers_words_not_negative_evidence(
    analyzer: NedAnalyzer,
) -> None:
    """The old model used the discount as the rejection side. It no longer does."""

    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text="可能只是人好")
    assert result.negative is None
    # the negative box held only positive-side language, so that side is empty
    assert result.comparison_reason == "insufficient_input"
    assert result.user_interpretation.positive_self_discount_present is True
    assert result.user_interpretation.negative_self_conclusion_present is False
    assert result.evidence_profile.negative_raw_strength is None


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
