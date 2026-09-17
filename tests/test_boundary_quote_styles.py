"""BOUNDARY-QUOTE-STYLE-1: an explicit boundary survives every Chinese quote style.

A boundary written inside the corner brackets 「」 or 『』 used to lose its author and be
dropped by the boundary firewall, and the fragment the boundary negates then leaked back as
a positive page (the screen said POSITIVE EVIDENCE DETECTED instead of the boundary screen).

These pins hold the whole contract rather than the final verdict alone: the verdict, the
screen it lands on, the boundary evidence itself, the containment outcome and the positive
mass. Every case is a fixed, hand-checked sentence; the four styles must agree.
"""

from __future__ import annotations

from typing import Any

import pytest
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import SignalType
from ned.app.ui import personality as p

BOUNDARY = "ned.direct_rejection"

#: (label, opening mark, closing mark, what she says)
STYLES = (
    ("plain", "", "", "我们还是做朋友吧"),
    ("plain-refusal", "", "", "别再联系我了"),
    ("curly", "\u201c", "\u201d", "我们还是做朋友吧"),
    ("curly-contained", "\u201c", "\u201d", "我不想见你"),
    ("corner", "\u300c", "\u300d", "我们还是做朋友吧"),
    ("corner-refusal", "\u300c", "\u300d", "别再联系我了"),
    ("corner-contained", "\u300c", "\u300d", "我不想见你"),
    ("corner-contained-partner", "\u300c", "\u300d", "她不想谈恋爱"),
    ("corner-brace", "\u300e", "\u300f", "我们还是做朋友吧"),
    ("corner-brace-contained", "\u300e", "\u300f", "我不想见你"),
)

#: A closing full stop may sit inside or outside the quotation mark.
CLOSINGS = ("", "\u3002")

#: Non-boundary families already worked inside the corner brackets; they must keep working.
OTHER_FAMILIES = (
    (
        "hostile",
        "\u5979\u8bf4\uff1a\u300c\u4f60\u4ed6\u5988\u6709\u75c5\u5427\u300d",
        SignalType.HOSTILE_EXPRESSION,
    ),
    (
        "cold reply",
        "\u5979\u8bf4\uff1a\u300c\u5c31\u56de\u4e86\u4e00\u4e2a\u55ef\u300d",
        SignalType.COLD_REPLY,
    ),
)


def situation_of(result: Any) -> str:
    """The screen this result gets, promotion included (the shared contract)."""

    signal_types = [span.signal_type.value for span in result.evidence]
    return p.screen_situation(
        p.resolve_situation(result.verdict.code),
        self_discount=any(item in p.SELF_DISCOUNT_SIGNAL_TYPES for item in signal_types),
        positive_evidence=any(span.polarity == "positive" for span in result.evidence),
        audit=result.interpretation_audit is not None,
        aspects=result.material_aspects is not None,
        reader_conclusion=any(item in p.READING_SIGNAL_TYPES for item in signal_types),
    )


def quoted(style: tuple[str, str, str, str], closing: str) -> str:
    _, opening, closing_mark, body = style
    return f"\u5979\u8bf4\uff1a{opening}{body}{closing}{closing_mark}"


@pytest.fixture
def analyzer() -> NedAnalyzer:
    return NedAnalyzer()


@pytest.mark.parametrize("closing", CLOSINGS)
@pytest.mark.parametrize(
    ("label", "opening", "closing_mark", "body"), STYLES, ids=[style[0] for style in STYLES]
)
def test_a_quoted_boundary_is_a_boundary(
    analyzer: NedAnalyzer, label: str, opening: str, closing_mark: str, body: str, closing: str
) -> None:
    """Verdict, screen and the boundary evidence itself, in every quote style."""

    text = f"\u5979\u8bf4\uff1a{opening}{body}{closing}{closing_mark}"
    result = analyzer.analyze_text(text, mode="normal")

    assert result.verdict.code == BOUNDARY, (label, text)
    assert situation_of(result) == p.SITUATION_BOUNDARY, (label, text)
    boundary = [span for span in result.evidence if span.signal_type is SignalType.DIRECT_REJECTION]
    assert boundary, (label, text)
    assert text[boundary[0].start : boundary[0].end].strip(), (label, text)


@pytest.mark.parametrize("closing", CLOSINGS)
@pytest.mark.parametrize("style", STYLES, ids=[style[0] for style in STYLES])
def test_a_quoted_boundary_contains_what_it_negates(
    analyzer: NedAnalyzer, style: tuple[str, str, str, str], closing: str
) -> None:
    """The containment outcome: nothing the boundary negates may survive as a page."""

    text = quoted(style, closing)
    result = analyzer.analyze_text(text, mode="normal")

    positives = [span for span in result.evidence if span.polarity == "positive"]
    assert positives == [], (style[0], text, [span.rule_id for span in positives])
    assert result.breakdown.positive_mass == 0.0, (style[0], text)
    assert result.breakdown.positive_information == 0.0, (style[0], text)
    assert result.material_aspects is None, (style[0], text)


def test_the_quote_styles_agree_on_the_same_content(analyzer: NedAnalyzer) -> None:
    """Parity: the markup around her sentence changes nothing about what it means."""

    for body in (
        "\u6211\u4eec\u8fd8\u662f\u505a\u670b\u53cb\u5427",
        "\u6211\u4e0d\u60f3\u89c1\u4f60",
    ):
        seen = []
        for label, opening, closing_mark, _ in STYLES:
            if body == "\u6211\u4e0d\u60f3\u89c1\u4f60" and "contained" not in label:
                continue
            text = f"\u5979\u8bf4\uff1a{opening}{body}{closing_mark}"
            result = analyzer.analyze_text(text, mode="normal")
            seen.append(
                (
                    result.verdict.code,
                    situation_of(result),
                    result.breakdown.positive_mass,
                    len(result.materials),
                    result.material_aspects is None,
                )
            )
        assert len(set(seen)) == 1, (body, seen)


@pytest.mark.parametrize(
    ("label", "text", "signal_type"), OTHER_FAMILIES, ids=[item[0] for item in OTHER_FAMILIES]
)
def test_other_families_still_fire_inside_the_corner_brackets(
    analyzer: NedAnalyzer, label: str, text: str, signal_type: SignalType
) -> None:
    """The non-boundary families were never broken; this keeps it that way."""

    result = analyzer.analyze_text(text, mode="normal")
    assert any(span.signal_type is signal_type for span in result.evidence), (label, text)
