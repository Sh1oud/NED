"""What M3 is allowed to compare, and which way each recorded family reads.

Everything here is *as recorded*: the tables are keyed on the material kind and rule id the entry
carried when it was filed, never on a fresh reading of the old input. M4 is where re-reading lives.

Three deliberate narrowings:

* only the families the commander listed are comparable. Anything M3 does not recognise is
  ``unknown`` and a review may only call it ``insufficient`` - it is never guessed at;
* a third party's stance is its own direction (``third_party``). It can never be read as the
  described person's position, so it is never promoted to ``conflicts``/``supports``;
* "explicit boundary" is a narrower set than "boundary": a soft fit judgement
  (``她说我们不太合适``) can oppose a reading, but it can never govern the file.
"""

from __future__ import annotations

from dataclasses import dataclass

from ned.app.review.models import RecordedDirection, ReviewFamily

#: Signals that read as positive evidence about the other person.
POSITIVE_SIGNAL_TYPES: frozenset[str] = frozenset(
    {
        "explicit_affection",
        "expressed_love",
        "missing_you",
        "commitment_offer",
        "marriage",
        "initiation",
        "sustained_interaction",
        "compliment",
        "care",
        "meetup_invitation",
        "responsiveness",
    }
)

#: Signals that read against the relationship. The two self-directed ones are included on
#: purpose: the case's own reading is negative, and that is what a review compares against.
NEGATIVE_SIGNAL_TYPES: frozenset[str] = frozenset(
    {
        "hostile_expression",
        "response_latency",
        "cold_reply",
        "plan_cancelled",
        "self_negative_belief",
        "self_discount",
    }
)

#: The one signal type that states a boundary about the two of them.
BOUNDARY_SIGNAL_TYPES: frozenset[str] = frozenset({"direct_rejection"})

#: Verdict codes that state a boundary even when no material was filed for it.
BOUNDARY_VERDICT_CODES: frozenset[str] = frozenset({"ned.direct_rejection"})


@dataclass(frozen=True)
class MaterialClass:
    """What one recorded material is, and which way it reads."""

    family: ReviewFamily
    direction: RecordedDirection
    #: True only for a boundary that may govern the file outright.
    explicit_boundary: bool = False


@dataclass(frozen=True)
class MaterialFacts:
    """The recorded fields of one material, from the store or from the current analysis.

    Deliberately tiny: a review may look at these five recorded facts and nothing else. In
    particular it never sees ``saved_at``, so no relation can accidentally be decided by the time
    something was filed rather than the time it happened.
    """

    material_kind: str
    origin_rule_id: str = ""
    polarity: str = "neutral"
    proposition_owner: str = ""
    target: str = ""


@dataclass(frozen=True)
class CaseFileClass:
    """What a case file with no comparable material still records about itself."""

    family: ReviewFamily
    direction: RecordedDirection
    explicit_boundary: bool = False


def _rule_suffix(origin_rule_id: str) -> str:
    return origin_rule_id.rsplit(".", 1)[-1] if origin_rule_id else ""


def classify_material(facts: MaterialFacts) -> MaterialClass:
    """Read one recorded material into (family, direction, may-govern)."""

    kind = facts.material_kind
    suffix = _rule_suffix(facts.origin_rule_id)

    if kind == "relationship_status":
        if suffix == "relationship_ended":
            # A stated end of the relationship is a state boundary.
            return MaterialClass(ReviewFamily.BOUNDARY, RecordedDirection.BOUNDARY, True)
        if suffix == "friends_only_declared":
            return MaterialClass(ReviewFamily.BOUNDARY, RecordedDirection.BOUNDARY, True)
        if suffix == "relationship_started":
            return MaterialClass(ReviewFamily.RELATIONSHIP_STATUS, RecordedDirection.POSITIVE)
        return MaterialClass(
            ReviewFamily.RELATIONSHIP_STATUS,
            RecordedDirection.POSITIVE
            if facts.polarity == "positive"
            else RecordedDirection.NEGATIVE,
        )
    if kind == "contact_access":
        return MaterialClass(ReviewFamily.CONTACT_ACCESS, RecordedDirection.NEGATIVE)
    if kind == "memory_care_act":
        return MaterialClass(ReviewFamily.MEMORY_CARE_ACT, RecordedDirection.POSITIVE)
    if kind == "reported_evaluation":
        if suffix == "evaluative_speech_soft_decline":
            # A soft fit judgement is a boundary for direction only; it never governs.
            return MaterialClass(ReviewFamily.BOUNDARY, RecordedDirection.BOUNDARY, False)
        return MaterialClass(ReviewFamily.REPORTED_ATTITUDE, RecordedDirection.NEGATIVE)
    if kind == "reported_negative_interpersonal":
        return MaterialClass(ReviewFamily.REPORTED_ATTITUDE, RecordedDirection.NEGATIVE)
    if kind == "reported_dismissal":
        return MaterialClass(ReviewFamily.BOUNDARY, RecordedDirection.BOUNDARY, True)
    if kind == "reported_deferral":
        return MaterialClass(ReviewFamily.DEFERRAL, RecordedDirection.NEUTRAL)
    if kind == "external_opposition":
        return MaterialClass(ReviewFamily.THIRD_PARTY_OPPOSITION, RecordedDirection.THIRD_PARTY)
    if kind == "social_interaction":
        return MaterialClass(ReviewFamily.THIRD_PARTY_ACTIVITY, RecordedDirection.THIRD_PARTY)
    if kind == "user_note":
        # The reader's own note is not a material about anyone: recorded, but not comparable.
        return MaterialClass(ReviewFamily.UNKNOWN, RecordedDirection.NONE)
    return MaterialClass(ReviewFamily.UNKNOWN, RecordedDirection.NONE)


def classify_case_file(*, signal_type: str, verdict_code: str) -> CaseFileClass:
    """Read a case file whose input registered no comparable material.

    The recorded signal and verdict are as-of-archive facts: using them is not re-reading the old
    input, which is why this is the only fallback M3 has.
    """

    if signal_type in BOUNDARY_SIGNAL_TYPES or verdict_code in BOUNDARY_VERDICT_CODES:
        return CaseFileClass(ReviewFamily.BOUNDARY, RecordedDirection.BOUNDARY, True)
    if signal_type in POSITIVE_SIGNAL_TYPES:
        return CaseFileClass(ReviewFamily.CASE_FILE_READING, RecordedDirection.POSITIVE)
    if signal_type in NEGATIVE_SIGNAL_TYPES:
        return CaseFileClass(ReviewFamily.CASE_FILE_READING, RecordedDirection.NEGATIVE)
    return CaseFileClass(ReviewFamily.CASE_FILE_READING, RecordedDirection.NONE)


def direction_sign(direction: RecordedDirection) -> int | None:
    """Map a direction onto the only comparison M3 makes: does it read the same way?

    A boundary and a negative reading share a sign: both mean "this is not a positive reading".
    That is a classification, not arithmetic - nothing is added up, and no row is weighted.
    """

    if direction is RecordedDirection.POSITIVE:
        return 1
    if direction in (RecordedDirection.NEGATIVE, RecordedDirection.BOUNDARY):
        return -1
    return None


def directions_agree(current: RecordedDirection, recorded: RecordedDirection) -> bool | None:
    """Do the two recorded readings point the same way? ``None`` when one of them has no sign."""

    left = direction_sign(current)
    right = direction_sign(recorded)
    if left is None or right is None:
        return None
    return left == right


__all__ = [
    "BOUNDARY_SIGNAL_TYPES",
    "BOUNDARY_VERDICT_CODES",
    "NEGATIVE_SIGNAL_TYPES",
    "POSITIVE_SIGNAL_TYPES",
    "CaseFileClass",
    "MaterialClass",
    "MaterialFacts",
    "classify_case_file",
    "classify_material",
    "direction_sign",
    "directions_agree",
]
