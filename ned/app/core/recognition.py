"""The recognition state: what NED heard, as opposed to what it could conclude.

One ``no_signal`` verdict used to carry two different realities, and PR-0 (the RH-5
black-box pass) showed the cost: a reader who submitted ``她说她不喜欢我`` was told "no
classifiable signal" on the first screen while the material registry below it had already
filed the statement, and a reader who submitted ``她记得我生日`` was told the same thing
while nothing at all had been recognised. Those are different products states, and they are
now different values:

``adjudicated``
    evidence decided the report; a verdict was signed.
``material_registered``
    the input was understood well enough to file material, but nothing in it can be
    adjudicated by this release.
``nothing_recognized``
    this release recognised no material and no evidence.

The state is read from the two real detection layers - the evidence list and the material
list - and from nothing else: no string matching, no front-end judgement. It is exposed on
the result so that every surface (CLI today, the page in PR-3) reads one value.
"""

from __future__ import annotations

from collections.abc import Sequence

from ned.app.core.models import EvidenceSpan, ObservedMaterial, RecognitionState

ADJUDICATED: RecognitionState = "adjudicated"
MATERIAL_REGISTERED: RecognitionState = "material_registered"
NOTHING_RECOGNIZED: RecognitionState = "nothing_recognized"


def state_for(
    evidence: Sequence[EvidenceSpan] | None,
    materials: Sequence[ObservedMaterial] | None,
) -> RecognitionState:
    """The recognition state of one analysis, from its evidence and material lists."""

    if evidence:
        return ADJUDICATED
    if materials:
        return MATERIAL_REGISTERED
    return NOTHING_RECOGNIZED


__all__ = [
    "ADJUDICATED",
    "MATERIAL_REGISTERED",
    "NOTHING_RECOGNIZED",
    "state_for",
]
