"""Parser tests: language detection, durations, rule matching, degradation."""

from __future__ import annotations

import pytest
from ned.app.core import parser
from ned.app.core.models import SignalType
from ned.app.core.rules import RuleBook


def rules_of(book: RuleBook, text: str) -> set[str]:
    return {span.rule_id for span in parser.detect(text, book)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("我想你了", "zh"),
        ("I miss you", "en"),
        ("She texted me first 她说喜欢我", "zh"),
        ("", "unknown"),
        ("12345 !!!", "unknown"),
    ],
)
def test_language_detection(text: str, expected: str) -> None:
    assert parser.detect_language(text) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("五", 5), ("十", 10), ("十五", 15), ("二十", 20), ("二十五", 25), ("两", 2), ("半", 0.5)],
)
def test_chinese_number_parsing(raw: str, expected: float) -> None:
    assert parser.parse_cn_number(raw) == expected


def test_unknown_chinese_number_is_none() -> None:
    assert parser.parse_cn_number("若干") is None


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("五分钟没回复", 300),
        ("等了两个小时", 7200),
        ("半个小时", 1800),
        ("5 minutes without a reply", 300),
        ("talked for two hours", 7200),
        ("half an hour later", 1800),
    ],
)
def test_duration_extraction(text: str, seconds: float) -> None:
    durations = parser.extract_durations(text)
    assert durations, text
    assert any(abs(duration.seconds - seconds) < 1 for duration in durations), durations


def test_human_duration_localizes() -> None:
    duration = parser.extract_durations("五分钟没回复")[0]
    assert parser.human_duration(duration, "zh") == "5 分钟"
    assert parser.human_duration(duration, "en") == "5 minutes"
    assert parser.human_duration(None, "zh") == "—"


def test_detect_finds_positive_signal(book: RuleBook) -> None:
    spans = parser.detect("我想你了", book)
    assert [span.rule_id for span in spans] == ["zh.miss_you"]
    assert spans[0].signal_type == SignalType.MISSING_YOU
    assert spans[0].polarity == "positive"


def test_detect_marks_negative_latency_with_duration(book: RuleBook) -> None:
    spans = parser.detect("消息发出去五分钟没回复", book)
    latency = next(span for span in spans if span.rule_id == "zh.response_latency")
    assert latency.polarity == "negative"
    assert latency.duration is not None
    assert latency.description == "未回复，持续约 5 分钟"
    assert latency.information_content < latency.base_strength / 5


def test_detect_gives_localized_labels(book: RuleBook) -> None:
    chinese = parser.detect("我想你了", book)[0]
    english = parser.detect("I miss you", book)[0]
    assert "想念" in chinese.label
    assert "miss" in english.label.lower()


def test_overlapping_patterns_are_not_counted_as_repetition(book: RuleBook) -> None:
    """Two patterns matching the same phrase must not double the evidence."""

    spans = parser.detect("她说喜欢我", book)
    reported = next(span for span in spans if span.rule_id == "zh.reported_affection")
    assert reported.occurrences == 1
    assert reported.weight == reported.base_strength


def test_genuine_repetition_increases_weight(book: RuleBook) -> None:
    spans = parser.detect("我想你了我又想你了", book)
    miss = next(span for span in spans if span.rule_id == "zh.miss_you")
    assert miss.occurrences == 2
    assert miss.weight > miss.base_strength


def test_exclusions_suppress_matches(book: RuleBook) -> None:
    assert "zh.miss_you" not in rules_of(book, "我不太想你")
    assert "zh.explicit_affection" not in rules_of(book, "我不喜欢你")


def test_negative_exclusion_does_not_kill_a_different_signal(book: RuleBook) -> None:
    found = rules_of(book, "我不太想你，但我喜欢你")
    assert "zh.miss_you" not in found
    assert "zh.explicit_affection" in found


def test_primary_span_prefers_positive_evidence(book: RuleBook) -> None:
    spans = parser.detect("她主动找我聊了两个小时，但五分钟没回复", book)
    primary = parser.primary_span(spans)
    assert primary is not None
    assert primary.polarity == "positive"


def test_primary_span_falls_back_to_the_negative_side(book: RuleBook) -> None:
    spans = parser.detect("五分钟没回复，她不想理我", book)
    primary = parser.primary_span(spans)
    assert primary is not None
    assert primary.polarity == "negative"


def test_primary_span_of_nothing_is_none(book: RuleBook) -> None:
    assert parser.primary_span(parser.detect("今天天气不错", book)) is None


def test_raw_interpretation_degrades_for_unknown_input(book: RuleBook) -> None:
    text = parser.raw_interpretation(None, book, "zh")
    assert text.strip()
    assert "没有检测到" in text


def test_split_clauses_splits_on_punctuation() -> None:
    clauses = parser.split_clauses("她主动找我聊了两个小时，但五分钟没回复。我觉得她不想理我！")
    assert len(clauses) >= 3


def test_signal_type_of_unknown_is_none(book: RuleBook) -> None:
    assert parser.signal_type_of(parser.detect("今天开会三小时", book)) is SignalType.NONE


def test_unknown_input_degrades_gracefully(book: RuleBook) -> None:
    """No rule matches, and nothing raises."""

    for text in ("", "   ", "?????", "今晚吃什么呢", "🫠🫠🫠"):
        spans = parser.detect(text, book)
        assert isinstance(spans, list)
