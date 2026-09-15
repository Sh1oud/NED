"""Text parsing: language detection, duration extraction, rule matching.

The parser is deterministic and offline. It does not understand language; it
matches configured patterns and reports what it matched, including the source
rule id, so every claim in a NED report can be traced back to a rule.
"""

from __future__ import annotations

import re
from functools import lru_cache

from ned.app.core import attribution
from ned.app.core.models import Duration, EvidenceSpan, Language, Polarity, SignalType
from ned.app.core.rules import RuleBook

#: Canonical unit name -> seconds.
UNIT_SECONDS: dict[str, float] = {
    "second": 1.0,
    "minute": 60.0,
    "hour": 3600.0,
    "day": 86400.0,
    "week": 604800.0,
    "month": 2592000.0,
    "year": 31536000.0,
}

_ZH_UNIT_ALIASES: dict[str, str] = {
    "秒": "second",
    "秒钟": "second",
    "分": "minute",
    "分钟": "minute",
    "小时": "hour",
    "个小时": "hour",
    "钟头": "hour",
    "天": "day",
    "日": "day",
    "周": "week",
    "星期": "week",
    "礼拜": "week",
    "月": "month",
    "个月": "month",
    "年": "year",
}

_EN_UNIT_ALIASES: dict[str, str] = {
    "second": "second",
    "seconds": "second",
    "sec": "second",
    "secs": "second",
    "minute": "minute",
    "minutes": "minute",
    "min": "minute",
    "mins": "minute",
    "hour": "hour",
    "hours": "hour",
    "hr": "hour",
    "hrs": "hour",
    "day": "day",
    "days": "day",
    "week": "week",
    "weeks": "week",
    "month": "month",
    "months": "month",
    "year": "year",
    "years": "year",
}

_CN_DIGITS: dict[str, int] = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}

_EN_NUMBER_WORDS: dict[str, float] = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "several": 3,
    "half a": 0.5,
    "half an": 0.5,
}

_ZH_DURATION_RE = re.compile(
    r"(?P<num>\d+(?:\.\d+)?|[零〇一二三四五六七八九十百两半]+)?\s*"
    r"(?P<unit>个小时|小时|钟头|分钟|分|秒钟|秒|个月|月|天|日|星期|礼拜|周|年)"
)

_EN_DURATION_RE = re.compile(
    r"(?P<num>\d+(?:\.\d+)?|half an|half a|several|a|an|one|two|three|four|five|six|"
    r"seven|eight|nine|ten)?\s*"
    r"(?P<unit>seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)",
    re.IGNORECASE,
)

_CLAUSE_SPLIT_RE = re.compile(r"[。！？!?；;\n]+|(?<=[，,])")

_LANGUAGE_UNIT_LABELS: dict[str, dict[str, str]] = {
    "zh": {
        "second": "秒",
        "minute": "分钟",
        "hour": "小时",
        "day": "天",
        "week": "周",
        "month": "个月",
        "year": "年",
    },
    "en": {
        "second": "second",
        "minute": "minute",
        "hour": "hour",
        "day": "day",
        "week": "week",
        "month": "month",
        "year": "year",
    },
}


@lru_cache(maxsize=2048)
def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile (and cache) a user-supplied rule pattern."""

    return re.compile(pattern, re.IGNORECASE)


def detect_language(text: str) -> Language:
    """Classify the input as Chinese, English or unknown.

    Chinese is assumed when a meaningful share of characters is CJK; mixed
    input counts as Chinese because the Chinese rules are the richer pack.
    """

    stripped = text.strip()
    if not stripped:
        return "unknown"
    cjk = sum(1 for ch in stripped if "\u4e00" <= ch <= "\u9fff")
    letters = sum(1 for ch in stripped if ch.isalpha())
    if cjk == 0:
        return "en" if letters else "unknown"
    if letters == 0:
        return "zh"
    return "zh" if cjk / letters >= 0.15 else "en"


def parse_cn_number(raw: str) -> float | None:
    """Parse a Chinese numeral such as ``二十五`` or ``两`` into a float."""

    if not raw:
        return None
    if raw == "半":
        return 0.5
    if raw.isdigit():
        return float(raw)
    if raw.replace(".", "", 1).isdigit():
        return float(raw)

    total = 0
    current = 0
    seen = False
    for char in raw:
        if char == "十":
            current = (current or 1) * 10
            total += current
            current = 0
            seen = True
        elif char == "百":
            current = (current or 1) * 100
            total += current
            current = 0
            seen = True
        elif char in _CN_DIGITS:
            current = _CN_DIGITS[char]
            seen = True
        else:
            return None
    if not seen:
        return None
    return float(total + current)


def _duration_from_match(match: re.Match[str], language: str) -> Duration | None:
    unit_raw = match.group("unit").lower()
    if language == "zh":
        unit = _ZH_UNIT_ALIASES.get(unit_raw)
        amount = parse_cn_number(match.group("num") or "")
    else:
        unit = _EN_UNIT_ALIASES.get(unit_raw)
        raw_num = (match.group("num") or "").lower()
        if not raw_num:
            amount = None
        elif raw_num in _EN_NUMBER_WORDS:
            amount = _EN_NUMBER_WORDS[raw_num]
        else:
            try:
                amount = float(raw_num)
            except ValueError:
                amount = None
    if unit is None or amount is None or amount <= 0:
        return None
    return Duration(
        seconds=amount * UNIT_SECONDS[unit],
        surface=match.group(0).strip(),
        unit=unit,
        amount=amount,
    )


def extract_durations(text: str) -> list[Duration]:
    """Extract every duration-looking span from ``text`` (both languages)."""

    found: list[Duration] = []
    seen: set[tuple[int, int]] = set()
    for pattern, language in ((_ZH_DURATION_RE, "zh"), (_EN_DURATION_RE, "en")):
        for match in pattern.finditer(text):
            key = (match.start(), match.end())
            if key in seen:
                continue
            duration = _duration_from_match(match, language)
            if duration is not None:
                seen.add(key)
                found.append(duration)
    found.sort(key=lambda item: item.seconds)
    return found


def human_duration(duration: Duration | None, language: str) -> str:
    """Render a duration for a human, e.g. ``5 分钟`` / ``5 minutes``."""

    if duration is None:
        return "—"
    labels = _LANGUAGE_UNIT_LABELS.get(language, _LANGUAGE_UNIT_LABELS["en"])
    unit = labels.get(duration.unit, duration.unit)
    amount = duration.amount
    amount_text = f"{amount:g}"
    if language == "en" and amount != 1:
        unit = f"{unit}s"
    if language == "zh":
        return f"{amount_text} {unit}"
    return f"{amount_text} {unit}"


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < other_end and other_start < end for other_start, other_end in spans)


def _dedupe_overlapping(
    matches: list[tuple[int, int, str]],
) -> list[tuple[int, int, str]]:
    """Collapse overlapping matches, preferring the longest at each position."""

    ordered = sorted(set(matches), key=lambda item: (item[0], -(item[1] - item[0]), item[2]))
    kept: list[tuple[int, int, str]] = []
    for candidate in ordered:
        start, end, _ = candidate
        if any(start < other_end and other_start < end for other_start, other_end, _ in kept):
            continue
        kept.append(candidate)
    return kept


def _nearest_duration(
    durations: list[Duration], text: str, start: int, end: int
) -> Duration | None:
    if not durations:
        return None
    best: tuple[int, Duration] | None = None
    for duration in durations:
        index = text.find(duration.surface)
        if index < 0:
            continue
        distance = min(abs(index - end), abs(start - (index + len(duration.surface))))
        if best is None or distance < best[0]:
            best = (distance, duration)
    return best[1] if best else durations[0]


def detect(text: str, book: RuleBook) -> list[EvidenceSpan]:
    """Match every configured signal rule against ``text``."""

    language = detect_language(text)
    durations = extract_durations(text)
    spans: list[EvidenceSpan] = []

    for rule in book.signals:
        matches: list[tuple[int, int, str]] = []
        for pattern in rule.patterns:
            compiled = compile_pattern(pattern)
            for match in compiled.finditer(text):
                matched_text = match.group(0)
                if not matched_text.strip():
                    continue
                matches.append((match.start(), match.end(), matched_text))
        if not matches:
            continue

        if rule.signal_type.value in attribution.READER_OWNED_TYPES:
            # Reader-owned families: the phrase has to belong to the reader. The
            # firewall only ever removes spans, and it answers "no" when unsure.
            matches = [item for item in matches if attribution.reader_owned(text, item[0])]
            if not matches:
                continue

        if rule.exclude:
            exclusions: list[tuple[int, int]] = []
            for pattern in rule.exclude:
                exclusions.extend(
                    (m.start(), m.end()) for m in compile_pattern(pattern).finditer(text)
                )
            matches = [item for item in matches if not _overlaps(item[0], item[1], exclusions)]
            if not matches:
                continue

        # Patterns within one rule deliberately overlap ("说喜欢我" inside
        # "她说喜欢我"). Count each region once, keeping the longest match, so a
        # single statement is never counted as repeated evidence.
        unique = _dedupe_overlapping(matches)
        first_start, first_end, _ = unique[0]
        duration = None
        if rule.uses_duration:
            duration = _nearest_duration(durations, text, first_start, first_end)

        description = ""
        if duration is not None:
            description = rule.text_for(
                rule.description,
                language,
                fallback="",
            )
            description = description.replace("{duration}", human_duration(duration, language))

        spans.append(
            EvidenceSpan(
                rule_id=rule.id,
                text=text[first_start:first_end],
                signal_type=rule.signal_type,
                label=rule.label_for(language),
                polarity=cast_polarity(rule.polarity),
                base_strength=rule.weight,
                information_content=rule.information_content,
                occurrences=len(unique),
                matched_keywords=[item[2] for item in unique][:5],
                start=first_start,
                end=first_end,
                duration=duration,
                description=description,
            )
        )

    spans.sort(key=lambda span: (-span.base_strength, span.start))
    return spans


def cast_polarity(value: str) -> Polarity:
    """Narrow a rule-pack polarity string to the public literal type."""

    if value in ("positive", "negative", "neutral", "self_discount"):
        return value  # type: ignore[return-value]
    return "neutral"


def spans_by_polarity(spans: list[EvidenceSpan], polarity: Polarity) -> list[EvidenceSpan]:
    return [span for span in spans if span.polarity == polarity]


def primary_span(spans: list[EvidenceSpan]) -> EvidenceSpan | None:
    """Pick the signal NED analyses first.

    Rule: positive evidence wins if there is any (it is the thing NED exists to
    de-weight); otherwise the strongest remaining signal wins. Ties break on
    strength, then on the order the rules were matched.
    """

    if not spans:
        return None
    positives = spans_by_polarity(spans, "positive")
    if positives:
        return max(positives, key=lambda span: span.base_strength)
    return max(spans, key=lambda span: span.base_strength)


def raw_interpretation(span: EvidenceSpan | None, book: RuleBook, language: str) -> str:
    """The plain reading of the primary signal, before NED interferes."""

    if span is None:
        return book.no_signal_text_for(language)
    for rule in book.signals:
        if rule.id == span.rule_id:
            return rule.text_for(rule.interpretations, language, fallback=span.label)
    return span.label


def split_clauses(text: str) -> list[str]:
    """Split free text into comparable clauses (used by the asymmetry detector)."""

    return [clause.strip() for clause in _CLAUSE_SPLIT_RE.split(text) if clause.strip()]


def signal_type_of(spans: list[EvidenceSpan]) -> SignalType:
    primary = primary_span(spans)
    return primary.signal_type if primary else SignalType.NONE


__all__ = [
    "UNIT_SECONDS",
    "compile_pattern",
    "detect",
    "detect_language",
    "extract_durations",
    "human_duration",
    "parse_cn_number",
    "primary_span",
    "raw_interpretation",
    "signal_type_of",
    "spans_by_polarity",
    "split_clauses",
]
