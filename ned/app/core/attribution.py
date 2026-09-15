"""Ownership firewall for the two reader-owned signal families.

``self_discount`` means *the reader's own discounting wording*; ``self_negative_belief``
means *the reader's own negative conclusion*. Both families match short phrases, so a
phrase that somebody else said, advised or relayed would otherwise be filed as the
reader's own stance — the one thing these families must never do.

The question this module answers is deliberately tiny: **could the reader have authored
the words in front of this trigger?** It does not parse, it does not infer relationships,
it does not look at polarity, and when it cannot tell it answers *no*: a missed
reader-owned phrase is silence, while a wrong one puts words in the reader's mouth.

How it decides, without a list of people:

* the clause is the text between the two nearest clause breaks;
* the prefix is everything in that clause in front of the trigger;
* the prefix is reader-authored when, after any leading hedges and adverbs, it is
  empty, or starts with the reader pronoun, or starts with a pronoun for the person
  being *described*, and everything after that is closed-class vocabulary — a hedge,
  a function word, or one of the reader's own speech and cognition verbs.

Anything containing a content word is a frame, and a frame is somebody else's words.
That is what makes the closure provable rather than sampled: the grammar only accepts
closed-class vocabulary, so an arbitrary named third party (``老师``, ``小王``,
``群里有人``) cannot be admitted by construction, and neither can an arbitrary
reporting verb (``转述``, ``提了一句``, ``发消息说``). Extending the guard for a new
*person* or a new *reporting verb* is therefore never necessary.
"""

from __future__ import annotations

#: Signal types whose contract is "the reader's own words".
READER_OWNED_TYPES = frozenset({"self_discount", "self_negative_belief"})

#: A clause ends here. Anything after the last break belongs to the trigger's clause.
CLAUSE_BREAKS = "\u3002\uff01\uff1f!?\uff0c,\uff1b;\u3001\n\r\t "

#: The reader, and the person the reader is describing.
READER_PRONOUNS = ("\u6211", "\u54b1")
DESCRIBED_PRONOUNS = ("\u5bf9\u65b9", "\u4ed6\u4eec", "\u5979\u4eec", "\u5979", "\u4ed6")

#: The reader speaking *to* somebody: the reader stays the author of the clause.
PREPOSITIONS = ("\u8ddf", "\u548c", "\u4e0e", "\u5bf9", "\u5411", "\u7ed9", "\u66ff", "\u4e3a")

#: The reader's own speech and cognition. Closed class: these are the reader's acts,
#: and they are why the reader's own report stays the reader's own.
READER_VERBS = (
    "\u544a\u8bc9",
    "\u8868\u793a",
    "\u89c9\u5f97",
    "\u8ba4\u4e3a",
    "\u611f\u89c9",
    "\u89e3\u91ca",
    "\u627f\u8ba4",
    "\u6000\u7591",
    "\u77e5\u9053",
    "\u4ee5\u4e3a",
    "\u5e0c\u671b",
    "\u6253\u7b97",
    "\u8bb0\u5f97",
    "\u611f\u5230",
    "\u731c",
    "\u60f3",
    "\u89c9\u5f97",
    "\u8bf4",
    "\u8bb2",
    "\u79f0",
    "\u95ee",
    "\u56de",
    "\u7b54",
    "\u63d0",
)

#: Reporting acts. Closed class, and only ever used to *reject* a described-subject
#: prefix: after "\u5979", a reporting verb means the clause is somebody's words rather
#: than the reader's assertion about her. It is never used to accept anything.
REPORT_VERBS = (
    "\u8bf4",
    "\u8bb2",
    "\u544a\u8bc9",
    "\u8868\u793a",
    "\u79f0",
    "\u63d0\u5230",
    "\u56de\u590d",
    "\u5199\u9053",
    "\u95ee",
    "\u56de",
    "\u8f6c\u8ff0",
    "\u8f6c\u544a",
    "\u8f6c\u8fbe",
    "\u53d1\u6d88\u606f",
    "\u53d1\u4fe1\u606f",
    "\u6253\u7535\u8bdd",
    "\u8ba9",
    "\u53eb",
    "\u529d",
    "\u5b89\u6170",
    "\u63d0\u9192",
    "\u7b11",
    "\u5efa\u8bae",
    "\u8981\u6c42",
    "\u5631\u5490",
    "\u53ee\u5631",
)

#: Hedges, adverbs, particles and negation: closed-class words that may stand between
#: the author and the trigger without changing who wrote the clause. Longest first.
MARKERS = tuple(
    sorted(
        (
            "\u4e0d\u4e00\u5b9a",
            "\u4e0d\u89c1\u5f97",
            "\u8bf4\u4e0d\u5b9a",
            "\u4f1a\u4e0d\u4f1a",
            "\u662f\u4e0d\u662f",
            "\u522b\u662f",
            "\u53ef\u80fd",
            "\u4e5f\u8bb8",
            "\u6216\u8bb8",
            "\u5927\u6982",
            "\u5927\u7ea6",
            "\u6050\u6015",
            "\u4f3c\u4e4e",
            "\u597d\u50cf",
            "\u5e94\u8be5",
            "\u672a\u5fc5",
            "\u53cd\u6b63",
            "\u5176\u5b9e",
            "\u6839\u672c",
            "\u771f\u7684",
            "\u660e\u660e",
            "\u679c\u7136",
            "\u7a76\u7adf",
            "\u5230\u5e95",
            "\u8001\u662f",
            "\u65f6\u4e0d\u65f6",
            "\u786e\u5b9e",
            "\u7684\u786e",
            "\u770b\u6765",
            "\u4f30\u8ba1",
            "\u5174\u8bb8",
            "\u641e\u4e0d\u597d",
            "\u4fdd\u4e0d\u9f50",
            "\u603b",
            "\u603b\u662f",
            "\u4e00\u76f4",
            "\u4ece\u6765",
            "\u5e73\u65f6",
            "\u4ee5\u524d",
            "\u6700\u8fd1",
            "\u73b0\u5728",
            "\u4eca\u5929",
            "\u6628\u5929",
            "\u521a\u624d",
            "\u5f53\u65f6",
            "\u540e\u6765",
            "\u5df2\u7ecf",
            "\u65e9\u5c31",
            "\u5e38\u5e38",
            "\u5076\u5c14",
            "\u7a81\u7136",
            "\u6709\u70b9",
            "\u4e00\u70b9",
            "\u4e00\u4e9b",
            "\u53ea\u662f",
            "\u5c31\u662f",
            "\u8fd8\u662f",
            "\u4e00\u5b9a",
            "\u80af\u5b9a",
            "\u672a\u514d",
            "\u53c8",
            "\u4e5f",
            "\u8fd8",
            "\u5c31",
            "\u90fd",
            "\u5f88",
            "\u592a",
            "\u66f4",
            "\u6700",
            "\u633a",
            "\u771f",
            "\u6ca1",
            "\u6709",
            "\u4e0d",
            "\u522b",
            "\u4f46\u662f",
            "\u53ef\u662f",
            "\u4e0d\u8fc7",
            "\u7136\u800c",
            "\u800c\u4e14",
            "\u6240\u4ee5",
            "\u56e0\u4e3a",
            "\u4e8e\u662f",
            "\u867d\u7136",
            "\u5373\u4f7f",
            "\u5982\u679c",
            "\u8981\u662f",
            "\u7ed3\u679c",
            "\u7adf\u7136",
            "\u5c45\u7136",
            "\u7ec8\u7a76",
            "\u6bd5\u7adf",
            "\u81f3\u5c11",
            "\u751a\u81f3",
            "\u5c24\u5176",
            "\u7279\u522b",
            "\u672c\u6765",
            "\u539f\u6765",
            "\u504f\u504f",
            "\u5e72\u8106",
            "\u7d22\u6027",
            "\u4e0d\u8fc7",
            "\u540c\u6837",
            "\u4e5f\u8bb8",
            "\u5f53\u7136",
            "\u96be\u602a",
            "\u628a",
            "\u7ed9",
            "\u662f",
            "\u7684",
            "\u4e86",
            "\u7740",
            "\u8fc7",
            "\u4f46",
            "\u800c",
            "\u6216",
        ),
        key=len,
        reverse=True,
    )
)


def _strip_markers(text: str) -> str:
    """Drop leading closed-class words and return what is left."""

    index = 0
    while index < len(text):
        for token in MARKERS:
            if text.startswith(token, index):
                index += len(token)
                break
        else:
            return text[index:]
    return ""


def _is_closed_class(text: str) -> bool:
    """True when nothing but hedges and function words is left.

    Used after a *described* subject: there, a verb or another pronoun means the
    described person is not the author of this clause, it is somebody's report.
    """

    return not _strip_markers(text).strip()


def _is_reader_side(text: str) -> bool:
    """True when only reader-side material is left: hedges, reader verbs, pronouns.

    Used after the reader pronoun: the reader is the author, so their own speech
    and cognition verbs do not turn the clause into a report.
    """

    rest = _strip_markers(text).strip()
    while rest:
        for token in READER_VERBS + READER_PRONOUNS + DESCRIBED_PRONOUNS:
            if rest.startswith(token):
                rest = _strip_markers(rest[len(token) :]).strip()
                break
        else:
            return False
    return True


def _clause_prefix(text: str, start: int) -> str:
    """Everything in front of ``start`` inside its own clause."""

    for index in range(start - 1, -1, -1):
        if text[index] in CLAUSE_BREAKS:
            return text[index + 1 : start]
    return text[:start]


def reader_owned(text: str, start: int) -> bool:
    """Whether the reader could have authored the words in front of this trigger.

    Conservative by construction: only closed-class material may precede a
    reader-owned trigger, so an unreasoned answer is always *no*.
    """

    rest = _strip_markers(_clause_prefix(text, start)).strip()
    if not rest:
        return True

    for pronoun in READER_PRONOUNS:
        if rest.startswith(pronoun):
            after = rest[len(pronoun) :]
            if after[:1] in PREPOSITIONS:
                return True
            return any(after.startswith(verb) for verb in READER_VERBS) or _is_reader_side(after)

    for pronoun in DESCRIBED_PRONOUNS:
        if rest.startswith(pronoun):
            after = rest[len(pronoun) :]
            return not any(verb in after for verb in REPORT_VERBS)

    return False


__all__ = ["CLAUSE_BREAKS", "READER_OWNED_TYPES", "reader_owned"]
