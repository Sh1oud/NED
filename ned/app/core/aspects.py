"""Stage 2: the material pages an input reports, kept side by side.

Stage 1 audited one explanation the reader supplied. Stage 2 asks a different
question about the input itself: **does it report more than one material that can
stand as a page of its own?** It keeps every page it finds and never relates
them: no support, no refutation, no average, no ranking, no overall verdict.

This module is a selector, not a second evidence model. It reads existing span
fields, returns pointers into ``AnalysisResult.evidence``, and copies no engine
number: polarity, strength, information content and the displayed grade all stay
in the evidence, where they already live.
"""

from __future__ import annotations

from collections.abc import Sequence

from ned.app.core.audit import CLAUSE_SEPARATORS, complete_fragment
from ned.app.core.models import EvidenceSpan, MaterialAspect, MaterialAspects

#: A positive page must reach the 有限 band on its own ruler — the same strength
#: ladder its own screen already grades it with — before NED files it as a page.
#: Below that it is a trace, and the ordinary screens already say so. The number
#: is that band edge, not a new one: ``quality_label(25.0) == "有限"`` and
#: ``quality_label(24.9) == "较弱"`` are pinned by test.
POSITIVE_PAGE_MIN_STRENGTH = 25.0

#: Negative pages that are plain observations the input reports. No floor applies
#: to them: a latency page is a page because the input reports the event, and its
#: own screen already exists. Its low grade is shown, not used as an admission
#: ticket.
OBSERVED_NEGATIVE_TYPES: tuple[str, ...] = ("response_latency", "cold_reply", "plan_cancelled")

#: A stated boundary is a page too. It is kept and never compared with anything.
BOUNDARY_TYPES: tuple[str, ...] = ("direct_rejection",)

#: A hostile expression gets no combined view at all: no "other side" framing.
EXCLUDED_TYPES: tuple[str, ...] = ("hostile_expression",)

#: Material the reader supplied themselves is not material the input reports.
READER_TYPES: tuple[str, ...] = ("self_negative_belief", "self_discount")

#: The two shapes Stage 2 files: a positive page beside an observation, or a
#: positive page beside a stated boundary.
OTHER_PAGE_TYPES: tuple[str, ...] = (*OBSERVED_NEGATIVE_TYPES, *BOUNDARY_TYPES)


def positive_pages(spans: Sequence[EvidenceSpan]) -> list[EvidenceSpan]:
    """The positive material pages of this input, on the positive ruler."""

    return [
        span
        for span in spans
        if span.polarity == "positive" and span.base_strength >= POSITIVE_PAGE_MIN_STRENGTH
    ]


#: Connectors a quoted fragment may start with. They belong to the sentence, not
#: to the material, so the filing card drops them. The fragment stays a verbatim
#: substring of what the reader typed; nothing is reworded or reordered.
LEADING_CONNECTORS: tuple[str, ...] = (
    "但是",
    "但",
    "不过",
    "可是",
    "然而",
    "而且",
    "并且",
    "然后",
    "所以",
    "因为",
    "如果",
    "虽然",
    "尽管",
    "只是",
    "but",
    "and",
    "so",
    "because",
    "although",
    "though",
    "however",
    "yet",
    "then",
)


def _clause_start(text: str, position: int) -> int:
    """Where the clause holding ``position`` begins."""

    for index in range(position - 1, -1, -1):
        if text[index] in CLAUSE_SEPARATORS:
            return index + 1
    return 0


def _strip_leading_connector(fragment: str) -> str:
    """Drop a leading connector, in either language, from a quoted fragment.

    A Latin connector is only dropped on a word boundary, so a word that merely
    starts with the same letters is left alone.
    """

    lowered = fragment.lower()
    for connector in LEADING_CONNECTORS:
        if not lowered.startswith(connector) or len(fragment) <= len(connector):
            continue
        rest = fragment[len(connector) :]
        if connector.isascii() and rest[:1].isalnum():
            continue
        return rest.lstrip()
    return fragment


def page_fragment(text: str, span: EvidenceSpan) -> str:
    """The verbatim fragment a page shows, with its own qualifiers intact.

    A positive page keeps the tail-completed fragment, exactly as Stage 1's
    material column does: the statement's subject is not restored.

    An observation or a boundary page takes its whole clause instead, because
    dropping what stands in front of the event would change what the input
    reported: "今天没回" is not the same material as "没回". A leading connector
    is dropped; the shape of the fragment is otherwise the reader's own words.
    """

    if span.polarity == "positive":
        return complete_fragment(text, span.start, span.end) or span.text
    clause = complete_fragment(text, _clause_start(text, span.start), span.end)
    return _strip_leading_connector(clause or span.text)


def _overlaps(first: EvidenceSpan, second: EvidenceSpan) -> bool:
    """Whether two spans cover some of the same text.

    When the two positions are unknown the answer is no: an unknown position may
    not be used to drop a page.
    """

    if first.start < 0 or second.start < 0:
        return False
    return first.start < second.end and second.start < first.end


Page = tuple[int, EvidenceSpan, str]


def _same_act(first: Page, second: Page) -> bool:
    """Whether two candidate pages describe the same act of text.

    Two positive rules can match nested stretches of one sentence (an initiation
    inside a sustained interaction), and the fragments complete to the same
    clause. The same words are one page, however many rules noticed them.
    """

    if _overlaps(first[1], second[1]):
        return True
    return first[2] in second[2] or second[2] in first[2]


def _one_page_per_act(pages: list[Page]) -> list[Page]:
    """File one page per act of text, keeping the fragment that covers more.

    Observation and boundary pages are never dropped this way.
    """

    chosen: list[Page] = []
    for page in pages:
        if page[1].polarity == "positive":
            clash = next(
                (
                    kept
                    for kept in chosen
                    if kept[1].polarity == "positive" and _same_act(kept, page)
                ),
                None,
            )
            if clash is not None:
                if len(page[2]) > len(clash[2]):
                    chosen[chosen.index(clash)] = page
                continue
        chosen.append(page)
    return chosen


def build(spans: Sequence[EvidenceSpan], text: str = "") -> MaterialAspects | None:
    """The pages this input reports, or ``None`` when it reports fewer than two.

    ``text`` is only ever used to slice a fragment that is already in the input.
    """

    if any(span.signal_type.value in EXCLUDED_TYPES for span in spans):
        return None

    candidates: list[Page] = [
        (index, span, page_fragment(text, span))
        for index, span in enumerate(spans)
        if span.signal_type.value not in READER_TYPES
        and (
            (span.polarity == "positive" and span.base_strength >= POSITIVE_PAGE_MIN_STRENGTH)
            or (span.polarity == "negative" and span.signal_type.value in OTHER_PAGE_TYPES)
        )
    ]
    pages = _one_page_per_act(candidates)
    if not any(span.polarity == "positive" for _index, span, _fragment in pages):
        return None
    if not any(span.polarity == "negative" for _index, span, _fragment in pages):
        return None

    ordered = sorted(pages, key=lambda page: page[1].start)
    return MaterialAspects(
        materials=[
            MaterialAspect(evidence_index=index, text=fragment)
            for index, _span, fragment in ordered
        ],
        relation_assessed=False,
    )


__all__ = [
    "BOUNDARY_TYPES",
    "EXCLUDED_TYPES",
    "LEADING_CONNECTORS",
    "OBSERVED_NEGATIVE_TYPES",
    "OTHER_PAGE_TYPES",
    "POSITIVE_PAGE_MIN_STRENGTH",
    "READER_TYPES",
    "build",
    "page_fragment",
    "positive_pages",
]
