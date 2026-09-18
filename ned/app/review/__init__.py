"""PR-6M3: the longitudinal casebook review - a parallel reading, never a second verdict.

The package is deliberately outside the semantic core:

* it is a **pure function over records**: the current analysis and the historical entries as they
  were *recorded*, and nothing else. Nothing here re-runs the engine on an old input, and nothing
  here can write to the casebook;
* it never touches ``verdict``, ``evidence``, ``materials``, ``breakdown``, ``recognition`` or any
  capacity figure of the current case: a review is a sibling of the report, not a part of it;
* it produces **relations and counts, never scores** - no total, no percentage, and no subtraction
  of positive from negative material.

See :mod:`ned.app.review.longitudinal` for the algorithm and :mod:`ned.app.review.relations` for
the tables it reads.
"""

from __future__ import annotations

from ned.app.review.longitudinal import (
    CurrentCase,
    ReviewRecord,
    build_casebook_review,
    current_case_facts,
)
from ned.app.review.models import (
    CasebookReview,
    GoverningReason,
    RecordedDirection,
    Relation,
    RelationReason,
    ReviewCounts,
    ReviewFamily,
    ReviewGoverning,
    ReviewItem,
    SummaryCode,
)
from ned.app.review.relations import (
    BOUNDARY_SIGNAL_TYPES,
    BOUNDARY_VERDICT_CODES,
    NEGATIVE_SIGNAL_TYPES,
    POSITIVE_SIGNAL_TYPES,
    MaterialFacts,
    classify_case_file,
    classify_material,
    directions_agree,
)
from ned.app.review.temporal import (
    MAX_OFFSET_EAST,
    MAX_OFFSET_WEST,
    ZONE_ENVELOPE,
    Comparison,
    Frame,
    Order,
    OrderReason,
    TemporalWindow,
    compare,
    strictly_before,
    undecidable,
)

__all__ = [
    "BOUNDARY_SIGNAL_TYPES",
    "BOUNDARY_VERDICT_CODES",
    "MAX_OFFSET_EAST",
    "MAX_OFFSET_WEST",
    "NEGATIVE_SIGNAL_TYPES",
    "POSITIVE_SIGNAL_TYPES",
    "ZONE_ENVELOPE",
    "CasebookReview",
    "Comparison",
    "CurrentCase",
    "Frame",
    "GoverningReason",
    "MaterialFacts",
    "Order",
    "OrderReason",
    "RecordedDirection",
    "Relation",
    "RelationReason",
    "ReviewCounts",
    "ReviewFamily",
    "ReviewGoverning",
    "ReviewItem",
    "ReviewRecord",
    "SummaryCode",
    "TemporalWindow",
    "build_casebook_review",
    "classify_case_file",
    "classify_material",
    "compare",
    "current_case_facts",
    "directions_agree",
    "strictly_before",
    "undecidable",
]
