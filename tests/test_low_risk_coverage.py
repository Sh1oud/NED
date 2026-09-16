"""BATCH 5.1: five existing-family Chinese coverage gaps.

Each family pins its approved positives and its negative controls, so widening the
wording never widens the semantics: an ordinary explanation stays an explanation, a
latency wording stays latency, a private conclusion stays the reader's own conclusion,
and 不该/不应该 only counts when the reader is the one saying it.
"""

from __future__ import annotations

import pathlib

from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.parser import detect
from ned.app.core.rules import RuleBook

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

A1_POSITIVE = ("她只是善良", "她心善而已", "她对谁都这么好", "她不好意思拒绝", "她对我客气而已")
A1_NEGATIVE = ("她很善良", "她是个善良的人", "她很客气", "客气", "善良")

B5_POSITIVE = (
    "她隔了一天才回我",
    "她隔天才回我消息",
    "她隔两天才回我",
    "她过了一天才回复我",
    "她第二天才回我",
)
B5_NEGATIVE = (
    "她一天回我很多次",
    "她第二天见了我",
    "她隔天去上班",
    "她两天后告诉我答案",
)

C_POSITIVE = ("她就是不喜欢我", "她根本不喜欢我", "她就是不喜欢我吧")
C_NEGATIVE = ("她回复得很敷衍", "她说她不喜欢我")

D_POSITIVE = (
    "我肯定被讨厌了",
    "我大概被讨厌了",
    "我是不是被讨厌了",
    "我可能被讨厌了",
    "我好像被讨厌了",
)

G_POSITIVE = ("我不该想太多", "我不应该想太多", "我也不该想太多", "我是不是不该想太多")
G_NEGATIVE = tuple(
    f"{subject}{word}想太多" for subject in ("她", "他", "对方") for word in ("不该", "不应该")
)
G_REPORTED = (
    "他说我不该想太多",
    "她说我不该想太多",
    "朋友告诉我我不该想太多",
    "他说我不应该想太多",
    "她说我不应该想太多",
)
G_UNTOUCHED = ("我不想和你说话", "我不喜欢她", "我不认为她喜欢我")

BOOK = RuleBook.load()
ANALYZER = NedAnalyzer(book=BOOK)


def _rules(text: str) -> set[str]:
    return {span.rule_id for span in detect(text, BOOK)}


def _verdict(text: str) -> str:
    return ANALYZER.analyze_text(text, mode="normal").verdict.code


def test_a1_an_ordinary_explanation_is_recognised_only_when_offered() -> None:
    for text in A1_POSITIVE:
        assert _rules(text) == {"zh.self_discount"}, text
        assert _verdict(text) == "ned.self_discount_noted", text
    for text in A1_NEGATIVE:
        assert _rules(text) == set(), text


def test_b5_the_approved_latency_wordings_are_the_only_ones() -> None:
    for text in B5_POSITIVE:
        assert "zh.response_latency" in _rules(text), text
        assert _verdict(text) == "nea.latency_insufficient", text
    for text in B5_NEGATIVE:
        assert "zh.response_latency" not in _rules(text), text


def test_c_an_explicit_self_negative_belief_stays_the_readers_conclusion() -> None:
    for text in C_POSITIVE:
        assert "zh.self_negative_belief" in _rules(text), text
        assert _verdict(text) == "nea.negative_conclusion", text
    for text in C_NEGATIVE:
        assert "zh.self_negative_belief" not in _rules(text), text
    assert "zh.cold_reply" in _rules("她回复得很敷衍")


def test_d_a_passive_self_negative_belief_is_a_reader_conclusion() -> None:
    for text in D_POSITIVE:
        assert "zh.self_negative_belief" in _rules(text), text
        assert _verdict(text) == "nea.negative_conclusion", text


def test_g_the_reader_own_negated_discount_is_reader_owned() -> None:
    for text in G_POSITIVE:
        assert _rules(text) == {"zh.self_discount"}, text
        assert _verdict(text) == "ned.self_discount_noted", text


def test_gap2_a_described_subject_keeps_its_own_reading() -> None:
    """我不该想太多 is the reader's; 她不应该想太多 never is (mirror contract)."""

    assert _rules("我不该想太多") == {"zh.self_discount"}
    assert _rules("我不应该想太多") == {"zh.self_discount"}
    for text in G_NEGATIVE:
        assert "zh.self_discount" not in _rules(text), text


def test_g_a_reported_proposition_is_never_a_stance_transfer() -> None:
    for text in G_REPORTED:
        assert "zh.self_discount" not in _rules(text), text


def test_g_unrelated_reader_phrases_keep_their_own_behaviour() -> None:
    for text in G_UNTOUCHED:
        assert "zh.self_discount" not in _rules(text), text
