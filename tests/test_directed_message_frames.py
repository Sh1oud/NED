"""Receiver-bound directed message frames: the grammar and the attribution outcome.

A directed message head ("嘀咕", "抱怨") only classifies an already structured message
event: sender, explicit receiver, then the proposition. Roles decide ownership, so the same
trigger is her report when the receiver is the reader, and stays unread when nobody is named
or the receiver is somebody else.
"""

from __future__ import annotations

import pytest
from ned.app.core import attribution, boundary
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import SignalType
from ned.app.core.rules import RuleBook

ANALYZER = NedAnalyzer(book=RuleBook.load())

DIRECTED_REPORTS = (
    "她跟我嘀咕她讨厌我",
    "她跟我抱怨她讨厌我",
    "她对我嘀咕她不喜欢我",
    "她对我抱怨她很烦我",
)

NO_RECEIVER = ("她嘀咕她讨厌我", "她抱怨她讨厌我")

NON_READER_RECEIVER = (
    "她跟他嘀咕她讨厌我",
    "她跟他抱怨她讨厌我",
    "她跟朋友抱怨她讨厌我",
)

EXCLUDED_HEADS = (
    "她跟我讨论她讨厌我",
    "她跟我分析她讨厌我",
    "她跟我猜她讨厌我",
    "她跟我觉得她讨厌我",
    "她跟我梦见她讨厌我",
)

NOT_AN_EVENT = (
    "她没跟我抱怨她讨厌我",
    "她没有跟我嘀咕她讨厌我",
    "她可能跟我抱怨她讨厌我",
    "她可能跟我嘀咕她讨厌我",
    "她是不是跟我抱怨她讨厌我",
    "她是不是跟我嘀咕她讨厌我",
)

MODIFIER_COMBOS = (
    "她跟我小声抱怨她讨厌我",
    "她跟我认真嘀咕她讨厌我",
    "她跟我突然抱怨她讨厌我",
)

PUNCTUATION_COMBOS = ("她跟我抱怨，她讨厌我", "她跟我嘀咕，她讨厌我")

#: Proposition forms used below, longest first so a shorter form never shadows one.
PROBES = (
    "她不喜欢我",
    "她讨厌我",
    "她很烦我",
    "他不喜欢我",
    "他讨厌我",
    "我讨厌她",
    "不喜欢我",
    "很烦我",
    "讨厌我",
)


def _frame(text: str):
    for probe in PROBES:
        index = text.find(probe)
        if index >= 0:
            return boundary._local_frame(text, index, len(text)), index
    raise AssertionError(text)


@pytest.mark.parametrize("text", DIRECTED_REPORTS)
def test_a_directed_message_names_its_sender_and_reader(text: str) -> None:
    frame, index = _frame(text)
    assert frame.speech_sender == "她", text
    assert frame.receiver == "我", text
    assert frame.local_subject == "她", text
    assert frame.ambiguous is False, text
    assert attribution.reader_owned(text, index) is False, text
    result = ANALYZER.analyze_text(text, mode="normal")
    assert result.evidence == [], text


@pytest.mark.parametrize("text", NO_RECEIVER)
def test_a_receiverless_directed_message_stays_unread(text: str) -> None:
    frame, _index = _frame(text)
    assert frame.receiver != "我", text
    assert not (frame.speech_sender and frame.receiver), text
    assert ANALYZER.analyze_text(text, mode="normal").evidence == [], text


@pytest.mark.parametrize("text", NON_READER_RECEIVER)
def test_a_non_reader_receiver_is_never_rewritten_as_the_reader(text: str) -> None:
    frame, _index = _frame(text)
    assert frame.receiver != "我", text
    assert ANALYZER.analyze_text(text, mode="normal").evidence == [], text


def test_a_relay_never_transfers_the_stance_to_her() -> None:
    for text in ("朋友跟我抱怨她讨厌我", "她妈妈跟我抱怨她讨厌我"):
        frame, _index = _frame(text)
        assert frame.speech_sender != "朋友", text
        assert frame.ambiguous is True, text
        assert ANALYZER.analyze_text(text, mode="normal").materials == [], text


def test_the_readers_own_message_event_is_not_hers() -> None:
    frame, index = _frame("我跟她抱怨她讨厌我")
    assert frame.speech_sender != "她"
    assert attribution.reader_owned("我跟她抱怨她讨厌我", index) is True


def test_ownership_follows_the_proposition_owner() -> None:
    _, index = _frame("她跟我抱怨她讨厌我")
    assert attribution.reader_owned("她跟我抱怨她讨厌我", index) is False
    # owner conflict: her frame, somebody else's proposition
    for text in ("她跟我抱怨他讨厌我", "她跟我嘀咕他不喜欢我"):
        _, conflict = _frame(text)
        assert attribution.reader_owned(text, conflict) is False, text
    # the reader's own proposition is never inverted
    _, reader_side = _frame("她跟我抱怨我讨厌她")
    assert attribution.reader_owned("她跟我抱怨我讨厌她", reader_side) is True


@pytest.mark.parametrize("text", EXCLUDED_HEADS)
def test_evaluation_cognition_and_experience_heads_stay_out(text: str) -> None:
    frame, index = _frame(text)
    assert not (frame.speech_sender and frame.receiver == "我"), text
    assert attribution.reader_owned(text, index) is True, text


@pytest.mark.parametrize("text", NOT_AN_EVENT)
def test_a_negated_or_uncertain_message_is_not_an_occurred_event(text: str) -> None:
    result = ANALYZER.analyze_text(text, mode="normal")
    assert result.evidence == [], text
    assert result.materials == [], text


@pytest.mark.parametrize("text", ("她跟我抱怨我", "她跟我嘀咕我"))
def test_an_object_is_not_a_proposition(text: str) -> None:
    """``抱怨我`` names an object; it may not be turned into a fabricated proposition."""

    result = ANALYZER.analyze_text(text, mode="normal")
    assert result.evidence == [], text
    assert result.materials == [], text
    assert all(
        SignalType.SELF_NEGATIVE_BELIEF is not span.signal_type for span in result.evidence
    ), text


@pytest.mark.parametrize("text", MODIFIER_COMBOS)
def test_the_delivery_modifier_and_the_directed_head_compose(text: str) -> None:
    frame, index = _frame(text)
    assert (frame.speech_sender, frame.receiver, frame.local_subject) == ("她", "我", "她"), text
    assert attribution.reader_owned(text, index) is False, text


@pytest.mark.parametrize("text", PUNCTUATION_COMBOS)
def test_the_clause_continuation_and_the_directed_head_compose(text: str) -> None:
    _, index = _frame(text)
    assert attribution.reader_owned(text, index) is False, text


def test_a_receiverless_directed_message_is_not_a_boundary_stance() -> None:
    """Candidate A's hazard must not survive: no receiver, no her-to-reader frame."""

    for text, stance in (
        ("她抱怨不要联系我", "不要联系我"),
        ("她抱怨我们不合适", "我们不合适"),
        ("她嘀咕不要联系我", "不要联系我"),
    ):
        start = text.index(stance)
        assert boundary.hers(text, start, start + len(stance)) is False, text
