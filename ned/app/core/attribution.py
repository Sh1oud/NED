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
  a function word, or one of the reader's own speech and cognition verbs. After a
  described subject the reader may also appear as the object of a preposition, but
  never as the subject of an un-prepositioned verb.

Anything containing a content word is a frame, and a frame is somebody else's words.
That is what makes the closure provable rather than sampled: the grammar only accepts
closed-class vocabulary, so an arbitrary named third party (``老师``, ``小王``,
``群里有人``) cannot be admitted by construction, and neither can an arbitrary
reporting predicate (``转述``, ``提了一句``, ``嘀咕``, ``断言``) — the closure never
asks which verbs are known, only whether the material is closed-class. Extending the guard for a new
*person* or a new *reporting verb* is therefore never necessary.
"""

from __future__ import annotations

#: Signal types whose contract is "the reader's own words".
READER_OWNED_TYPES = frozenset({"self_discount", "self_negative_belief"})

#: A clause ends here. Anything after the last break belongs to the trigger's clause.
CLAUSE_BREAKS = "\u3002\uff01\uff1f!?\uff0c,\uff1b;\u3001\n\r\t "

#: Inline formatting whitespace. Inside a CJK sentence it separates characters, so it is
#: not a clause boundary, not a content token and not a speaker boundary. Between or next
#: to ASCII it keeps its own meaning - English words need their spaces.
INLINE_WHITESPACE = " \t\u3000"

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


def _reader_is_a_prepositional_object(text: str) -> bool:
    """True when every \u6211 in the text is the object of a preposition.

    Used for a described subject: "\u5979\u5bf9\u6211\u597d" is the reader's own clause about her,
    while "\u5979\u8ddf\u6211\u8bf4\u6211\u60f3\u592a\u591a\u4e86" has a second, un-prepositioned
    \u6211 \u2014 which makes it her report. No verb has to be named for that
    distinction.
    """

    for index, char in enumerate(text):
        if char == "\u6211" and (index == 0 or text[index - 1] not in PREPOSITIONS):
            return False
    return True


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


def _is_cjk(char: str) -> bool:
    """Whether ``char`` is a CJK character (a one-character string, or empty)."""

    return char != "" and "\u3400" <= char <= "\u9fff"


def _is_cjk_inline_whitespace_run(text: str, start: int, end: int) -> bool:
    """Whether the whitespace run ``text[start:end]`` is CJK formatting whitespace.

    Only a run whose two neighbours are both CJK characters is a formatting separator.
    A run at the edge of the text, or one next to ASCII ("I think she is just being
    polite"), keeps whatever structural meaning it had.
    """

    if start <= 0 or end >= len(text):
        return False
    return _is_cjk(text[start - 1]) and _is_cjk(text[end])


def _strip_cjk_inline_whitespace(text: str) -> str:
    """Drop the CJK formatting separators from a clause read by the firewall."""

    kept: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in INLINE_WHITESPACE:
            end = index
            while end < len(text) and text[end] in INLINE_WHITESPACE:
                end += 1
            if _is_cjk_inline_whitespace_run(text, index, end):
                index = end
                continue
            kept.append(char)
            index += 1
            continue
        kept.append(char)
        index += 1
    return "".join(kept)


def _clause_prefix(text: str, start: int) -> str:
    """Everything in front of ``start`` inside its own clause.

    CJK formatting whitespace does not end the clause, so the reader of "他 说 我 想太多"
    still sees the whole clause; newline and punctuation keep ending it.
    """

    index = start - 1
    while index >= 0:
        char = text[index]
        if char in CLAUSE_BREAKS:
            if char in INLINE_WHITESPACE:
                run_start = index
                while run_start > 0 and text[run_start - 1] in INLINE_WHITESPACE:
                    run_start -= 1
                run_end = index + 1
                while run_end < start and text[run_end] in INLINE_WHITESPACE:
                    run_end += 1
                if _is_cjk_inline_whitespace_run(text, run_start, run_end):
                    index = run_start - 1
                    continue
            return text[index + 1 : start]
        index -= 1
    return text[:start]


def _is_her_speech_to_the_reader(text: str, start: int) -> bool:
    """Whether the report frame in front of the trigger is her speech to the reader.

    The frame - including the single clause-punctuation continuation - is resolved once in
    ``report_event``, so this screen and the material layer share one implementation instead
    of copying it. A receiver frame whose speaker is the described person and whose receiver
    is the reader means the words in front of the trigger are a report, not the reader's own
    wording. The proposition's own actor must not be the reader.
    """

    from ned.app.core import report_event

    resolved = report_event.resolve_report_event(text, start)
    frame = resolved.frame
    if frame.speech_sender in DESCRIBED_PRONOUNS and frame.receiver in READER_PRONOUNS:
        return resolved.proposition_owner not in READER_PRONOUNS
    return False


def reader_owned(text: str, start: int) -> bool:
    """Whether the reader could have authored the words in front of this trigger.

    Conservative by construction: only closed-class material may precede a
    reader-owned trigger, so an unreasoned answer is always *no*.
    """

    if _is_her_speech_to_the_reader(text, start):
        # Her frame with the reader as its receiver: the trigger is her words, the
        # same contract ``boundary.hers`` already reads.
        return False
    clause = _strip_cjk_inline_whitespace(_clause_prefix(text, start))
    rest = _strip_markers(clause).strip()
    if not rest:
        return True

    for pronoun in READER_PRONOUNS:
        if rest.startswith(pronoun):
            after = rest[len(pronoun) :]
            if after[:1] in PREPOSITIONS:
                return True
            lead = (
                "是不是" if after.startswith("是不是") else ("也" if after.startswith("也") else "")
            )
            if after[len(lead) :].startswith(("不应该", "不该")):
                # 我不该想太多 / 我也不该想太多 / 我是不是不该想太多: the reader's own
                # conclusion, negation included. Only this branch - the reader's own
                # clause - takes it, so a relay keeps its own reading.
                return True
            return any(after.startswith(verb) for verb in READER_VERBS) or _is_reader_side(after)

    for pronoun in DESCRIBED_PRONOUNS:
        if rest.startswith(pronoun):
            after = rest[len(pronoun) :]
            if after.startswith(("不应该", "不该")):
                # 她不应该想太多: a claim about her, not the reader's own discount.
                return False
            if _is_closed_class(after):
                return True
            if after[:1] in PREPOSITIONS and after[1:2] in READER_PRONOUNS:
                return _reader_is_a_prepositional_object(after)
            return False

    return False


__all__ = ["CLAUSE_BREAKS", "READER_OWNED_TYPES", "reader_owned"]
