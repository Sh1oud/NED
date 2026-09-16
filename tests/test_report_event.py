"""The shared report-event contract: frame resolution plus event actuality.

Structure comes from the bounded frame grammar; actuality is read from the report event's own
surface (report clause start through speech head). The two failures stay distinguishable: an
unasserted report, and an asserted report whose content does not qualify.
"""

from __future__ import annotations

import pytest
from ned.app.core import report_event

ASSERTED_FRAMES = (
    "她说讨厌我",
    "她跟我说她讨厌我",
    "她昨天跟我说她讨厌我",
    "她刚才跟我说她讨厌我",
    "她最近跟我说她讨厌我",
    "她真的跟我说她讨厌我",
    "她明确跟我说她讨厌我",
    "她跟我小声说她讨厌我",
    "她跟我认真说她讨厌我",
    "她跟我突然说她讨厌我",
    "她跟我抱怨她讨厌我",
    "她跟我嘀咕她讨厌我",
    "她对我说她讨厌我",
)

OUTER_UNASSERTED = (
    "她没跟我说她讨厌我",
    "她没有跟我说她讨厌我",
    "她没跟我抱怨她讨厌我",
    "她没有跟我嘀咕她讨厌我",
    "她没说讨厌我",
    "她可能跟我说她讨厌我",
    "她也许跟我说她讨厌我",
    "她可能跟我抱怨她讨厌我",
    "她可能跟我嘀咕她讨厌我",
    "她可能说讨厌我",
    "她是不是跟我说她讨厌我",
    "她是否跟我说她讨厌我",
    "她是不是跟我抱怨她讨厌我",
    "她是不是跟我嘀咕她讨厌我",
)

FUTURE_INTENTION = (
    "她会跟我说她讨厌我",
    "她准备跟我说她讨厌我",
    "她想跟我说她讨厌我",
    "她要跟我说她讨厌我",
)

INNER_MODALITY = (
    "她说她可能讨厌我",
    "她跟我说她可能讨厌我",
    "她跟我抱怨她不讨厌我",
    "她跟我说她是不是讨厌我",
)

BARE_DENIAL_ATTACHED = ("她不跟我说她讨厌我", "她不说她讨厌我")

BARE_DENIAL_NOT_MODALITY = ("她不但跟我说她讨厌我", "她不久前跟我说她讨厌我")

#: Candidate proposition forms, longest first, so the harness can locate the proposition the
#: contract is measured at. This is test-only: the resolver never carries this list.
PROBES = (
    "她可能讨厌我",
    "她是不是讨厌我",
    "她不讨厌我",
    "她不喜欢我",
    "她讨厌我",
    "他很烦我",
    "他讨厌我",
    "我讨厌她",
    "很烦我",
    "不喜欢我",
    "嫌弃我",
    "她说嫌弃我",
    "讨厌我",
)


def _resolve(text: str):
    for probe in PROBES:
        index = text.find(probe)
        if index >= 0:
            return index, report_event.resolve_report_event(text, index)
    raise AssertionError(f"no candidate proposition found in {text!r}")


def _detail(text: str, index: int, resolved) -> str:
    frame = resolved.frame
    return (
        f"{text!r} proposition_start={index} report_start={resolved.report_start} "
        f"head_end={resolved.head_end} sender={frame.speech_sender!r} receiver={frame.receiver!r} "
        f"head={frame.speech_verb!r} actuality={resolved.actuality} "
        f"owner={resolved.proposition_owner!r} inherited={resolved.inherited}"
    )


@pytest.mark.parametrize("text", ASSERTED_FRAMES)
def test_an_asserted_report_resolves_its_frame(text: str) -> None:
    index, resolved = _resolve(text)
    detail = _detail(text, index, resolved)
    assert resolved.frame.speech_sender == "她", detail
    assert resolved.actuality == "ASSERTED", detail
    assert resolved.inherited is False, detail


@pytest.mark.parametrize("text", OUTER_UNASSERTED)
def test_outer_modality_is_never_asserted(text: str) -> None:
    index, resolved = _resolve(text)
    assert resolved.actuality == "NOT_ASSERTED", _detail(text, index, resolved)


@pytest.mark.parametrize("text", FUTURE_INTENTION)
def test_a_future_or_intended_report_is_unresolved(text: str) -> None:
    index, resolved = _resolve(text)
    assert resolved.actuality == "UNRESOLVED", _detail(text, index, resolved)


@pytest.mark.parametrize("text", INNER_MODALITY)
def test_inner_modality_stays_an_asserted_report(text: str) -> None:
    """The proposition inside the report is the content layer's business, not actuality's."""

    index, resolved = _resolve(text)
    assert resolved.actuality == "ASSERTED", _detail(text, index, resolved)


@pytest.mark.parametrize("text", BARE_DENIAL_ATTACHED)
def test_a_structurally_attached_bare_denial_is_not_asserted(text: str) -> None:
    index, resolved = _resolve(text)
    assert resolved.actuality == "NOT_ASSERTED", _detail(text, index, resolved)


@pytest.mark.parametrize("text", BARE_DENIAL_NOT_MODALITY)
def test_a_bare_denial_outside_the_event_is_not_modality(text: str) -> None:
    """没有全局 substring 判断：不在 report event 上的「不」既不判否定，也不吞掉断言。"""

    index, resolved = _resolve(text)
    assert resolved.actuality != "NOT_ASSERTED", _detail(text, index, resolved)


def test_punctuation_continuation_carries_actuality_with_the_frame() -> None:
    index, resolved = _resolve("她跟我说，她讨厌我")
    assert (resolved.inherited, resolved.actuality) == (True, "ASSERTED"), _detail(
        "她跟我说，她讨厌我", index, resolved
    )
    assert resolved.frame.receiver == "我"
    for text in ("她没跟我说，她讨厌我", "她可能跟我说，她讨厌我"):
        index, resolved = _resolve(text)
        assert (resolved.inherited, resolved.actuality) == (True, "NOT_ASSERTED"), _detail(
            text, index, resolved
        )


def test_the_continuation_contract_is_not_widened() -> None:
    for text in ("她跟我说，但是她讨厌我", "她跟我说，后来她讨厌我"):
        index, resolved = _resolve(text)
        assert resolved.inherited is False, _detail(text, index, resolved)


def test_relay_and_reader_frames_never_resolve_as_hers() -> None:
    for text in (
        "朋友跟我说她讨厌我",
        "她妈妈跟我抱怨她讨厌我",
        "我跟她说她讨厌我",
    ):
        index, resolved = _resolve(text)
        assert resolved.frame.speech_sender == "", _detail(text, index, resolved)


def test_the_proposition_owner_is_extracted_without_touching_the_frame() -> None:
    index, conflict = _resolve("她跟我说他讨厌我")
    assert conflict.frame.speech_sender == "她", _detail("她跟我说他讨厌我", index, conflict)
    assert conflict.proposition_owner == "他", _detail("她跟我说他讨厌我", index, conflict)
    index, reader_side = _resolve("她跟我说我讨厌她")
    assert reader_side.proposition_owner == "我", _detail("她跟我说我讨厌她", index, reader_side)
    index, aligned = _resolve("她跟我说她讨厌我")
    assert aligned.proposition_owner == "她", _detail("她跟我说她讨厌我", index, aligned)
    # the owner never makes an unresolved frame resolved
    index, relay = _resolve("朋友跟我说他讨厌我")
    assert relay.frame.speech_sender == "", _detail("朋友跟我说他讨厌我", index, relay)


#: The owner lives in the proposition's head slot. A pronoun further inside the proposition is
#: a predicate object and never the owner; an owner the text does not state stays empty.
HEAD_SLOT_OWNERS = (
    ("她说讨厌我", ""),
    ("她说不喜欢我", ""),
    ("她说很烦我", ""),
    ("她说嫌弃我", ""),
    ("她说真的讨厌我", ""),
    ("她说她讨厌我", "她"),
    ("她跟我说她讨厌我", "她"),
    ("她跟我说他讨厌我", "他"),
    ("她跟我说我讨厌她", "我"),
)


@pytest.mark.parametrize(("text", "owner"), HEAD_SLOT_OWNERS)
def test_the_proposition_owner_comes_from_the_head_slot(text: str, owner: str) -> None:
    index, resolved = _resolve(text)
    assert resolved.proposition_owner == owner, _detail(text, index, resolved)


def test_an_object_pronoun_is_never_the_proposition_owner() -> None:
    """predicate object pronouns must not be read as the proposition owner."""

    for text in ("她说讨厌我", "她说不喜欢我", "她说很烦我", "她说嫌弃我"):
        index, resolved = _resolve(text)
        assert resolved.proposition_owner == "", _detail(text, index, resolved)
        assert resolved.frame.speech_sender == "她", _detail(text, index, resolved)
        assert resolved.actuality == "ASSERTED", _detail(text, index, resolved)
