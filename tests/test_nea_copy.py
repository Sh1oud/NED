"""NEA copy norm: every amplified reading is the reader's over-reading.

The Negative Evidence Amplifier panel shows the inflated interpretation under
test, next to the reality check that says what it is worth. A reading that reads
like NED's own conclusion is therefore a defect rather than a style preference,
and it is the defect the boundary fix exposed. The norm is enforced across the
whole pack so that a new negative rule cannot skip it.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.rules import RuleBook
from ned.app.core.scoring import negative_amplification, noisy_or
from ned.app.core.theories import NEA_FALLBACK_READING
from ned.app.ui.personality import NEA_FRAMING

#: Wording that would turn the reading into a claim of NED's own.
CERTAINTY_TOKENS = {
    "zh": ("说明", "证明", "已经确定", "可以断定", "毫无疑问", "事实是"),
    "en": ("means", "proves", "definitely", "certainly", "is over", "the truth is"),
}

#: Wording that attributes the reading to the reader instead.
SUBJECTIVE_TOKENS = {
    "zh": ("我是不是开始觉得", "可能", "觉得"),
    "en": ("am i starting to feel", "might", "feel"),
}

#: Extreme conclusions a reading may contain, but only inside the frame.
EXTREME_CLAIMS = {
    "zh": ("不想理我", "已经不在乎", "已经结束", "不想见我", "没有余地"),
    "en": (
        "do not want to talk to me",
        "stopped caring",
        "has ended",
        "never really wanted",
        "no room left",
    ),
}

#: Every negative family must carry a reading, in both display languages.
REQUIRED_FAMILIES = (
    "response_latency",
    "self_negative_belief",
    "cold_reply",
    "plan_cancelled",
    "direct_rejection",
    "hostile_expression",
)

#: (input, family, verdict). Every family now owns a verdict, so no input with a
#: detected signal can fall through to the catch-all.
FAMILY_CASES = (
    ("消息发出去五分钟没回复", "response_latency", "nea.latency_insufficient"),
    ("她不喜欢我，根本不在乎我", "self_negative_belief", "nea.negative_conclusion"),
    ("她就回了一个嗯", "cold_reply", "nea.cold_reply_insufficient"),
    ("她临时说有事，改天吧", "plan_cancelled", "nea.plan_cancelled_insufficient"),
    ("他让我滚出去别烦他了", "direct_rejection", "ned.direct_rejection"),
    ("她怒骂我", "hostile_expression", "nea.hostile_expression_insufficient"),
)


def readings(book: RuleBook) -> list[tuple[str, str, str]]:
    """Return ``(rule_id, language, text)`` for every amplified reading."""

    rows: list[tuple[str, str, str]] = []
    for rule in book.signals:
        mapping = rule.amplified_interpretation or {}
        for language, text in sorted(mapping.items()):
            if text:
                rows.append((rule.id, language, text))
    return rows


def test_the_pack_carries_a_reading_for_every_negative_family(book: RuleBook) -> None:
    for family in REQUIRED_FAMILIES:
        rules = [rule for rule in book.signals if rule.signal_type.value == family]
        assert rules, f"no rule carries the {family} signal"
        for language in ("zh", "en"):
            assert any((rule.amplified_interpretation or {}).get(language) for rule in rules), (
                f"{family} has no {language} amplified reading"
            )


def test_every_amplified_reading_uses_the_subjective_frame(book: RuleBook) -> None:
    """The reading belongs to the reader's head, not to NED's report."""

    offenders = [
        f"{rule_id} [{language}]: {text}"
        for rule_id, language, text in readings(book)
        if not any(token in text.lower() for token in SUBJECTIVE_TOKENS[language])
    ]
    assert not offenders, "readings without a subjective frame:\n  " + "\n  ".join(offenders)


def test_no_amplified_reading_reads_like_a_finding(book: RuleBook) -> None:
    offenders = [
        f"{rule_id} [{language}]: {text}"
        for rule_id, language, text in readings(book)
        for token in CERTAINTY_TOKENS[language]
        if token in text.lower()
    ]
    assert not offenders, "readings that assert a fact:\n  " + "\n  ".join(offenders)


def test_extreme_claims_stay_inside_the_subjective_frame(book: RuleBook) -> None:
    """An extreme conclusion is allowed only after the attribution."""

    problems: list[str] = []
    for rule_id, language, text in readings(book):
        lowered = text.lower()
        markers = [
            lowered.index(token) for token in SUBJECTIVE_TOKENS[language] if token in lowered
        ]
        for claim in EXTREME_CLAIMS[language]:
            if claim in lowered and (not markers or lowered.index(claim) < min(markers)):
                problems.append(f"{rule_id} [{language}]: {text}")
    assert not problems, "claims asserted before the frame:\n  " + "\n  ".join(problems)


def test_the_display_fallback_also_uses_the_subjective_frame() -> None:
    """A rule pack without a reading of its own must not fall back to an assertion."""

    for language, text in NEA_FALLBACK_READING.items():
        assert any(token in text.lower() for token in SUBJECTIVE_TOKENS[language]), text
        for token in CERTAINTY_TOKENS[language]:
            assert token not in text.lower(), f"{token!r} in {text!r}"


@pytest.mark.parametrize(("text", "family", "verdict"), FAMILY_CASES)
def test_the_copy_is_not_an_input_to_scoring(
    analyzer: NedAnalyzer, text: str, family: str, verdict: str
) -> None:
    """The reading is display copy: the numbers still come from the spans alone."""

    result = analyzer.analyze_text(text, mode="normal")
    negatives = [span for span in result.evidence if span.polarity == "negative"]
    assert negatives, text

    recomputed = negative_amplification(
        noisy_or([span.weight for span in negatives]),
        noisy_or([span.information_content for span in negatives]),
        analyzer.book.scoring.negative_amplification_floor,
    )
    assert result.signal_type.value == family
    assert result.negative_evidence_amplification == pytest.approx(recomputed)
    assert result.verdict.code == verdict

    # The reading appears in exactly one place: it never leaks into the verdict
    # or into the reality check that judges it.
    assert result.irrational_amplification
    assert result.irrational_amplification not in result.verdict.text
    assert result.irrational_amplification not in result.reality_check


def test_ui_framing_is_still_shipped(client: TestClient) -> None:
    """The panel keeps saying what the reading is, and what it is not."""

    body = client.get("/").text
    assert 'id="nea-framing"' in body

    match = re.search(r'<script id="personality-catalog"[^>]*>(.*?)</script>', body, re.DOTALL)
    assert match, "the personality catalog script tag is missing"
    assert json.loads(match.group(1))["nea_framing"] == NEA_FRAMING
