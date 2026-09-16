"""BATCH 5 hard-line closure: boundary ownership stays inside bounded speech frames.

A private belief is not an explicit boundary; an outer speech sender may not take over a
proposition that names somebody else as the actor; and every explicit frame keeps its
boundary, including a receiver frame, a nested communicated belief and a subjectless
stance.
"""

from __future__ import annotations

import pathlib

from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.parser import detect
from ned.app.core.rules import RuleBook

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

PRIVATE_BELIEF = ("她觉得我们不合适", "她认为我们不合适", "她感觉我们不合适")
COMMUNICATED_BELIEF = (
    "她说她觉得我们不合适",
    "她告诉我她觉得我们不合适",
    "她跟我说她认为我们不合适",
)
OWNER_ALIGNED = ("她说她拒绝了我", "她跟我说她拒绝了我", "她告诉我她拒绝了我")
OWNER_CONFLICT = (
    "她说他拒绝了我",
    "她跟我说他拒绝了我",
    "她告诉我他拒绝了我",
    "他说她拒绝了我",
    "对方说她拒绝了我",
)
NESTED_MENTAL_ALIGNED = ("她说她觉得我们不合适",)
NESTED_MENTAL_CONFLICT = ("她说他觉得我们不合适",)
SUBJECTLESS = ("她说拒绝了我",)
UNCERTAINTY = ("她可能觉得我们不合适", "她是不是觉得我们不合适", "她好像觉得我们不合适")
POLICY_A = ("我想你了", "我不想和你说话", "请不要再联系我", "我觉得我们不合适")
RELAY = ("她妈妈说她觉得我们不合适", "室友告诉我她觉得我们不合适")

BOOK = RuleBook.load()
ANALYZER = NedAnalyzer(book=BOOK)


def _boundary(text: str) -> bool:
    return any(span.signal_type.value == "direct_rejection" for span in detect(text, BOOK))


def _verdict(text: str) -> str:
    return ANALYZER.analyze_text(text, mode="normal").verdict.code


def test_a_private_belief_is_not_an_explicit_boundary() -> None:
    for text in PRIVATE_BELIEF:
        assert not _boundary(text), text
        assert _verdict(text) != "ned.direct_rejection", text


def test_a_communicated_belief_keeps_its_boundary() -> None:
    for text in COMMUNICATED_BELIEF:
        assert _boundary(text), text
        assert _verdict(text) == "ned.direct_rejection", text


def test_an_aligned_owner_keeps_the_boundary() -> None:
    for text in OWNER_ALIGNED:
        assert _boundary(text), text
        assert _verdict(text) == "ned.direct_rejection", text


def test_an_outer_sender_never_takes_over_a_different_owner() -> None:
    for text in OWNER_CONFLICT:
        assert not _boundary(text), text
        assert _verdict(text) != "ned.direct_rejection", text


def test_a_nested_belief_follows_its_own_owner() -> None:
    for text in NESTED_MENTAL_ALIGNED:
        assert _boundary(text), text
    for text in NESTED_MENTAL_CONFLICT:
        assert not _boundary(text), text


def test_a_subjectless_stance_is_not_a_conflict() -> None:
    """No owner named is not the same as a conflicting owner: the guard must not fire."""

    from ned.app.core import boundary

    frame = boundary._local_frame("她说拒绝了我", 0, len("她说拒绝了我"))
    assert frame.speech_sender == "她"
    assert frame.local_subject == ""
    # no owner named is not a conflict, so the stance keeps whatever it had at HEAD
    assert _boundary(SUBJECTLESS[0])
    assert _verdict(SUBJECTLESS[0]) == "ned.direct_rejection"


def test_uncertainty_does_not_reopen_a_private_belief() -> None:
    for text in UNCERTAINTY:
        assert not _boundary(text), text
        assert _verdict(text) != "ned.direct_rejection", text


def test_policy_a_never_hands_the_reader_stance_to_her() -> None:
    for text in POLICY_A:
        assert not _boundary(text), text
        assert _verdict(text) != "ned.direct_rejection", text


def test_a_third_party_relay_keeps_precision_first() -> None:
    for text in RELAY:
        assert not _boundary(text), text
        assert _verdict(text) != "ned.direct_rejection", text


#: The contrast the closure is about: the word 觉得 is not banned, privacy is.
DIRECT_BOUNDARY = ("她说我们不合适", "她告诉我我们不合适", "她明确拒绝了我")


def test_private_belief_versus_communicated_versus_direct() -> None:
    """PRIVATE -> no explicit boundary; COMMUNICATED / DIRECT -> boundary kept."""

    for text in PRIVATE_BELIEF:
        assert not _boundary(text), text
    for text in COMMUNICATED_BELIEF:
        assert _boundary(text), text
    for text in DIRECT_BOUNDARY:
        assert _boundary(text), text
        assert _verdict(text) == "ned.direct_rejection", text
