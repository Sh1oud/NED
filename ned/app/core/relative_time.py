"""PR-6M4D: recognise that an input *mentions* a relative time. Never resolve one.

This module answers exactly one question - does this text use wording like "昨天" or "last week" -
and it answers it as a fact about the text. It does not know today's date, it takes no clock, and
it produces no date: NED may tell a reader that their time is not pinned down, but it must not
invent the day they meant.

Nothing on the analysis path imports this module, so no verdict, no evidence and no material
registration can depend on it. Its only consumers are the casebook's archive path (which records
``occurred_source="input_relative"``) and the hint the interface shows before filing.
"""

from __future__ import annotations

#: Chinese wordings that point at a time relative to "now". Longest first when scanning, so a
#: longer phrase is never reported as the shorter one inside it.
CHINESE_CUES: tuple[str, ...] = (
    "大前天",
    "大后天",
    "前几天",
    "前阵子",
    "几个月前",
    "几年前",
    "几天前",
    "第二天",
    "那天晚上",
    "那天",
    "当晚",
    "隔天",
    "昨天",
    "前天",
    "今天",
    "明天",
    "后天",
    "上周",
    "本周",
    "这周",
    "下周",
    "上星期",
    "这星期",
    "下星期",
    "上个月",
    "这个月",
    "本月",
    "下个月",
    "去年",
    "今年",
    "明年",
    "前年",
    "后年",
    "刚才",
    "刚刚",
    "最近",
    "以前",
    "之前",
    "之后",
    "以后",
    "后来",
    "起初",
    "当初",
)

#: English wordings with the same meaning.
ENGLISH_CUES: tuple[str, ...] = (
    "the day before yesterday",
    "the day after tomorrow",
    "a few days ago",
    "a few months ago",
    "a few years ago",
    "the other day",
    "last week",
    "this week",
    "next week",
    "last month",
    "this month",
    "next month",
    "last year",
    "this year",
    "next year",
    "yesterday",
    "today",
    "tomorrow",
    "recently",
    "lately",
    "earlier",
    "later",
    "back then",
    "at the time",
    "just now",
    "before",
    "after",
)


def relative_time_cues(text: str) -> tuple[str, ...]:
    """Every relative-time wording the text uses, in order, without overlaps.

    Deterministic and case-insensitive for the English words. The result is evidence that the
    text mentioned time; it is never an input to a date.
    """

    if not text:
        return ()
    lowered = text.lower()
    spans: list[tuple[int, int, str]] = []
    for cue in sorted((*CHINESE_CUES, *ENGLISH_CUES), key=len, reverse=True):
        needle = cue.lower()
        start = lowered.find(needle)
        while start >= 0:
            end = start + len(needle)
            taken = any(
                start < other_end and other_start < end for other_start, other_end, _ in spans
            )
            if not taken:
                spans.append((start, end, cue))
            start = lowered.find(needle, start + 1)
    spans.sort(key=lambda item: item[0])
    ordered: list[str] = []
    for _start, _end, cue in spans:
        if cue not in ordered:
            ordered.append(cue)
    return tuple(ordered)


def has_relative_time(text: str) -> bool:
    """Whether the text mentions a time relative to now at all."""

    return bool(relative_time_cues(text))


__all__ = ["CHINESE_CUES", "ENGLISH_CUES", "has_relative_time", "relative_time_cues"]
