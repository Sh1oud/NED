"""The shapes of a longitudinal review. Pure data: no store, no engine, no I/O."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Relation(StrEnum):
    """The six relations an M3 review may state. There is no seventh, and no number."""

    SUPPORTS = "supports"
    CONFLICTS = "conflicts"
    SUPERSEDED = "superseded"
    UNRELATED = "unrelated"
    NOT_COMPARABLE = "not_comparable"
    INSUFFICIENT = "insufficient"


class RecordedDirection(StrEnum):
    """Which way a recorded item reads, as it was recorded (never as re-read today)."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    NEUTRAL = "neutral"
    THIRD_PARTY = "third_party"
    NONE = "none"


class ReviewFamily(StrEnum):
    """The bounded material families M3 is allowed to compare."""

    RELATIONSHIP_STATUS = "relationship_status"
    BOUNDARY = "boundary"
    REPORTED_ATTITUDE = "reported_attitude"
    CONTACT_ACCESS = "contact_access"
    MEMORY_CARE_ACT = "memory_care_act"
    DEFERRAL = "deferral"
    THIRD_PARTY_OPPOSITION = "third_party_opposition"
    THIRD_PARTY_ACTIVITY = "third_party_activity"
    CASE_FILE_READING = "case_file_reading"
    UNKNOWN = "unknown"


class RelationReason(StrEnum):
    """Why a row got its relation. Machine-readable, so the UI language lives elsewhere."""

    DIRECTION_AGREES = "direction_agrees"
    DIRECTION_OPPOSES = "direction_opposes"
    SUPERSEDED_BY_LATER_BOUNDARY = "superseded_by_later_boundary"
    THIRD_PARTY_STANCE = "third_party_stance"
    THIRD_PARTY_ACTIVITY = "third_party_activity"
    DEFERRAL_DOES_NOT_SETTLE_DIRECTION = "deferral_does_not_settle_direction"
    RECORDED_TOO_THINLY = "recorded_too_thinly"
    NO_RECORDED_READING = "no_recorded_reading"
    CURRENT_CASE_HAS_NO_DIRECTION = "current_case_has_no_direction"
    BOUNDARY_ORDER_NOT_DETERMINABLE = "boundary_order_not_determinable"


class GoverningReason(StrEnum):
    """Why a governing boundary was, or was not, named."""

    LATEST_EXPLICIT_BOUNDARY = "latest_explicit_boundary"
    NO_EXPLICIT_BOUNDARY = "no_explicit_boundary"
    BOUNDARY_HAS_NO_EVENT_TIME = "boundary_has_no_event_time"
    ORDER_NOT_DETERMINABLE = "order_not_determinable"
    #: A safely later record exists after the boundary: the boundary is not the file's last word.
    LATER_RECORD_AFTER_BOUNDARY = "later_record_after_boundary"


class SummaryCode(StrEnum):
    """One sentence's worth of meaning; every renderer words it for itself."""

    NO_HISTORY = "no_history"
    NOTHING_COMPARABLE = "nothing_comparable"
    CURRENT_CASE_HAS_NO_DIRECTION = "current_case_has_no_direction"
    BOUNDARY_GOVERNS = "boundary_governs"
    ORDER_UNKNOWN = "order_unknown"
    MIXED_DIRECTIONS = "mixed_directions"
    ONLY_SUPPORTS = "only_supports"
    ONLY_CONFLICTS = "only_conflicts"


class ReviewItem(BaseModel):
    """One historical record, side by side with the current case. Never folded into it."""

    model_config = ConfigDict(extra="forbid")

    item_kind: Literal["entry", "case_file"]
    item_id: str
    case_file_id: str
    entry_kind: str = ""
    material_kind: str = ""
    family: ReviewFamily
    recorded_direction: RecordedDirection
    relation: Relation
    relation_reason: RelationReason
    reported_content: str = ""
    recorded_verdict_code: str = ""
    recorded_verdict_text: str = ""
    recorded_signal_type: str = ""
    occurred_at: str | None = None
    occurred_precision: str = "unknown"
    occurred_source: str = "unknown"
    governing: bool = False
    superseded_by: str | None = None


class ReviewCounts(BaseModel):
    """How many rows of each kind. Counts are not weights and are never summed into a score."""

    model_config = ConfigDict(extra="forbid")

    supports: int = 0
    conflicts: int = 0
    superseded: int = 0
    unrelated: int = 0
    not_comparable: int = 0
    insufficient: int = 0


class ReviewGoverning(BaseModel):
    """The boundary that governs the file, and the basis on which that was decided."""

    model_config = ConfigDict(extra="forbid")

    item_kind: Literal["entry", "case_file", "current_case"]
    item_id: str
    occurred_at: str | None = None
    occurred_precision: str = "unknown"
    reported_content: str = ""
    verdict_code: str = ""
    order_basis: Literal["declared_event_time"] = "declared_event_time"


class CasebookReview(BaseModel):
    """The casebook opinion: relations, counts and one sentence. Never a verdict."""

    model_config = ConfigDict(extra="forbid")

    casebook_id: str
    casebook_label: str
    case_files_read: int = 0
    entries_read: int = 0
    items_compared: int = 0
    current_direction: RecordedDirection = RecordedDirection.NONE
    items: list[ReviewItem] = Field(default_factory=list)
    counts: ReviewCounts = Field(default_factory=ReviewCounts)
    governing: ReviewGoverning | None = None
    governing_reason: GoverningReason = GoverningReason.NO_EXPLICIT_BOUNDARY
    order_known: bool = False
    summary_code: SummaryCode = SummaryCode.NO_HISTORY
    #: Small, language-neutral ingredients a renderer needs for the summary sentence.
    summary_args: dict[str, str] = Field(default_factory=dict)
    relation_assessed: bool = True
    #: Present for honesty: this release says nothing about whether a score exists.
    scored: bool = False


__all__ = [
    "CasebookReview",
    "GoverningReason",
    "RecordedDirection",
    "Relation",
    "RelationReason",
    "ReviewCounts",
    "ReviewFamily",
    "ReviewGoverning",
    "ReviewItem",
    "SummaryCode",
]
