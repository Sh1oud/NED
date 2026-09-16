"""BATCH 4.6: boundary ownership stays inside the coordinated clause.

A coordination mark starts a new report-local clause. The material in front of the
mark belongs to that other proposition, so it may not glue itself onto the boundary
clause's subject - and the report frame in front of the mark still owns the stance.
"""

from __future__ import annotations

import pathlib

from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.parser import detect
from ned.app.core.rules import RuleBook

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BOUNDARY_SOURCE = REPO_ROOT / "ned" / "app" / "core" / "boundary.py"

RESTORED_BOUNDARIES = (
    "她给我买了早餐但她说不想见我",
    "她记得我生日但她说不想谈恋爱",
    "她说她喜欢我不过她不想谈恋爱",
    "她给我发了消息可是她说只想当普通朋友",
    "她记得我生日不过她说不想发展成恋爱关系",
)

THIRD_PARTY_RELAY = (
    "室友说她很喜欢我但她只想当朋友",
    "朋友说她很喜欢我不过她不想谈恋爱",
)

REPORTED_SPEECH_CONTINUATION = "他说他很喜欢我 但我们还是做朋友吧"
READER_SELF_DISCOUNT = "我本来觉得可能只是人好，但她后来让我别再联系"

BOOK = RuleBook.load()
ANALYZER = NedAnalyzer(book=BOOK)


def _has_boundary(text: str) -> bool:
    return any(span.signal_type.value == "direct_rejection" for span in detect(text, BOOK))


def _verdict(text: str) -> str:
    return ANALYZER.analyze_text(text, mode="normal").verdict.code


def test_a_material_clause_in_front_does_not_steal_the_boundary_clause() -> None:
    """The gift or the remembered birthday is another proposition, not the stance."""

    for text in RESTORED_BOUNDARIES:
        assert _has_boundary(text), text
        assert _verdict(text) == "ned.direct_rejection", text


def test_a_relayed_stance_belongs_to_the_relay_not_to_her() -> None:
    """A third party relaying her stance is not her own statement to the reader."""

    for text in THIRD_PARTY_RELAY:
        assert not _has_boundary(text), text
        assert _verdict(text) != "ned.direct_rejection", text


def test_the_two_settled_rulings_keep_their_answers() -> None:
    """The reported-speech continuation keeps its boundary, the self-discount does not."""

    assert _has_boundary(REPORTED_SPEECH_CONTINUATION)
    assert _verdict(REPORTED_SPEECH_CONTINUATION) == "ned.direct_rejection"
    assert not _has_boundary(READER_SELF_DISCOUNT)
    assert _verdict(READER_SELF_DISCOUNT) != "ned.direct_rejection"


def test_only_the_noun_phrase_reading_is_scoped() -> None:
    """The fix scopes the adjacency chain, not the speaker, frame or volition reading."""

    source = BOUNDARY_SOURCE.read_text(encoding="utf-8")
    start = source.index("def _report_local_spans")
    body = source[start:].split('"""')[2]
    assert "tokens" not in body
    assert "tokens = _walk(prefix)" in source
    hers = source[source.index("def hers(") :]
    assert hers.count("_adjacent_content(local_spans)") == 2
    assert "_adjacent_content(spans)" not in hers
