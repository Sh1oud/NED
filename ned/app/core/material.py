"""The material registry: what an input reports, before any qualification.

This layer is deliberately empty at this stage. No material family exists yet, so every
input registers no material and every existing behaviour is unchanged. The signature is
``register_materials(text, ...)`` rather than ``register(spans)`` on purpose: a material
rule reads the input, not the evidence list, and a material record never becomes an
``EvidenceSpan``. Qualification, weighting and verdicts live in other layers.
"""

from __future__ import annotations

import hashlib

from ned.app.core.models import ObservedMaterial
from ned.app.core.rules import RuleBook


def material_id(kind: str, start: int, end: int, origin_rule_id: str) -> str:
    """A stable material id: no uuid, no clock, no process state."""

    seed = f"{kind}:{start}:{end}:{origin_rule_id}"
    return "mat_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def register_materials(text: str, *, book: RuleBook | None = None) -> list[ObservedMaterial]:
    """The materials this input reports.

    Empty until a material family exists: the registry is plumbing, not recognition.
    """

    _ = (text, book)
    return []


__all__ = ["material_id", "register_materials"]
