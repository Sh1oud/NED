"""The material registry: what an input reports, before any qualification.

A material rule reads the raw input. It never becomes an ``EvidenceSpan``, it never enters
the signal pipeline and it carries no weight: a material record says *what the input
reports*, never how much that report counts. Qualification, weighting and verdicts live in
other layers, and an absent qualification record means precisely "no qualification has been
produced".

Recognition is structural rather than a sentiment reading. A material exists when a
described person is reported to hold a negative attitude toward the reader: her frame, her
proposition, the reader as the target. The frame has to be hers - the reader must not be
the speaker, a named third party must not be the reporter, an uncertain frame is not a
report, and a negated attitude is not the attitude. Who spoke, to whom and whether the report
happened at all is not decided here: the shared report-event contract resolves the frame, and
this layer reads the resolved head to decide eligibility, and the resolved proposition to
delimit the content. Everything this layer does not recognise stays silent, which is the safe
direction: a missed report is a missing record, while an invented one puts words in somebody's
mouth.

``register_materials(text, ...)`` takes the input, not the evidence list, on purpose: a
material rule reads the input directly and a material record never becomes an
``EvidenceSpan``.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ned.app.core import attribution
from ned.app.core.models import ObservedMaterial, Polarity, SourceKind
from ned.app.core.rules import RuleBook

#: Who "I" is, read from the attribution layer so the material layer never grows a second
#: pronoun list of its own.
READER_PRONOUNS = attribution.READER_PRONOUNS

#: The material pack lives next to the signal pack and is read from the book's own
#: directory, so ``NED_RULES_DIR`` overrides it too. A pack that predates the material
#: layer has no such file and registers nothing, which keeps the layer additive.
MATERIAL_PACK = "materials.json"

#: Inline CJK formatting whitespace. The evidence firewall already rules that a space
#: between two CJK characters has no vote; this layer reads the same input, so it reads it
#: the same way. Newlines and punctuation still separate one proposition from the next.
INLINE_WHITESPACE = attribution.INLINE_WHITESPACE

_WS = f"[{INLINE_WHITESPACE}]*"


class MaterialRule(BaseModel):
    """One material-recognition rule: what the input reports, never how much it counts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    material_kind: str
    polarity: Polarity
    source_kind: SourceKind
    reporter_role: str
    proposition_owner: str
    target: str
    reporters: tuple[str, ...] = Field(min_length=1)
    #: Which report acts this rule may register, named the way the shared resolver names the
    #: frame head ("说", "告诉", "嘀咕", "抱怨"). This is semantic eligibility, never speech
    #: grammar: the layer never uses it to find a sender, a receiver, a frame or a modifier,
    #: and it never reads it to widen the content pattern. Empty registers nothing, so a pack
    #: that predates the field fails closed rather than inheriting the whole report grammar.
    allowed_report_heads: tuple[str, ...] = ()
    speech_verbs: tuple[str, ...] = Field(min_length=1)
    predicates: tuple[str, ...] = Field(min_length=1)
    degree_adverbs: tuple[str, ...] = ()
    reader: str = "\u6211"
    notes: str = ""


def material_id(kind: str, start: int, end: int, origin_rule_id: str) -> str:
    """A stable material id: no uuid, no clock, no process state."""

    seed = f"{kind}:{start}:{end}:{origin_rule_id}"
    return "mat_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _alternation(values: tuple[str, ...]) -> str:
    """A regex alternation, longest first so a longer wording is never shadowed."""

    return "|".join(re.escape(value) for value in sorted(values, key=len, reverse=True))


@lru_cache(maxsize=64)
def compile_material_rule(rule: MaterialRule) -> re.Pattern[str]:
    """The pattern a material rule reads with.

    The rule reads content only - a negative attitude with the reader as its target - and the
    pack supplies the vocabulary for that content. No frame, no modifier, no receiver and no
    ownership judgement is expressed here: those belong to the shared report-event contract,
    which decides whether a candidate is a report at all. Keeping them out is what stops a
    second, drifting speech grammar from growing inside the material layer.
    """

    proposition = [f"(?:(?P<owner>{_alternation(rule.reporters)}){_WS})?"]
    if rule.degree_adverbs:
        proposition.append(f"(?:(?P<adverb>{_alternation(rule.degree_adverbs)}){_WS})?")
    proposition.append(f"(?P<predicate>{_alternation(rule.predicates)})")
    proposition.append(_WS)
    proposition.append(f"(?P<reader>{re.escape(rule.reader)})")
    # The rule reads *content* only: a negative attitude toward the reader. Who reported it,
    # to whom, how, and whether the report happened at all belongs to the shared report-event
    # contract - never to a second frame grammar here.
    return re.compile("".join(["(?P<proposition>", *proposition, ")"]))


@lru_cache(maxsize=8)
def _load_material_rules(directory: str) -> tuple[MaterialRule, ...]:
    path = Path(directory) / MATERIAL_PACK
    if not path.is_file():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = tuple(MaterialRule.model_validate(item) for item in payload.get("rules", []))
    if len({rule.id for rule in rules}) != len(rules):
        raise ValueError("duplicate material rule ids in the material pack")
    return rules


def material_rules(book: RuleBook | None) -> tuple[MaterialRule, ...]:
    """The material rules of ``book``: empty when there is no book or no pack."""

    if book is None:
        return ()
    return _load_material_rules(str(book.source_dir))


def _observed_material(
    rule: MaterialRule, text: str, match: re.Match[str]
) -> ObservedMaterial | None:
    """The material one match reports, or ``None`` when the match is not a report."""

    from ned.app.core import report_event

    start, end = match.start("proposition"), match.end("proposition")
    resolved = report_event.resolve_report_event(text, start, end)
    frame = resolved.frame
    if frame.speech_verb not in rule.allowed_report_heads:
        # The report act itself is not eligible for this material rule. The shared resolver
        # accepts many more report acts than this rule may register, and eligibility is the
        # rule's own decision, taken here and from this one field. An absent or empty list
        # therefore registers nothing: the layer fails closed instead of widening silently.
        return None
    if frame.speech_sender not in rule.reporters:
        # No described person is resolved as the speaker: a relay, the reader's own words, an
        # uncertain frame. ``reporters`` only decides whether the resolved source is eligible.
        return None
    if frame.ambiguous:
        # The grammar could not settle who speaks: silence, not an attribution.
        return None
    if resolved.actuality != "ASSERTED":
        # The report event is negated, uncertain, questioned or not yet due.
        return None
    if start != resolved.content_start:
        # The candidate is not the proposition this report governs: it sits inside a qualified
        # phrase or somewhere else in the clause. Inline whitespace has no vote here, so the
        # semantic slot - not the raw frame offset - is the anchor.
        return None
    owner = resolved.proposition_owner
    if owner in READER_PRONOUNS:
        # The reader is the proposition's own actor: it reports what the reader is like.
        return None
    if owner and owner != frame.speech_sender:
        # An explicit owner who is not the sender: an owner conflict, never a stance transfer.
        return None
    return ObservedMaterial(
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


def register_materials(text: str, *, book: RuleBook | None = None) -> list[ObservedMaterial]:
    """The materials this input reports.

    Empty when no material rule recognises the input. ``start``, ``end`` and
    ``reported_content`` delimit the reported proposition: the frame belongs to the
    reporter, not to the material.
    """

    rules = material_rules(book)
    if not text or not rules:
        return []

    found: list[ObservedMaterial] = []
    seen: set[tuple[int, int, str]] = set()
    for rule in rules:
        for match in compile_material_rule(rule).finditer(text):
            material = _observed_material(rule, text, match)
            if material is None:
                continue
            key = (material.start, material.end, material.origin_rule_id)
            if key in seen:
                continue
            seen.add(key)
            found.append(material)
    found.sort(key=lambda item: (item.start, item.end, item.origin_rule_id))
    return found


__all__ = [
    "INLINE_WHITESPACE",
    "MATERIAL_PACK",
    "MaterialRule",
    "compile_material_rule",
    "material_id",
    "material_rules",
    "register_materials",
]
