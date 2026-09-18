"""Turn a real analysis into the snapshot the casebook stores.

This module is the reason a client cannot file a forged verdict. The archive request carries the
reader's input, a mode, the target casebook and the reader's own event-time metadata - and nothing
else. The snapshot written to the casebook is built *here*, from an ``AnalysisResult`` this
process produced by running the engine, so "what NED said at the time" is NED's own record.

Two details are deliberate:

* ``generated_at`` is the engine's timestamp from this very run, and ``saved_at`` is the archive
  transaction's clock (the store's). Neither is accepted from a caller.
* an entry's ``entry_kind`` says which registrar produced it. That is read by running the two
  registrars again rather than by parsing a rule id, so a renamed rule pack cannot move a
  material into the wrong column.
"""

from __future__ import annotations

from ned.app.core import events as event_registry
from ned.app.core.models import AnalysisResult
from ned.app.core.rules import RuleBook
from ned.app.store.fingerprint import rules_fingerprint
from ned.app.store.models import CaseFileSnapshot, MaterialSnapshot, OccurredTime


def build_case_file_snapshot(
    result: AnalysisResult,
    *,
    occurred: OccurredTime | None = None,
    book: RuleBook | None = None,
    fingerprint: str | None = None,
) -> CaseFileSnapshot:
    """The archived snapshot of one analysis, built from the analysis itself."""

    event_ids = _event_material_ids(result.input, book)
    materials = tuple(
        MaterialSnapshot(
            material_index=index,
            entry_kind="event" if material.material_id in event_ids else "material",
            material_id=material.material_id,
            material_kind=material.material_kind,
            reported_content=material.reported_content,
            start_offset=material.start,
            end_offset=material.end,
            source_kind=material.source_kind,
            reporter_role=material.reporter_role,
            proposition_owner=material.proposition_owner,
            target=material.target,
            polarity=material.polarity,
            epistemic_status=material.epistemic_status,
            origin_rule_id=material.origin_rule_id,
        )
        for index, material in enumerate(result.materials)
    )
    return CaseFileSnapshot(
        input_text=result.input,
        mode=result.mode,
        language=result.language,
        recognition=result.recognition,
        verdict_code=result.verdict.code,
        verdict_text=result.verdict.text,
        verdict_severity=result.verdict.severity,
        signal_type=result.signal_type,
        signal_label=result.signal_label,
        engine_name=result.engine.name,
        engine_version=result.engine.version,
        rules_version=(book.version if book is not None else ""),
        rules_fingerprint=fingerprint if fingerprint is not None else rules_fingerprint(),
        generated_at=result.generated_at,
        occurred=occurred if occurred is not None else OccurredTime(),
        materials=materials,
    )


def _event_material_ids(text: str, book: RuleBook | None) -> frozenset[str]:
    """The ids of the materials the *event* registrar produced for this input."""

    if book is None:
        return frozenset()
    return frozenset(
        material.material_id for material in event_registry.register_events(text, book=book)
    )


__all__ = ["build_case_file_snapshot"]
