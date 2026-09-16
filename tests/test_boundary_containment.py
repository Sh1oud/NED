"""BATCH 4 / AS-1: an explicit boundary owns the proposition inside it.

"她不想见你" is not "她" + "想见你": the positive fragment is part of the negated
proposition the boundary states, so it may not become material, weight or a page. The
other half of the contract is that a boundary does not delete the rest of the reality:
material that merely shares the sentence survives.
"""

from __future__ import annotations

import pathlib

import pytest
from ned.app.core.analyzer import NedAnalyzer

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BOUNDARY = "ned.direct_rejection"

#: The fragment is inside the boundary's own proposition: it must disappear.
NESTED_POSITIVE_FRAGMENTS = (
    "她说她不想谈恋爱",
    "她不想见你",
    "她说：“我不想见你”",
    "她明确说不想谈恋爱",
    "她跟我说不想见我",
    "她说不想谈恋爱，但她很喜欢我",
)

#: An independent positive in the same sentence must survive the suppression.
INDEPENDENT_POSITIVES = (
    "她给我买了早餐，但她说不想见我",
    "她说她很喜欢我，但不想谈恋爱",
    "她说：“我喜欢你，但我不想谈恋爱”",
    "她主动找我聊了两个小时，但她最后说不想谈恋爱",
)


@pytest.fixture
def analyzer() -> NedAnalyzer:
    return NedAnalyzer()


@pytest.mark.parametrize("text", NESTED_POSITIVE_FRAGMENTS)
def test_a_boundary_does_not_fragment_into_a_positive_page(
    analyzer: NedAnalyzer, text: str
) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == BOUNDARY, text
    assert [span for span in result.evidence if span.polarity == "positive"] == [], text
    assert result.material_aspects is None, text
    assert result.breakdown.positive_mass == 0.0, text
    assert result.breakdown.positive_information == 0.0, text


@pytest.mark.parametrize("text", INDEPENDENT_POSITIVES)
def test_independent_positive_material_survives_the_boundary(
    analyzer: NedAnalyzer, text: str
) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    positives = [span for span in result.evidence if span.polarity == "positive"]
    assert positives, text
    assert result.breakdown.positive_mass > 0.0, text


def test_the_gift_page_is_not_contained_by_the_boundary(analyzer: NedAnalyzer) -> None:
    """The two materials share a sentence and do not contain each other."""

    text = "她给我买了早餐，但她说不想见我"
    result = analyzer.analyze_text(text, mode="normal")
    gift = next(span for span in result.evidence if span.rule_id == "zh.gift")
    boundary = next(span for span in result.evidence if span.rule_id == "zh.direct_rejection")
    assert gift.end <= boundary.start, (gift.start, gift.end, boundary.start)
    assert result.material_aspects is not None
    assert len(result.material_aspects.materials) == 2


@pytest.mark.parametrize(
    "text",
    ("她说她想谈恋爱", "她说她很喜欢我", "她说她很喜欢我，但我们也聊得很开心"),
)
def test_a_positive_without_a_boundary_is_untouched(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    positives = [span for span in result.evidence if span.polarity == "positive"]
    assert positives, text
    assert result.verdict.code != BOUNDARY, text


def test_the_containment_rule_is_structural() -> None:
    """Offsets and polarity only: no word list, and no global overlap dedup."""

    source = (REPO_ROOT / "ned" / "app" / "core" / "parser.py").read_text(encoding="utf-8")
    start = source.index("def _drop_boundary_contained_positives")
    end = source.index("def split_clauses")
    rule = source[start:end]
    # the docstring may cite example sentences; the rule itself may not name words
    body = rule.split('"""')[2] if rule.count('"""') >= 2 else rule
    for word in ("谈恋爱", "想见你", "喜欢你", "朋友", "距离"):
        assert word not in body, word
    assert 'span.polarity == "positive"' in body
    assert "start <= span.start and span.end <= end" in body
    assert "SignalType.DIRECT_REJECTION" in body
    # and it is wired into detect()
    assert "_drop_boundary_contained_positives(spans)" in source
