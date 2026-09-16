"""Report events: which frame governs a proposition, and whether the input asserts it.

Structure lives in ``boundary`` - one bounded speech-frame grammar. This facade answers the
two questions its consumers share: *which report frame governs the proposition* (including
the single clause-punctuation continuation) and *whether the input asserts that the report
event happened at all*. It does not classify material, qualify evidence or say anything about
a relationship.

Actuality is read from the report event's own surface - the report clause's start through the
end of its speech head - and never from the proposition inside it. So
"\u5979\u8ddf\u6211\u8bf4\u5979\u53ef\u80fd\u8ba8\u538c\u6211"
is an asserted report of an uncertain attitude, while
"\u5979\u53ef\u80fd\u8ddf\u6211\u8bf4\u5979\u8ba8\u538c\u6211" is not an asserted
report at all: the same marker, two different layers, two different reasons.
"""

from __future__ import annotations

from typing import Literal, NamedTuple

from ned.app.core import attribution, boundary

#: What the input says about the report event itself.
Actuality = Literal["ASSERTED", "NOT_ASSERTED", "UNRESOLVED"]

#: Outer modality, kept in one place. It is deliberately not ``attribution.MARKERS``: that
#: list mixes negation, hedges, time words and plain fillers, so it would call a legal
#: asserted frame ("\u5979\u6628\u5929\u8ddf\u6211\u8bf4") uncertain.
NEGATION = ("\u6ca1\u6709", "\u6ca1", "\u672a")
UNCERTAINTY = ("\u53ef\u80fd", "\u4e5f\u8bb8", "\u6216\u8bb8", "\u5927\u6982", "\u597d\u50cf")
QUESTION = ("\u662f\u4e0d\u662f", "\u662f\u5426", "\u4f1a\u4e0d\u4f1a")
NON_ASSERTION = NEGATION + UNCERTAINTY + QUESTION

#: Future and intention: the report event has not happened. The product contract does not
#: decide these, so they are unresolved rather than asserted or denied.
FUTURE_INTENTION = ("\u51c6\u5907", "\u60f3", "\u8981", "\u4f1a")

#: A bare 不 is a denial only where it is structurally attached to the report event: directly
#: in front of the receiver frame or of the speech head. Anywhere else
#: ("\u5979\u4e0d\u4e45\u524d\u8ddf\u6211\u8bf4",
#: "\u5979\u4e0d\u4f46\u8ddf\u6211\u8bf4") it is not read as modality at all.
BARE_DENIAL = "\u4e0d"

#: The heads the bounded grammar knows. Used only to find where the report event's own
#: surface ends - never to build a frame the grammar did not resolve.
HEADS = (
    boundary.SIMPLE_SPEECH_VERBS + boundary.OBJECT_RECEIVER_VERBS + boundary.DIRECTED_MESSAGE_HEADS
)


class ResolvedReportEvent(NamedTuple):
    """The report frame that governs a proposition, plus the event's actuality."""

    frame: boundary.LocalFrame
    inherited: bool
    actuality: Actuality
    report_start: int
    head_end: int
    proposition_start: int
    proposition_owner: str


def _head_end(text: str, clause_start: int, proposition_start: int) -> int:
    """Where the report event's own surface ends: the last speech head in the clause."""

    end = proposition_start
    best = -1
    for index in range(clause_start, proposition_start):
        token = boundary._starts_with(text, index, HEADS)
        if token is not None and index + len(token) > best:
            best = index + len(token)
    return best if best > 0 else end


def _assertion(text: str, report_start: int, head_end: int) -> Actuality:
    """Whether the report event on ``[report_start, head_end)`` is asserted."""

    surface = text[report_start:head_end]
    if any(marker in surface for marker in NON_ASSERTION):
        return "NOT_ASSERTED"
    for index, char in enumerate(surface):
        if char != BARE_DENIAL:
            continue
        attached = boundary._starts_with(
            surface, index + 1, attribution.PREPOSITIONS + boundary.RECEIVER_VERBS
        ) or boundary._starts_with(surface, index + 1, HEADS)
        if attached is not None:
            return "NOT_ASSERTED"
    if any(marker in surface for marker in FUTURE_INTENTION):
        return "UNRESOLVED"
    return "ASSERTED"


def _proposition_owner(text: str, start: int, end: int) -> str:
    """The proposed actor of the proposition, read from the proposition slice.

    This only ever fills in the proposition owner, and only after the report structure is
    already established: it may not create a frame, resolve one, or change actuality.
    """

    for index in range(start, end):
        token = boundary._starts_with(
            text, index, attribution.DESCRIBED_PRONOUNS + attribution.READER_PRONOUNS
        )
        if token is not None:
            return token
    return ""


def resolve_report_event(
    text: str, proposition_start: int, proposition_end: int | None = None
) -> ResolvedReportEvent:
    """The report frame governing the proposition at ``proposition_start``.

    The frame may be complete in the clause in front
    ("\u5979\u8ddf\u6211\u8bf4\uff0c\u5979\u8ba8\u538c\u6211"): one clause
    punctuation may be crossed when nothing stands between it and the proposition and that
    clause is her own frame addressed to the reader. The inherited event keeps its own
    actuality, so "\u5979\u6ca1\u8ddf\u6211\u8bf4\uff0c\u5979\u8ba8\u538c\u6211" is not an asserted
    report.
    """

    prefix = boundary._clause_prefix(text, proposition_start)
    clause_start = proposition_start - len(prefix)
    frame = boundary._local_frame(text, proposition_start, len(text))
    end = proposition_end if proposition_end is not None else len(text)
    if frame.speech_sender:
        head_end = min(proposition_start, frame.proposition_start)
        return ResolvedReportEvent(
            frame=frame,
            inherited=False,
            actuality=_assertion(text, clause_start, head_end),
            report_start=clause_start,
            head_end=head_end,
            proposition_start=proposition_start,
            proposition_owner=frame.local_subject or _proposition_owner(text, head_end, end),
        )
    owner = frame.local_subject or _proposition_owner(text, proposition_start, end)
    if prefix.strip():
        head_end = _head_end(text, clause_start, proposition_start)
        return ResolvedReportEvent(
            frame=frame,
            inherited=False,
            actuality=_assertion(text, clause_start, head_end),
            report_start=clause_start,
            head_end=head_end,
            proposition_start=proposition_start,
            proposition_owner=owner,
        )
    previous = boundary._previous_clause(text, proposition_start)
    if not previous.strip():
        return ResolvedReportEvent(
            frame, False, "UNRESOLVED", clause_start, clause_start, proposition_start, owner
        )
    inherited = boundary._local_frame(previous, 0, len(previous))
    if not (
        inherited.speech_sender in attribution.DESCRIBED_PRONOUNS
        and inherited.receiver in attribution.READER_PRONOUNS
    ):
        return ResolvedReportEvent(
            frame, False, "UNRESOLVED", clause_start, clause_start, proposition_start, owner
        )
    inherited_start = max(inherited.tail_start, 0)
    previous_start = max(inherited.proposition_start, inherited_start)
    return ResolvedReportEvent(
        frame=inherited,
        inherited=True,
        actuality=_assertion(previous, inherited_start, previous_start),
        report_start=clause_start,
        head_end=clause_start,
        proposition_start=proposition_start,
        proposition_owner=owner,
    )


__all__ = [
    "NEGATION",
    "NON_ASSERTION",
    "QUESTION",
    "UNCERTAINTY",
    "Actuality",
    "ResolvedReportEvent",
    "resolve_report_event",
]
