"""READER-WS-CLOSURE: reader ownership is invariant to CJK inline whitespace.

`attribution.reader_owned` decides "whose words are these" for `zh.self_discount` and
`zh.self_negative_belief`. Inside a CJK sentence an inline formatting separator (one
space, several spaces, Tab, U+3000) may not change that answer - while English keeps its
space structure, and newline and punctuation keep ending a clause.
"""

from __future__ import annotations

import pathlib

from ned.app.core import attribution
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.parser import compile_pattern, detect
from ned.app.core.rules import RuleBook

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

VARIANTS = ("", " ", "  ", "\t", "\u3000")

SELF_DISCOUNT = (
    ("我", "想太多了"),
    ("我", "可能想多了"),
    ("我", "是不是想太多了"),
)

#: READER-GAP-1 closed in BATCH 5.1: 不该/不应该 is part of the reader's own closed-class
#: reading, so the reader's negated discount is reader-owned. The reader-owned firewall is
#: still space-sensitive (a separate plane from the boundary whitespace contract), so this
#: test pins the wording itself rather than a whitespace equivalence claim.
READER_SELF_DISCOUNT_NEGATION = (
    "我不该想太多",
    "我不应该想太多",
    "我也不该想太多",
    "我是不是不该想太多",
)

SELF_NEGATIVE_BELIEF = (
    ("我", "觉得她不喜欢我"),
    ("我", "总觉得她不喜欢我"),
    ("我", "没有觉得她不喜欢我"),
)

THIRD_PARTY_RELAY = (
    ("她说", "我想太多了"),
    ("她说", "我是不是想太多了"),
    ("她告诉我别想太多", ""),
    ("老师说她不喜欢我", ""),
    ("室友说她讨厌我", ""),
    ("小王告诉我她嫌我烦", ""),
    ("她朋友说她不喜欢我", ""),
)

COMPOUND_RECEIVER = (
    ("我跟她妈妈说", "我想太多了"),
    ("我跟她朋友说", "我想多了"),
    ("我对室友说", "我觉得她不喜欢我"),
    ("我向老师说", "我觉得她讨厌我"),
)

ENGLISH_PROTECTION = "She said she likes me, but I think she is just being polite."

BOOK = RuleBook.load()
ANALYZER = NedAnalyzer(book=BOOK)
READER_RULES = tuple(
    rule for rule in BOOK.signals if rule.signal_type.value in attribution.READER_OWNED_TYPES
)


def _variants(pair: tuple[str, str]) -> list[str]:
    head, tail = pair
    return [f"{head}{separator}{tail}" for separator in VARIANTS]


def _owned_evidence(text: str) -> list[tuple[str, bool]]:
    """Every reader-owned-family match with the firewall's own answer."""

    found = []
    for rule in READER_RULES:
        for pattern in rule.patterns:
            for match in compile_pattern(pattern).finditer(text):
                if not match.group(0).strip():
                    continue
                found.append((rule.id, attribution.reader_owned(text, match.start())))
    return sorted(found)


def _surviving_reader_signals(text: str) -> list[str]:
    return sorted(
        span.rule_id
        for span in detect(text, BOOK)
        if span.rule_id in {rule.id for rule in READER_RULES}
    )


def test_self_discount_keeps_the_reader_as_author() -> None:
    for pair in SELF_DISCOUNT:
        answers = {
            (tuple(_owned_evidence(text)), tuple(_surviving_reader_signals(text)))
            for text in _variants(pair)
        }
        assert len(answers) == 1, pair
        evidence, signals = answers.pop()
        assert evidence and all(owned for _rule, owned in evidence), pair
        assert signals == ("zh.self_discount",), pair


def test_the_readers_own_negated_discount_is_reader_owned() -> None:
    """我不该想太多 and its approved neighbours are the reader's own conclusion."""

    for text in READER_SELF_DISCOUNT_NEGATION:
        evidence = _owned_evidence(text)
        assert evidence, text
        assert all(owned for _rule, owned in evidence), text
        assert _surviving_reader_signals(text) == ["zh.self_discount"], text


def test_self_negative_belief_keeps_the_reader_as_author() -> None:
    for pair in SELF_NEGATIVE_BELIEF:
        answers = {
            (tuple(_owned_evidence(text)), tuple(_surviving_reader_signals(text)))
            for text in _variants(pair)
        }
        assert len(answers) == 1, pair
        evidence, _signals = answers.pop()
        assert evidence and all(owned for _rule, owned in evidence), pair


def test_a_third_party_relay_is_never_the_readers_own_words() -> None:
    for pair in THIRD_PARTY_RELAY:
        for text in _variants(pair):
            assert not any(owned for _rule, owned in _owned_evidence(text)), text
            assert _surviving_reader_signals(text) == [], text


def test_a_compound_receiver_does_not_usurp_the_reader() -> None:
    for pair in COMPOUND_RECEIVER:
        for text in _variants(pair):
            evidence = _owned_evidence(text)
            assert evidence and all(owned for _rule, owned in evidence), text


def test_english_space_structure_is_untouched() -> None:
    """The known English case stays reader-owned: spaces still build English words."""

    evidence = _owned_evidence(ENGLISH_PROTECTION)
    assert evidence and all(owned for _rule, owned in evidence), evidence
    assert _surviving_reader_signals(ENGLISH_PROTECTION) == ["en.self_discount"]


def test_newline_and_punctuation_still_end_a_clause() -> None:
    for separator in ("\n", "。", "，", "；", "、", "："):
        assert separator not in attribution.INLINE_WHITESPACE
    assert "\n" in attribution.CLAUSE_BREAKS
    for mark in "。！？!?，,；;、":
        assert mark in attribution.CLAUSE_BREAKS
