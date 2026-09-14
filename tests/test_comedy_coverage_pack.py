"""Comedy Coverage Pack v1: the three hard lines, and the pack's new coverage.

Three rules may not be broken, however funny NED wants to be:

1. it may not say the opposite of what was written;
2. it may not joke about a stated boundary;
3. it may not certify reported speech as reality.

This file pins the pack's own work: the subject of "我想你了" (P0-b), the
negation guard on reported affection (P0-a), and the ordinary-language coverage
the pack added (P1). Repetition is deliberately NOT counted: "他发了一百遍"
is one observation, and the screen keeps saying 样本量 N=1.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ned.app.cli import captured_reading_of, screen_context
from ned.app.core.analyzer import NedAnalyzer
from ned.app.ui.personality import first_screen

RULES = Path(__file__).resolve().parent.parent / "ned" / "app" / "rules" / "signals.json"

#: A. The reader is the subject. Their own longing is not evidence about anyone.
READER_LONGING = (
    "我想你了",
    "我好想你",
    "我想见你",
    "我有点想你",
    "我每天都很想你",
)

#: D/E/F. Someone else's longing, including the quoted and repeated forms.
COUNTERPART_LONGING = (
    "她说想我了",
    "他说他最近很想我",
    "她半夜发消息说想我",
    "他对我说“我想你了”",
    "他说：“我想你。”",
    "他发消息跟我说想我了",
    "他说了好多遍想我",
    "他连续说了好多次想我",
    "他发了一百遍“想我了”",
    "他发了一百个他想我了",
    "他发了一堆“我想你了”",
)

#: F. The mirror image: the reader longing for someone else.
NOT_COUNTERPART_LONGING = ("我说了好多遍想他", "你说你想我了")

#: P0-a. A negation inside the reported clause is not a report of affection.
NEGATED_REPORT = (
    "他从来不说喜欢我 但对我很好",
    "他从来没说过喜欢我",
    "他从没说过爱我",
    "他说他不喜欢我",
)

#: P1. Ordinary ways people describe the same events.
PACK_COVERAGE: tuple[tuple[str, str], ...] = (
    ("她说我们做朋友吧", "direct_rejection"),
    ("他说我们还是保持距离吧", "direct_rejection"),
    ("他说我很好 但我们不合适", "direct_rejection"),
    ("我表白被拒了 但我还是喜欢她", "direct_rejection"),
    ("他约我周末去看电影", "meetup_invitation"),
    ("她问我周末有没有空", "meetup_invitation"),
    ("他今天第一次主动给我发消息", "initiation"),
    ("他给我点了一杯奶茶", "care"),
    ("他记得我爱吃什么", "care"),
)

#: The same widening, stated as a negation or about someone else.
WIDENING_GUARDS: tuple[tuple[str, str], ...] = (
    ("他从来不主动给我发消息", "initiation"),
    ("他没有主动给我发消息", "initiation"),
    ("他以前主动给我发消息，现在不发了", "initiation"),
    ("他从来没约我出去吃饭", "meetup_invitation"),
    ("他没约我出去", "meetup_invitation"),
    ("他没说要做朋友吧", "direct_rejection"),
    ("这个方案不合适", "direct_rejection"),
    ("公司拒绝了我的申请", "direct_rejection"),
    ("他没给我点外卖", "care"),
    ("我妈给我点了一份外卖", "care"),
    ("我妈记得我爱吃什么", "care"),
)


@pytest.fixture(scope="module")
def analyzer() -> NedAnalyzer:
    return NedAnalyzer()


@pytest.fixture(scope="module")
def rules() -> dict[str, dict[str, object]]:
    pack = json.loads(RULES.read_text(encoding="utf-8"))
    return {rule["id"]: rule for rule in pack["signals"]}


def families(result: object) -> set[str]:
    return {span.signal_type.value for span in result.evidence}  # type: ignore[attr-defined]


def positive_families(result: object) -> set[str]:
    return {
        span.signal_type.value
        for span in result.evidence  # type: ignore[attr-defined]
        if str(span.polarity) == "positive"
    }


def screen_reality(result: object) -> str:
    """The reality line a user actually reads on the 30-second screen."""

    situation, basis, language = screen_context(result)  # type: ignore[arg-type]
    screen = first_screen(
        situation,
        result.mode,  # type: ignore[attr-defined]
        language,
        basis=basis,
        reading=captured_reading_of(result),  # type: ignore[arg-type]
    )
    return screen.reality


# --------------------------------------------------------------------------- #
# hard line 1: never the opposite
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", READER_LONGING)
def test_the_readers_own_longing_is_not_external_evidence(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert positive_families(result) == set(), (text, families(result))


@pytest.mark.parametrize("text", NEGATED_REPORT)
def test_a_negated_report_is_not_a_report_of_affection(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert "explicit_affection" not in positive_families(result), text


@pytest.mark.parametrize(("text", "family"), WIDENING_GUARDS)
def test_the_new_coverage_does_not_fire_on_its_own_negation(
    analyzer: NedAnalyzer, text: str, family: str
) -> None:
    assert family not in families(analyzer.analyze_text(text, mode="normal")), text


def test_the_two_mirror_inputs_are_told_apart(analyzer: NedAnalyzer) -> None:
    """A and F: "我想你" is the reader; "她想我" is the counterpart."""

    assert positive_families(analyzer.analyze_text("我想你了", mode="normal")) == set()
    assert "explicit_affection" in families(analyzer.analyze_text("她说想我了", mode="normal"))


@pytest.mark.parametrize("text", NOT_COUNTERPART_LONGING)
def test_the_readers_mirror_never_becomes_counterpart_longing(
    analyzer: NedAnalyzer, text: str
) -> None:
    assert positive_families(analyzer.analyze_text(text, mode="normal")) == set(), text


# --------------------------------------------------------------------------- #
# counterpart longing, including the repeated phrasing
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", COUNTERPART_LONGING)
def test_counterpart_longing_is_recognised(analyzer: NedAnalyzer, text: str) -> None:
    assert positive_families(analyzer.analyze_text(text, mode="normal")), text


def test_a_quoted_counterpart_line_survives_the_subject_guard(analyzer: NedAnalyzer) -> None:
    """D: the quote is the counterpart's words, not the reader's."""

    result = analyzer.analyze_text("她对我说“我想你了”", mode="normal")
    assert "missing_you" in families(result)


def test_repetition_does_not_create_a_hundred_samples(analyzer: NedAnalyzer) -> None:
    """E: one input, one observation — even when he sent it a hundred times."""

    once = analyzer.analyze_text("他说想我了", mode="normal")
    many = analyzer.analyze_text("他发了一百遍“想我了”", mode="normal")
    assert once.signal_strength == many.signal_strength
    for result in (once, many):
        assert result.evidence, result.input
        for span in result.evidence:
            assert span.occurrences == 1, (result.input, span.rule_id)
            assert span.weight == span.base_strength, (result.input, span.rule_id)
    assert many.breakdown.positive_mass == once.breakdown.positive_mass


def test_the_hundred_times_screen_still_says_sample_size_one(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("他发了一百遍“想我了”", mode="normal")
    assert "样本量 N=1" in screen_reality(result)


# --------------------------------------------------------------------------- #
# hard line 2: a boundary stays sober, and hard line 3: a report stays a report
# --------------------------------------------------------------------------- #


def test_a_stated_downgrade_gets_the_boundary_verdict(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她说我们还是做朋友吧", mode="normal")
    assert result.verdict.code == "ned.direct_rejection"
    assert result.verdict.severity == "warning"


def test_reported_affection_is_still_hedged_as_reported(
    rules: dict[str, dict[str, object]],
) -> None:
    """Hard line 3: the copy may not turn 转述 into a fact."""

    interpretation = rules["zh.reported_affection"]["interpretations"]
    assert isinstance(interpretation, dict)
    assert "据称" in str(interpretation["zh"])


def test_the_reality_check_refuses_to_certify_a_report(analyzer: NedAnalyzer) -> None:
    """Hard line 3 again, on the line the user reads: it confirms, it does not certify."""

    result = analyzer.analyze_text("他发了一百遍“想我了”", mode="normal")
    assert "只能证明对方说了这句话" in result.reality_check


# --------------------------------------------------------------------------- #
# the pack adds coverage; it does not add families or architecture
# --------------------------------------------------------------------------- #


def test_the_rule_pack_still_holds_every_signal(rules: dict[str, dict[str, object]]) -> None:
    assert len(rules) == 38


@pytest.mark.parametrize(("text", "family"), PACK_COVERAGE)
def test_the_pack_covers_the_ordinary_phrasing(
    analyzer: NedAnalyzer, text: str, family: str
) -> None:
    assert family in families(analyzer.analyze_text(text, mode="normal")), text


# --------------------------------------------------------------------------- #
# regression: the previous correctness rounds still hold
# --------------------------------------------------------------------------- #


CONTRAST_REVERSALS = (
    "他以前秒回，现在半天才回",
    "以前他每天都聊，现在很少联系",
    "以前他总夸我，现在不夸了",
    "以前他会送我礼物，现在什么都没有",
    "以前他每天跟我说晚安，现在不说了",
    "以前我们每天聊到很晚，现在几乎不聊",
)


@pytest.mark.parametrize("text", CONTRAST_REVERSALS)
def test_the_contrast_guard_still_holds(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert positive_families(result) == set(), (text, families(result))
