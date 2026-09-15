"""The epistemic audit of an explanation the reader supplied themselves.

Stage 1 answers exactly one question: **does the input report material for this
explanation, beyond the material the explanation is about?** It never judges the
explanation, it never scores it, and it never relates material to it — stating a
relation would need a judgement this agency does not perform.

The quotes in this data are complete at the source. A rule matches the shape it
recognises, so its span can stop in the middle of a clause (``记得我爱``); the
fragment is therefore extended to the end of the clause it sits in. Nothing is
invented, reordered or paraphrased: every fragment stays a verbatim substring of
what the reader typed.
"""

from __future__ import annotations

from collections.abc import Sequence

from ned.app.core.models import EvidenceSpan, InterpretationAudit

#: The reader's own words, as the rule pack captures them. Only a discount of
#: positive material is audited here: a negative conclusion about the other
#: person can be a statement about the reader's own worth, and a self-worth
#: conclusion is not comedy material. It keeps its existing serious screen.
READER_SIGNAL_TYPES: tuple[str, ...] = ("self_discount",)

#: Which side of the ledger the audited shape is about.
EXPLAINED_POLARITY: dict[str, str] = {"self_discount": "positive"}

MATERIAL_POLARITIES: tuple[str, ...] = ("positive", "negative")

#: Where a quoted fragment stops. This is the display rule the screens have
#: always used, now applied to the audit data as well: one list, so a payload and
#: a screen cannot disagree about where a clause ends.
CLAUSE_SEPARATORS: tuple[str, ...] = ("。", "！", "？", "!", "?", "，", ",", "；", ";", "\n")


def complete_fragment(text: str, start: int, end: int) -> str:
    """One verbatim fragment, extended to the end of the clause it sits in.

    Returns an empty string when the span cannot be located in the input, so the
    caller can fall back to the match itself rather than quoting nothing.
    """

    if start < 0 or end < 0 or start >= end or end > len(text):
        return ""
    stop = len(text)
    for index in range(end, len(text)):
        if text[index] in CLAUSE_SEPARATORS:
            stop = index
            break
    return text[start:stop].strip()


def _fragment(span: EvidenceSpan, text: str) -> str:
    """A material fragment: the clause-complete quote, or the raw match."""

    return complete_fragment(text, span.start, span.end) or span.text


def build(spans: Sequence[EvidenceSpan], text: str = "") -> InterpretationAudit | None:
    """The audit for the reader's own explanation, or ``None`` when there is none.

    Two conditions, both required: the reader actually submitted an explanation,
    and the input reports material at all. NED never invents an explanation to
    audit, and never audits an explanation with nothing to be about.

    ``text`` is the input the spans came from. It is only ever used to slice a
    fragment that is already in the input.
    """

    explanation = next(
        (span for span in spans if span.signal_type.value in READER_SIGNAL_TYPES), None
    )
    if explanation is None:
        return None

    material = [
        span
        for span in spans
        if span.polarity in MATERIAL_POLARITIES
        and span.signal_type.value not in READER_SIGNAL_TYPES
    ]
    if not material:
        return None

    explained = EXPLAINED_POLARITY.get(explanation.signal_type.value, "positive")
    other = [span for span in material if span.polarity != explained]
    return InterpretationAudit(
        reading=complete_fragment(text, explanation.start, explanation.end) or explanation.text,
        reading_rule_id=explanation.rule_id,
        material=[_fragment(span, text) for span in material],
        other_material=[_fragment(span, text) for span in other],
        material_status="additional_material_present" if other else "no_additional_material",
        relation_assessed=False,
    )


__all__ = [
    "CLAUSE_SEPARATORS",
    "EXPLAINED_POLARITY",
    "MATERIAL_POLARITIES",
    "READER_SIGNAL_TYPES",
    "build",
    "complete_fragment",
]
