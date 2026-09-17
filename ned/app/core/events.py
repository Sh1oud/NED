"""The event registry: bounded recognition of what an input reports as having happened.

PR-0 (the RH-5 black-box pass) showed that most ordinary inputs produce nothing at all:
``她记得我生日``, ``我们分手了``, ``她把我删了`` and ``她跟别的男生出去玩了`` were not classified as
anything, so the report said "no classifiable signal" and the reader could not tell whether
NED had heard them. The material layer already answered that question for one narrow frame
(a described person's reported negative attitude); this layer answers it for a small, closed
list of *event families*.

Design rules, in order of importance:

* an event record is **material, never evidence** - it carries no weight, it never becomes an
  ``EvidenceSpan`` and it never produces a verdict;
* recognition is **bounded**: eight families, each with an explicit pattern list and a
  ``commitment_reason`` saying why this release cannot sign a conclusion on it alone;
* every record quotes the input **verbatim** (``reported_content`` is the matched slice), and
  the layer never rewrites, normalises or paraphrases it;
* actor/reporter fields are only filled when the surface makes them certain; a family that
  cannot settle who acted is registered as low-commitment material rather than promoted to
  evidence (nothing here is ever promoted);
* whatever a rule does not recognise stays silent.

The pack lives next to the signal pack (``ned/app/rules/events.json``) and is read through the
rule book's own directory, so ``NED_RULES_DIR`` overrides it as well.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ned.app.core.material import material_id
from ned.app.core.models import ObservedMaterial, Polarity, SourceKind
from ned.app.core.rules import RuleBook

#: The event pack, beside the signal pack and the material pack.
EVENT_PACK = "events.json"


class EventRule(BaseModel):
    """One bounded event family: what the input reports, never how much it counts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    material_kind: str
    family: str
    polarity: Polarity
    source_kind: SourceKind
    reporter_role: str
    proposition_owner: str
    target: str
    #: Why this release cannot sign a conclusion on this material alone. Machine-readable,
    #: rendered as the "why not" line of the material screen.
    commitment_reason: str
    patterns: tuple[str, ...] = Field(min_length=1)
    labels: dict[str, str] = Field(default_factory=dict)
    notes: str = ""

    def label_for(self, language: str) -> str:
        return self.labels.get(language) or self.labels.get("zh") or self.material_kind


def compile_event_rule(rule: EventRule) -> re.Pattern[str]:
    """One alternation over the rule's own pattern list, longest first.

    Compiled per call on purpose: a rule carries its labels mapping, so it is not hashable,
    and ``re`` already caches compiled patterns internally.
    """

    ordered = sorted(rule.patterns, key=len, reverse=True)
    return re.compile("|".join(f"(?:{pattern})" for pattern in ordered))


@lru_cache(maxsize=8)
def _load_event_rules(directory: str) -> tuple[EventRule, ...]:
    path = Path(directory) / EVENT_PACK
    if not path.is_file():
        # A pack that predates this layer registers nothing: the layer is additive.
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = tuple(EventRule.model_validate(item) for item in payload.get("rules", []))
    if len({rule.id for rule in rules}) != len(rules):
        raise ValueError("duplicate event rule ids in the event pack")
    families: dict[str, str] = {}
    for rule in rules:
        known = families.setdefault(rule.family, rule.material_kind)
        if known != rule.material_kind:
            raise ValueError(f"family {rule.family!r} mixes material kinds")
    return rules


def event_rules(book: RuleBook | None) -> tuple[EventRule, ...]:
    """The event rules of ``book``: empty when there is no book or no pack."""

    if book is None:
        return ()
    return _load_event_rules(str(book.source_dir))


#: Opening and closing quotation marks this layer understands, read from the ownership
#: layer's own definition so the two never drift.
OPENING_QUOTES = ("\u201c", "'", "\u300c", "\u300e")
CLOSING_QUOTES = {"\u201c": "\u201d", "'": "'", "\u300c": "\u300d", "\u300e": "\u300f"}
#: How far a quoted proposition may run before the layer stops looking for its close.
QUOTE_WINDOW = 60


def _complete_quote(text: str, start: int, end: int) -> int:
    """Extend ``end`` to the closing quote when the match sits inside a quotation.

    ``reported_content`` is always a verbatim slice, and a slice that stops in the middle of
    her quotation ("她说“你人很好") reads like a mangled quote even though it is exact. When
    the phrase opens or sits inside a quotation, the layer quotes the whole thing. The
    quotation may open right before the match (a quoted proposition) or inside it (the match
    starts at the reporting frame).
    """

    for at in range(min(end, len(text)) - 1, start - 1, -1):
        opener = text[at]
        if opener not in OPENING_QUOTES:
            continue
        closer = CLOSING_QUOTES[opener]
        close_at = text.find(closer, end)
        if close_at < 0 or close_at - end > QUOTE_WINDOW or "\n" in text[end:close_at]:
            return end
        return close_at + 1
    return end


def register_events(text: str, *, book: RuleBook | None = None) -> list[ObservedMaterial]:
    """The events this input reports, as material records.

    ``reported_content`` is always a verbatim slice of ``text``; ``start``/``end`` delimit it.
    At most one record per family is filed, at the earliest match, so a paragraph that
    mentions the same family twice is one material, not two.
    """

    rules = event_rules(book)
    if not text or not rules:
        return []

    found: list[ObservedMaterial] = []
    for rule in rules:
        match = compile_event_rule(rule).search(text)
        if match is None:
            continue
        if not match.group(0).strip():
            continue
        start, end = match.start(), _complete_quote(text, match.start(), match.end())
        found.append(
            ObservedMaterial(
                material_id=material_id(rule.material_kind, start, end, rule.id),
                material_kind=rule.material_kind,
                reported_content=text[start:end],
                start=start,
                end=end,
                reporter_role=rule.reporter_role,
                proposition_owner=rule.proposition_owner,
                target=rule.target,
                polarity=rule.polarity,
                source_kind=rule.source_kind,
                origin_rule_id=rule.id,
            )
        )
    found.sort(key=lambda item: (item.start, item.end, item.origin_rule_id))
    return found


def commitment_reason(book: RuleBook | None, origin_rule_id: str) -> str:
    """The machine-readable reason the pack gives for one event family."""

    for rule in event_rules(book):
        if rule.id == origin_rule_id:
            return rule.commitment_reason
    return ""


def event_label(book: RuleBook | None, origin_rule_id: str, language: str = "zh") -> str:
    """The family label for one event rule, in the requested language."""

    for rule in event_rules(book):
        if rule.id == origin_rule_id:
            return rule.label_for(language)
    return ""


__all__ = [
    "EVENT_PACK",
    "EventRule",
    "commitment_reason",
    "compile_event_rule",
    "event_label",
    "event_rules",
    "register_events",
]
