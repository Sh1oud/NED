"""BATCH 4.8: inline whitespace has no vote in boundary attribution.

None of these variants may change the speaker, the reporter, the proposition owner, the
boundary eligibility, the verdict or the screen:

    none / one ASCII space / two ASCII spaces / Tab / full-width space U+3000

Punctuation (, ; 。 、 :) and newline are not in that equivalence class, and the reader
owned firewall keeps its own clause-break set - the change is boundary-local.
"""

from __future__ import annotations

import pathlib

from ned.app.core import attribution, boundary
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.parser import detect
from ned.app.core.rules import RuleBook

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

VARIANTS = ("", " ", "  ", "\t", "\u3000")

THIRD_PARTY_RELAY = (
    ("她妈妈跟我说", "她不想见我"),
    ("室友告诉我", "她不想见我"),
    ("朋友说", "她只想当普通朋友"),
    ("小王跟我说", "她觉得我们不合适"),
    ("她朋友说", "她不想和我说话"),
)

DESCRIBED_PERSON_SPEECH = (
    ("她说", "她不想见我"),
    ("她跟我说", "她不想谈恋爱"),
    ("她告诉我", "她只想当普通朋友"),
)

REPORTED_SPEECH_CONTINUATION = (
    ("他说他很喜欢我", "但我们还是做朋友吧"),
    ("他说我很好", "但我们不合适"),
)

TOP_LEVEL_COORDINATION = (
    ("她给我买了早餐", "但她说不想见我"),
    ("她记得我生日", "不过她说不想谈恋爱"),
)

POLICY_A = (
    ("我", "不想和你说话"),
    ("我", "觉得我们不合适"),
    ("我", "希望你别联系我"),
)

BOOK = RuleBook.load()
ANALYZER = NedAnalyzer(book=BOOK)


def _has_boundary(text: str) -> bool:
    return any(span.signal_type.value == "direct_rejection" for span in detect(text, BOOK))


def _verdict(text: str) -> str:
    return ANALYZER.analyze_text(text, mode="normal").verdict.code


def _variants(pair: tuple[str, str]) -> list[str]:
    head, tail = pair
    return [f"{head}{separator}{tail}" for separator in VARIANTS]


def test_the_whitespace_contract_is_boundary_local() -> None:
    """The firewall keeps its own clause-break set; only the boundary path is scoped."""

    assert " " in attribution.CLAUSE_BREAKS
    assert "\t" in attribution.CLAUSE_BREAKS
    for char in boundary.INLINE_WHITESPACE:
        assert char not in boundary.BOUNDARY_BREAKS
    assert "\n" in boundary.BOUNDARY_BREAKS
    for mark in "。！？!?，,；;、":
        assert mark in boundary.BOUNDARY_BREAKS


def test_a_relayed_stance_is_never_hers_in_any_whitespace_variant() -> None:
    for pair in THIRD_PARTY_RELAY:
        for text in _variants(pair):
            assert not _has_boundary(text), text
            assert _verdict(text) != "ned.direct_rejection", text


def test_her_own_statements_keep_their_boundary_in_any_whitespace_variant() -> None:
    for pair in DESCRIBED_PERSON_SPEECH:
        for text in _variants(pair):
            assert _has_boundary(text), text
            assert _verdict(text) == "ned.direct_rejection", text


def test_reported_speech_continuation_never_needs_a_separator() -> None:
    for pair in REPORTED_SPEECH_CONTINUATION:
        answers = {(_has_boundary(text), _verdict(text)) for text in _variants(pair)}
        assert answers == {(True, "ned.direct_rejection")}, (pair, answers)


def test_top_level_coordination_is_whitespace_invariant() -> None:
    for pair in TOP_LEVEL_COORDINATION:
        answers = {(_has_boundary(text), _verdict(text)) for text in _variants(pair)}
        assert answers == {(True, "ned.direct_rejection")}, (pair, answers)


def test_a_reader_stance_is_never_handed_to_the_other_person() -> None:
    for pair in POLICY_A:
        for text in _variants(pair):
            assert not _has_boundary(text), text
            assert _verdict(text) != "ned.direct_rejection", text
