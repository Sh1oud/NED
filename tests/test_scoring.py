"""Scoring tests.

The scoring model is documented arithmetic, so it gets arithmetic tests: the
formulas are checked against hand-computed values, not against NED's current
output.
"""

from __future__ import annotations

import math

import pytest
from ned.app.config import AsymmetryConfig, ScoringConfig
from ned.app.core import scoring
from ned.app.core.models import EvidenceSpan, SignalType


def span(
    weight: float, information: float, polarity: str = "positive", occurrences: int = 1
) -> EvidenceSpan:
    return EvidenceSpan(
        rule_id=f"test.{polarity}.{weight}",
        text="x",
        signal_type=SignalType.MISSING_YOU,
        label="test",
        polarity=polarity,  # type: ignore[arg-type]
        base_strength=weight,
        information_content=information,
        occurrences=occurrences,
    )


def test_clamp_bounds() -> None:
    assert scoring.clamp(-5) == 0
    assert scoring.clamp(105) == 100
    assert scoring.clamp(42, 0, 10) == 10


def test_noisy_or_of_nothing_is_zero() -> None:
    assert scoring.noisy_or([]) == 0.0


def test_noisy_or_combines_independent_evidence() -> None:
    # 1 - (1 - 0.5)(1 - 0.5) = 0.75 -> 75
    assert scoring.noisy_or([50, 50]) == pytest.approx(75.0)


def test_noisy_or_saturates_below_certainty() -> None:
    value = scoring.noisy_or([90, 90, 90, 90])
    assert value < 100
    assert value > 99


def test_noisy_or_is_order_independent() -> None:
    assert math.isclose(scoring.noisy_or([70, 20, 5]), scoring.noisy_or([5, 70, 20]))


def test_repeated_occurrences_raise_weight_with_a_cap() -> None:
    assert span(50, 10, occurrences=2).weight == pytest.approx(57.5)
    assert span(95, 10, occurrences=5).weight == 100.0


def test_positive_and_negative_mass_use_only_their_own_side() -> None:
    spans = [span(60, 50), span(90, 5, "negative"), span(70, 20, "self_discount")]
    assert scoring.positive_mass(spans) == pytest.approx(60.0)
    assert scoring.negative_mass(spans) == pytest.approx(90.0)


def test_information_content_filters_by_polarity() -> None:
    spans = [span(60, 50), span(90, 5, "negative")]
    assert scoring.information_content(spans, "positive") == 50.0
    assert scoring.information_content(spans, "negative") == 5.0


def test_negative_amplification_is_high_for_uninformative_evidence() -> None:
    # A 90-weight rule carrying 5 units of information: 100 * (1 - 5/90).
    assert scoring.negative_amplification(90, 5) == pytest.approx(94.4444, abs=1e-3)


def test_negative_amplification_is_zero_without_negative_evidence() -> None:
    assert scoring.negative_amplification(0, 0) == 0.0


def test_negative_amplification_respects_the_floor() -> None:
    assert scoring.negative_amplification(50, 50, floor=5.0) == 5.0


def test_escape_pressure_is_mean_implausibility() -> None:
    assert scoring.escape_pressure([80, 20]) == pytest.approx(0.5)
    assert scoring.escape_pressure([]) == 0.0


def test_history_pressure_is_bounded() -> None:
    assert scoring.history_pressure(0) == 0.0
    assert scoring.history_pressure(50) == 0.5
    assert scoring.history_pressure(500) == 1.0


def test_escape_capacity_grows_with_evidence_and_history() -> None:
    config = ScoringConfig()
    assert scoring.escape_capacity(config, 0, 0) == 0.0
    assert scoring.escape_capacity(config, 100, 0) == pytest.approx(0.6)
    assert scoring.escape_capacity(config, 100, 1.0) == pytest.approx(1.0)
    assert scoring.escape_capacity(config, 50, 0.5) == pytest.approx(0.5)


def test_discount_is_at_least_the_mode_baseline() -> None:
    config = ScoringConfig()
    discount, bonus = scoring.discount(config, 60, 0.0, 0.0)
    assert (discount, bonus) == (60.0, 0.0)


def test_discount_grows_when_ned_has_to_reach() -> None:
    config = ScoringConfig()
    low, _ = scoring.discount(config, 35, 0.0, 0.0)
    high, bonus = scoring.discount(config, 35, 1.0, 100.0)
    assert high > low
    assert bonus == pytest.approx(
        config.discount_escape_bonus + config.discount_amplification_bonus
    )


def test_discount_never_exceeds_hundred() -> None:
    assert scoring.discount(ScoringConfig(), 95, 1.0, 100.0)[0] == 100.0


def test_reaching_level_matches_the_documented_formula() -> None:
    config = ScoringConfig()
    level, positive, escape, history = scoring.reaching_level(config, 55, 0.5, 0.25)
    assert positive == pytest.approx(0.62 * 55)
    assert escape == pytest.approx(14.0)
    assert history == pytest.approx(5.0)
    assert level == pytest.approx(positive + escape + history)


def test_reaching_level_is_capped() -> None:
    assert scoring.reaching_level(ScoringConfig(), 100, 1.0, 1.0)[0] == 100.0


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (0, "Reasonable skepticism"),
        (12.5, "Reasonable skepticism"),
        (25, "Routine doubt"),
        (50, "Advanced overthinking"),
        (70, "Industrial-grade denial"),
        (85, "NED is currently reaching."),
        (100, "人好。👍"),
    ],
)
def test_reaching_labels(level: float, expected: str) -> None:
    assert scoring.reaching_label(ScoringConfig(), level) == expected


@pytest.mark.parametrize(
    ("value", "positive_side", "expected"),
    [
        (10, True, "EXTREMELY HIGH"),
        (40, True, "HIGH"),
        (60, True, "MODERATE"),
        (90, True, "LOW"),
        (95, False, "EXTREMELY LOW"),
        (60, False, "LOW"),
        (30, False, "MODERATE"),
        (5, False, "HIGH"),
    ],
)
def test_threshold_labels(value: float, positive_side: bool, expected: str) -> None:
    assert scoring.threshold_label(value, positive_side=positive_side) == expected


def test_threshold_labels_use_configured_band_edges() -> None:
    """Widening the band edges must move the labels with them."""

    strict = AsymmetryConfig(high_positive_threshold=10.0, low_negative_threshold=90.0)
    assert scoring.threshold_label(15.0, positive_side=True, config=strict) == "HIGH"
    assert scoring.threshold_label(85.0, positive_side=False, config=strict) == "LOW"
    assert scoring.threshold_label(95.0, positive_side=False, config=strict) == "EXTREMELY LOW"
    # With the shipped defaults, 85 crosses the EXTREMELY LOW edge.
    assert scoring.threshold_label(85.0, positive_side=False) == "EXTREMELY LOW"


def test_band_label_accepts_tuples_and_objects() -> None:
    assert scoring.band_label([(0, 49, "low"), (50, 100, "high")], 70) == "high"
    config = ScoringConfig()
    assert scoring.band_label(config.reaching_bands, 100) == "人好。👍"
    assert scoring.band_label([(0, 10, "x")], 50) == ""
