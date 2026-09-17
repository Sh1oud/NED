"""Relationship-intent polarity: is the proposition affirmed, negated or opposed?

One narrow question about one family. When a relationship-intent phrase matched
(``我们在一起`` / ``谈恋爱`` / ``做男女朋友`` / ``跟我在一起``), was the proposition that
contains it *affirmed*, or was it *negated* or *opposed*?

Before PR-1 the engine had no answer at all: a positive phrase that happened to sit
inside a refusal, or inside somebody else's objection, was offered as positive evidence.
PR-0 documented the consequence (``她暂时不想谈恋爱`` and ``她妈妈不同意我们在一起`` both
signed as ``POSITIVE EVIDENCE DETECTED``). Two causes lived in different layers, and this
module is the second one: pattern matching alone cannot tell

    我们在一起            (affirmed -> positive evidence)
    不想和我们在一起      (negated  -> not positive evidence)
    不同意我们在一起      (opposed  -> not positive evidence, and not her boundary either)

This is deliberately **not** a general Chinese negation framework. It reads the clause the
span sits in for the two things that actually decide these cases:

  * a volition / cognition predicate under negation in front of the span
    (``不想`` / ``不愿意`` / ``没想过`` / ``不可能`` ...);
  * a *negative* approval predicate, or a lexical opposition predicate, anywhere in the
    clause (``不同意`` / ``不赞成`` / ``不支持`` / ``反对`` ...).

It reports what it found and whose objection it is, so a caller can tell "she refused" from
"her mother objects". It never creates a boundary: dropping a positive span is all it
authorises.
"""

from __future__ import annotations

from dataclasses import dataclass

from ned.app.core import attribution

#: Signal types whose positive spans this layer guards. The relationship-intent family
#: only: gift, care, latency, compliments and the rest are out of scope.
RELATIONSHIP_INTENT_SIGNAL_TYPES = frozenset({"commitment_offer"})

#: Negation words that can negate a following predicate.
NEGATIONS = (
    "不可能",
    "不愿意",
    "不想",
    "不要",
    "不会",
    "不能",
    "不再",
    "没法",
    "无法",
    "没有",
    "没",
    "别",
    "不",
)

#: Predicates a negation can govern to make the proposition non-positive.
VOLITION_PREDICATES = (
    "愿意",
    "希望",
    "打算",
    "考虑",
    "准备",
    "接受",
    "可能",
    "想",
    "要",
    "肯",
)

#: Approval predicates: affirming them is support, negating them is opposition.
APPROVAL_PREDICATES = ("同意", "赞成", "支持", "允许", "答应", "认可", "看好")

#: Lexical opposition predicates.
OPPOSITION_PREDICATES = (
    "不同意",
    "不赞成",
    "不支持",
    "不允许",
    "不答应",
    "不肯",
    "不让",
    "不许",
    "反对",
    "阻止",
    "阻拦",
    "抗拒",
)

#: Interrogative forms that merely contain 不/没: 要不要在一起 is a question, not a refusal.
INTERROGATIVE_FORMS = ("要不要", "是不是", "有没有", "好不好", "行不行", "能不能", "要不要")

#: Third-party subjects: an objection from one of these is not her own boundary.
THIRD_PARTY_WORDS = (
    "妈妈",
    "妈",
    "爸爸",
    "爸",
    "父母",
    "家里",
    "家人",
    "家长",
    "朋友",
    "闺蜜",
    "姐姐",
    "妹妹",
    "哥哥",
    "弟弟",
    "亲戚",
    "同事",
    "同学",
)


@dataclass(frozen=True)
class IntentPolarity:
    """What the clause says about the relationship-intent proposition."""

    positive: bool
    reason: str  # "affirmed" | "negated" | "opposed"
    marker: str = ""
    opposition_subject: str = ""  # "target" | "third_party" | "reader" | "unknown"


AFFIRMED = IntentPolarity(positive=True, reason="affirmed")


def _clause_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """The clause the span sits in, using the engine's own clause breaks."""

    left = start
    while left > 0 and text[left - 1] not in attribution.CLAUSE_BREAKS:
        left -= 1
    right = end
    while right < len(text) and text[right] not in attribution.CLAUSE_BREAKS:
        right += 1
    return left, right


def _negation_before(text: str, window_start: int, span_start: int) -> str:
    """The negation that governs a volition predicate in front of the span, if any."""

    prefix = text[window_start:span_start]
    for negation in NEGATIONS:
        at = prefix.find(negation)
        while at >= 0:
            absolute = window_start + at
            preceded_by = text[absolute - 1] if absolute > 0 else ""
            if preceded_by + negation in INTERROGATIVE_FORMS:
                at = prefix.find(negation, at + 1)
                continue
            after = prefix[at + len(negation) :]
            if any(predicate in after[:4] for predicate in VOLITION_PREDICATES):
                return negation
            # a negation glued to the span itself ("不" + relationship phrase)
            if not after.strip():
                return negation
            at = prefix.find(negation, at + 1)
    return ""


def _opposition(text: str, window_start: int, window_end: int) -> tuple[str, int]:
    """The opposition predicate in the clause, if any, with its offset."""

    clause = text[window_start:window_end]
    for predicate in OPPOSITION_PREDICATES:
        at = clause.find(predicate)
        if at >= 0:
            return predicate, window_start + at
    for approval in APPROVAL_PREDICATES:
        at = clause.find(approval)
        while at >= 0:
            before = clause[max(0, at - 3) : at]
            for negation in ("不", "没", "没有", "别"):
                if negation in before:
                    return negation + approval, window_start + at
            at = clause.find(approval, at + 1)
    return "", -1


def _subject_of(text: str, window_start: int, predicate_at: int) -> str:
    """Whose objection this is: hers, a third party's, or the reader's."""

    prefix = text[window_start:predicate_at]
    if any(word in prefix for word in THIRD_PARTY_WORDS):
        return "third_party"
    if any(pronoun in prefix for pronoun in attribution.READER_PRONOUNS):
        return "reader"
    if any(pronoun in prefix for pronoun in attribution.DESCRIBED_PRONOUNS):
        return "target"
    return "unknown"


def relationship_intent_polarity(text: str, start: int, end: int) -> IntentPolarity:
    """Whether the relationship-intent proposition at ``[start:end]`` may be positive.

    Returns ``AFFIRMED`` when nothing in the clause negates or opposes it. A caller may
    only *drop* a positive span on a non-positive verdict; it must not turn one into a
    boundary, because "her mother objects" is not "she refused".
    """

    window_start, window_end = _clause_bounds(text, start, end)

    predicate, predicate_at = _opposition(text, window_start, window_end)
    if predicate:
        return IntentPolarity(
            positive=False,
            reason="opposed",
            marker=predicate,
            opposition_subject=_subject_of(text, window_start, predicate_at),
        )

    negation = _negation_before(text, window_start, start)
    if negation:
        return IntentPolarity(
            positive=False,
            reason="negated",
            marker=negation,
            opposition_subject=_subject_of(text, window_start, start),
        )

    return AFFIRMED


__all__ = [
    "AFFIRMED",
    "RELATIONSHIP_INTENT_SIGNAL_TYPES",
    "IntentPolarity",
    "relationship_intent_polarity",
]
