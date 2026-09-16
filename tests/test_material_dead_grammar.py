"""PHASE 3.5B-2C-3B-2: the dead material speech grammar stays deleted.

``CLAUSE_HEADS``, ``_clause_head_pattern()`` and ``_reporter_heads_its_clause()`` were the
material layer's own clause-head guard: an earlier design in which this module decided for
itself whether a reporter headed its clause. ``report_event`` owns that question now, so the
guard is gone. Freeze the deletion. If any of these names comes back, the material layer is
growing a second frame grammar again - which is exactly what the rewire removed.

``MaterialRule.speech_verbs`` deliberately stays, and is a different thing entirely. It is
runtime-dead but compatibility-live: a required field of a published rule pack, so deleting it
would make every pack that still declares it fail validation. It must keep loading, and it
must never be given runtime meaning again.
"""

from __future__ import annotations

from ned.app.core import material
from ned.app.core.rules import RuleBook

DEAD_NAMES = ("CLAUSE_HEADS", "_clause_head_pattern", "_reporter_heads_its_clause")


def test_the_dead_clause_head_grammar_is_gone() -> None:
    for name in DEAD_NAMES:
        assert not hasattr(material, name), name
        assert name not in material.__all__, name


def test_the_compatibility_field_still_loads() -> None:
    """A published pack field must keep validating; it is not this batch's to remove."""

    rule = material.material_rules(RuleBook.load())[0]
    assert isinstance(rule.speech_verbs, tuple)
    assert rule.speech_verbs


def test_the_compatibility_field_has_no_runtime_meaning() -> None:
    """It loads, and it decides nothing: the content pattern must not read it back."""

    rule = material.material_rules(RuleBook.load())[0]
    pattern = material.compile_material_rule(rule).pattern
    for verb in rule.speech_verbs:
        assert verb not in pattern, verb
