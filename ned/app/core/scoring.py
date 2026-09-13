"""The transparent scoring model.

Every number NED reports is computed here from a small set of documented
formulas, and every intermediate value is exposed in the report's ``breakdown``
so anyone can check the arithmetic. The comedy comes from what the numbers
mean, not from hiding them.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ned.app.config import AsymmetryConfig, ScoringConfig
from ned.app.core.models import Duration, EvidenceSpan, ScoringBreakdown
from ned.app.core.parser import human_duration


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp ``value`` into ``[low, high]``."""

    return max(low, min(high, value))


def noisy_or(values: Iterable[float]) -> float:
    """Combine independent evidence strengths, saturating below 100.

    Two weak independent signals should add up to something stronger than
    either, but never to certainty. Each signal is treated as a probability
    mass: ``P = 1 - Π(1 - pᵢ)``.
    """

    remaining = 1.0
    for value in values:
        remaining *= 1.0 - clamp(value) / 100.0
    return round(clamp(100.0 * (1.0 - remaining)), 4)


def positive_mass(spans: Sequence[EvidenceSpan]) -> float:
    """Accumulated strength of all positive evidence."""

    return noisy_or([span.weight for span in spans if span.polarity == "positive"])


def negative_mass(spans: Sequence[EvidenceSpan]) -> float:
    """Accumulated strength of all negative evidence, as the input frames it."""

    return noisy_or([span.weight for span in spans if span.polarity == "negative"])


def information_content(spans: Sequence[EvidenceSpan], polarity: str) -> float:
    """Accumulated *real* information carried by one side of the evidence."""

    return noisy_or([span.information_content for span in spans if span.polarity == polarity])


def negative_amplification(mass: float, information: float, floor: float = 5.0) -> float:
    """How much a negative reading over-reads its own evidence, 0-100.

    ``100 · (1 − information / mass)``: evidence that carries almost no
    information but carries near-maximal weight is the definition of
    amplification. With no negative evidence there is nothing to amplify, and
    with any negative evidence the amplification never falls below ``floor``.
    """

    if mass <= 0:
        return 0.0
    ratio = clamp(information) / max(mass, 1.0)
    raw = 100.0 * (1.0 - ratio)
    return round(clamp(max(raw, clamp(floor))), 4)


def history_pressure(history_mass: float) -> float:
    """Turn the accumulated strength of earlier turns into a 0-1 pressure."""

    return round(clamp(history_mass / 100.0, 0.0, 1.0), 4)


def escape_capacity(config: ScoringConfig, mass: float, pressure: float) -> float:
    """How close NED is to running out of alternative explanations, 0-1.

    Strong evidence and a long history of strong evidence both consume NED's
    capacity to keep explaining things away.
    """

    return round(
        clamp(
            config.capacity_positive_weight * (clamp(mass) / 100.0)
            + config.capacity_history_weight * clamp(pressure, 0.0, 1.0),
            0.0,
            1.0,
        ),
        4,
    )


def escape_pressure(plausibilities: Sequence[float]) -> float:
    """Mean implausibility of the explanations NED had to resort to, 0-1."""

    if not plausibilities:
        return 0.0
    mean = sum(clamp(100.0 - value) for value in plausibilities) / len(plausibilities)
    return round(clamp(mean / 100.0, 0.0, 1.0), 4)


def discount(
    config: ScoringConfig,
    discount_base: float,
    escape_press: float,
    amplification: float,
) -> tuple[float, float]:
    """Positive evidence discount, plus the escape-pressure component.

    NED starts from the mode's baseline discount — the amount of your evidence
    it discards before reading it — and then discounts *more* when it has had to
    reach for strained explanations, which is exactly backwards as reasoning and
    exactly right as satire.
    """

    bonus = config.discount_escape_bonus * clamp(escape_press, 0.0, 1.0) + (
        config.discount_amplification_bonus * clamp(amplification) / 100.0
    )
    return round(clamp(discount_base + bonus), 4), round(bonus, 4)


def reaching_level(
    config: ScoringConfig, mass: float, escape_press: float, pressure: float
) -> tuple[float, float, float, float]:
    """NED Reaching Level plus its three additive terms.

    ``reaching = 0.62·positive_mass + 28·escape_pressure + 20·history_pressure``
    (all terms clamped; total clamped to 0-100).
    """

    positive_term = config.reaching_positive_weight * clamp(mass)
    escape_term = config.reaching_escape_weight * clamp(escape_press, 0.0, 1.0)
    history_term = config.reaching_history_weight * clamp(pressure, 0.0, 1.0)
    total = clamp(positive_term + escape_term + history_term)
    return (
        round(total, 4),
        round(positive_term, 4),
        round(escape_term, 4),
        round(history_term, 4),
    )


def band_label(bands: Sequence[tuple[float, float, str]] | Sequence[object], value: float) -> str:
    """Look up a label band for ``value``.

    Accepts either ``(min, max, label)`` tuples or objects with ``min``/``max``/
    ``label`` attributes (the pydantic band models).
    """

    for band in bands:
        if isinstance(band, tuple):
            low, high, label = band
        else:
            low = getattr(band, "min", 0.0)
            high = getattr(band, "max", 100.0)
            label = getattr(band, "label", "")
        if low <= value <= high:
            return str(label)
    return ""


def reaching_label(config: ScoringConfig, level: float) -> str:
    """Human label for a NED Reaching Level."""

    return band_label(config.reaching_bands, level)


def threshold_label(
    value: float, *, positive_side: bool, config: AsymmetryConfig | None = None
) -> str:
    """Describe an evidence threshold implied by a weight.

    A *low* positive weight means the bar for believing good news is high.
    A *high* negative weight means the bar for believing bad news is on the
    floor. Both are stated in the same vocabulary on purpose, so the report can
    place them next to each other.
    """

    high = config.high_positive_threshold if config is not None else 25.0
    low = config.low_negative_threshold if config is not None else 75.0
    if positive_side:
        if value < high:
            return "EXTREMELY HIGH"
        if value < high * 2:
            return "HIGH"
        if value < low:
            return "MODERATE"
        return "LOW"
    midpoint = (high + low) / 2.0
    if value > low:
        return "EXTREMELY LOW"
    if value > midpoint:
        return "LOW"
    if value > high:
        return "MODERATE"
    return "HIGH"


def describe_evidence(span: EvidenceSpan | None, language: str, fallback: str = "") -> str:
    """Human description of one evidence span, duration included when known."""

    if span is None:
        return fallback
    if span.description:
        return span.description
    if span.duration is not None:
        return f"{span.label} ({human_duration(span.duration, language)})"
    return span.label


def duration_label(spans: Sequence[EvidenceSpan], language: str) -> str:
    """Best available duration string across a set of spans."""

    for span in spans:
        if span.duration is not None:
            return human_duration(span.duration, language)
    return "—"


def nearest_duration(spans: Sequence[EvidenceSpan]) -> Duration | None:
    for span in spans:
        if span.duration is not None:
            return span.duration
    return None


def empty_breakdown() -> ScoringBreakdown:
    """A zeroed breakdown, used by the no-signal path."""

    return ScoringBreakdown()


__all__ = [
    "band_label",
    "clamp",
    "describe_evidence",
    "discount",
    "duration_label",
    "empty_breakdown",
    "escape_capacity",
    "escape_pressure",
    "history_pressure",
    "information_content",
    "nearest_duration",
    "negative_amplification",
    "negative_mass",
    "noisy_or",
    "positive_mass",
    "reaching_label",
    "reaching_level",
    "threshold_label",
]
