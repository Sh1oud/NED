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
report, and a negated attitude is not the attitude. Everything this layer does not
recognise stays silent, which is the safe direction: a missed report is a missing record,
while an invented one puts words in somebody's mouth.

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

#: The material pack lives next to the signal pack and is read from the book's own
#: directory, so ``NED_RULES_DIR`` overrides it too. A pack that predates the material
#: layer has no such file and registers nothing, which keeps the layer additive.
MATERIAL_PACK = "materials.json"

#: Inline CJK formatting whitespace. The evidence firewall already rules that a space
#: between two CJK characters has no vote; this layer reads the same input, so it reads it
#: the same way. Newlines and punctuation still separate one proposition from the next.
INLINE_WHITESPACE = attribution.INLINE_WHITESPACE

_WS = f"[{INLINE_WHITESPACE}]*"

#: A clause ends here. Only a clause break and closed-class words may stand in front of a
#: reporter, which is what keeps the reader's own frame ("我跟她说她讨厌我") and a relay
#: ("朋友说她说她讨厌我") out of the material layer.
CLAUSE_HEADS = "\u3002\uff01\uff1f!?\uff0c,\uff1b;\u3001\n\r"


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

    The shape is fixed - reporter, frame, proposition, reader as target - and the pack
    supplies the vocabulary. Only the pack's own words may stand between the frame and the
    predicate, so an uncertainty marker or a negation is never read past: "她可能说讨厌我"
    and "她不讨厌我" do not reach the predicate at all.
    """

    proposition = [f"(?:(?P<owner>{_alternation(rule.reporters)}){_WS})?"]
    if rule.degree_adverbs:
        proposition.append(f"(?:(?P<adverb>{_alternation(rule.degree_adverbs)}){_WS})?")
    proposition.append(f"(?P<predicate>{_alternation(rule.predicates)})")
    proposition.append(_WS)
    proposition.append(f"(?P<reader>{re.escape(rule.reader)})")
    return re.compile(
        "".join(
            [
                f"(?P<reporter>{_alternation(rule.reporters)})",
                _WS,
                f"(?P<frame>{_alternation(rule.speech_verbs)})",
                _WS,
                "(?P<proposition>",
                *proposition,
                ")",
            ]
        )
    )


@lru_cache(maxsize=1)
def _clause_head_pattern() -> re.Pattern[str]:
    """A reporter heads its clause when only a break and closed-class words precede it."""

    markers = "|".join(
        re.escape(marker) for marker in sorted(attribution.MARKERS, key=len, reverse=True)
    )
    return re.compile(rf"(?:^|[{re.escape(CLAUSE_HEADS)}])(?:{markers}|[{INLINE_WHITESPACE}]+)*$")


def _reporter_heads_its_clause(text: str, start: int) -> bool:
    """Whether only a clause break and closed-class words stand in front of the reporter."""

    return bool(_clause_head_pattern().search(text[:start]))


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

    reporter = match.group("reporter")
    owner = match.group("owner")
    if owner is not None and owner != reporter:
        # The proposition belongs to somebody else: a relay or a quotation, not her own
        # report about the reader.
        return None
    if not _reporter_heads_its_clause(text, match.start("reporter")):
        # The reader or a named third party speaks this frame.
        return None
    start, end = match.start("proposition"), match.end("proposition")
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
    "CLAUSE_HEADS",
    "INLINE_WHITESPACE",
    "MATERIAL_PACK",
    "MaterialRule",
    "compile_material_rule",
    "material_id",
    "material_rules",
    "register_materials",
]
