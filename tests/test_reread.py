"""M4C: the reread unit - alignment by hand, one analysis per case file, and the five classes.

The alignment rules are the product rules of this batch: kind plus span overlap, one candidate or
nothing, and no guessing when two candidates fit.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.rules import RuleBook
from ned.app.review import (
    Difference,
    RecordedCaseFile,
    RecordedEntry,
    align,
    reread_case_file,
)
from ned.app.review.reread import OVERLAP_THRESHOLD, _Material
from ned.app.store import rules_fingerprint
from ned.app.store.snapshot import build_case_file_snapshot

RULES = Path(__file__).resolve().parents[1] / "ned" / "app" / "rules"


def entry(
    *,
    entry_id: str = "en_1",
    kind: str = "memory_care_act",
    content: str = "她记得我生日",
    span: tuple[int, int] = (0, 6),
    polarity: str = "positive",
    epistemic: str = "reported",
    owner: str = "described_person",
    role: str = "reader",
    target: str = "reader",
    rule: str = "zh.event.memory_act",
) -> RecordedEntry:
    return RecordedEntry(
        entry_id=entry_id,
        entry_kind="event",
        material_index=0,
        material_kind=kind,
        reported_content=content,
        start_offset=span[0],
        end_offset=span[1],
        polarity=polarity,
        epistemic_status=epistemic,
        proposition_owner=owner,
        reporter_role=role,
        target=target,
        origin_rule_id=rule,
    )


def material(
    *,
    kind: str = "memory_care_act",
    content: str = "她记得我生日",
    span: tuple[int, int] = (0, 6),
    polarity: str = "positive",
    epistemic: str = "reported",
    owner: str = "described_person",
    role: str = "reader",
    target: str = "reader",
    rule: str = "zh.event.memory_act",
) -> _Material:
    return _Material(
        kind, content, span[0], span[1], polarity, epistemic, owner, role, target, rule
    )


# --------------------------------------------------------------- the five classes ---
def test_an_identical_record_is_same() -> None:
    rows = align((entry(),), (material(),))
    assert [row.difference for row in rows] == [Difference.SAME]
    assert rows[0].changed_fields == []


@pytest.mark.parametrize(
    ("changed", "field"),
    [
        ({"polarity": "neutral"}, "polarity"),
        ({"epistemic": "asserted"}, "epistemic_status"),
        ({"owner": "third_party"}, "proposition_owner"),
        ({"role": "described_person"}, "reporter_role"),
        ({"target": "third_party"}, "target"),
        ({"content": "她记得我生日，还记错日期"}, "reported_content"),
    ],
)
def test_a_moved_structural_field_is_changed(changed, field) -> None:
    rows = align((entry(),), (material(**changed),))
    assert rows[0].difference is Difference.CHANGED
    assert field in rows[0].changed_fields


def test_a_rule_rename_alone_is_same_with_a_flag() -> None:
    """Renaming a rule inside the pack is not the archive having been wrong."""

    rows = align((entry(),), (material(rule="zh.event.memory_act_v2"),))
    assert rows[0].difference is Difference.SAME
    assert rows[0].rule_id_changed is True
    assert rows[0].changed_fields == []


def test_a_record_with_no_counterpart_is_missing() -> None:
    rows = align((entry(),), (material(kind="contact_access", span=(20, 30)),))
    assert [row.difference for row in rows] == [Difference.MISSING, Difference.NEW]
    assert rows[0].recorded_slice == "她记得我生日"
    assert rows[1].reread_kind == "contact_access"


def test_a_material_nobody_recorded_is_new() -> None:
    rows = align(
        (entry(span=(0, 6)),),
        (material(span=(0, 6)), material(kind="contact_access", span=(20, 30))),
    )
    assert [row.difference for row in rows] == [Difference.SAME, Difference.NEW]


def test_two_candidates_are_ambiguous_and_are_not_guessed() -> None:
    """Synthetic by construction: one recorded span, two today-materials covering it."""

    rows = align(
        (entry(span=(0, 20), content="x" * 20),),
        (material(span=(0, 12), content="x" * 12), material(span=(10, 20), content="x" * 10)),
    )
    assert [row.difference for row in rows] == [Difference.AMBIGUOUS]
    assert rows[0].candidate_count == 2
    assert rows[0].recorded_slice == "x" * 20


def test_two_recorded_entries_cannot_share_one_material() -> None:
    """A material cannot be two things, so a double claim is ambiguous, not a match."""

    rows = align(
        (entry(entry_id="en_1", span=(0, 12)), entry(entry_id="en_2", span=(6, 18))),
        (material(span=(0, 18)),),
    )
    assert [row.difference for row in rows] == [Difference.AMBIGUOUS, Difference.AMBIGUOUS]
    assert {row.entry_id for row in rows} == {"en_1", "en_2"}


def test_overlap_is_measured_on_the_shorter_span_at_the_stated_threshold() -> None:
    assert OVERLAP_THRESHOLD == 0.5
    # exactly half of the shorter span
    rows = align((entry(span=(0, 10)),), (material(span=(5, 15)),))
    assert rows[0].difference is Difference.SAME
    # one character less than half
    rows = align((entry(span=(0, 10)),), (material(span=(6, 16)),))
    assert rows[0].difference is Difference.MISSING


def test_a_kind_that_differs_is_never_aligned() -> None:
    rows = align((entry(kind="memory_care_act"),), (material(kind="relationship_status"),))
    assert rows[0].difference is Difference.MISSING


def test_an_empty_span_matches_only_the_same_position() -> None:
    rows = align((entry(span=(4, 4)),), (material(span=(4, 4)),))
    assert rows[0].difference is Difference.SAME
    rows = align((entry(span=(4, 4)),), (material(span=(9, 9)),))
    assert rows[0].difference is Difference.MISSING


# --------------------------------------------------------------- the whole input ---
def test_the_reread_asks_the_engine_exactly_once_for_the_whole_input() -> None:
    class Spy:
        def __init__(self) -> None:
            self.seen: list[str] = []
            self.inner = NedAnalyzer()

        def analyze_text(self, text: str):
            self.seen.append(text)
            return self.inner.analyze_text(text)

    spy = Spy()
    case_file = RecordedCaseFile(
        case_file_id="cf_1",
        input_text="她记得我生日，但她说我们只是朋友",
        generated_at="2026-08-03T00:00:00Z",
        engine_name="ned-local-rules",
        engine_version="0.1.10",
        rules_version="0.1.0",
        rules_fingerprint=rules_fingerprint(),
        recognition="material_registered",
        verdict_code="ned.no_signal",
        verdict_text="x",
        signal_type="none",
    )
    reread_case_file(
        casebook_id="cb_x",
        casebook_label="小 X",
        case_file=case_file,
        entries=(),
        engine=spy,
        rules_version="0.1.0",
        rules_fingerprint=rules_fingerprint(),
    )
    assert spy.seen == [case_file.input_text]


def test_the_alignment_never_uses_material_id() -> None:
    source = (Path(__file__).resolve().parents[1] / "ned/app/review/reread.py").read_text(
        encoding="utf-8"
    )
    # the prose may name it (it explains why it is not used); no code may read one
    assert ".material_id" not in source
    assert "material_id=" not in source
    # and the recorded entry type does not even carry one
    import dataclasses

    assert "material_id" not in {field.name for field in dataclasses.fields(RecordedEntry)}


def test_a_reread_of_the_same_version_is_identical() -> None:
    analyzer = NedAnalyzer()
    text = "她记得我生日，但她说我们只是朋友"
    result = analyzer.analyze_text(text)
    snapshot = build_case_file_snapshot(result, book=analyzer.book, fingerprint=rules_fingerprint())
    entries = tuple(
        RecordedEntry(
            entry_id=f"en_{index}",
            entry_kind=item.entry_kind,
            material_index=item.material_index,
            material_kind=item.material_kind,
            reported_content=item.reported_content,
            start_offset=item.start_offset,
            end_offset=item.end_offset,
            polarity=str(item.polarity),
            epistemic_status=str(item.epistemic_status),
            proposition_owner=item.proposition_owner,
            reporter_role=item.reporter_role,
            target=item.target,
            origin_rule_id=item.origin_rule_id,
        )
        for index, item in enumerate(snapshot.materials)
    )
    case_file = RecordedCaseFile(
        case_file_id="cf_1",
        input_text=text,
        generated_at=str(snapshot.generated_at),
        engine_name=snapshot.engine_name,
        engine_version=snapshot.engine_version,
        rules_version=analyzer.book.version,
        rules_fingerprint=rules_fingerprint(),
        recognition=str(snapshot.recognition),
        verdict_code=snapshot.verdict_code,
        verdict_text=snapshot.verdict_text,
        signal_type=str(snapshot.signal_type),
    )
    outcome = reread_case_file(
        casebook_id="cb_x",
        casebook_label="小 X",
        case_file=case_file,
        entries=entries,
        engine=analyzer,
        rules_version=analyzer.book.version,
        rules_fingerprint=rules_fingerprint(),
    )
    assert outcome.identical is True
    assert outcome.note_code == "identical_to_recorded"
    assert outcome.counts.same == len(entries) == 2
    assert outcome.rules_differ_from_archive is False


# ------------------------------------------------------------- cross-version ---
@pytest.fixture
def old_pack(workdir: Path) -> Path:
    """A controlled older rule pack: one rename, one dropped pattern, one added, one polarity."""

    target = workdir / "rules"
    shutil.copytree(RULES, target)
    payload = json.loads((target / "events.json").read_text(encoding="utf-8"))
    for rule in payload["rules"]:
        if rule["id"] == "zh.event.reported_dismissal":
            rule["id"] = "zh.event.reported_dismissal_v0"
        elif rule["id"] == "zh.event.memory_act":
            rule["patterns"] = [p for p in rule["patterns"] if "生日" not in p]
        elif rule["id"] == "zh.event.contact_removed":
            rule["patterns"] = [*rule["patterns"], "(她|他|对方)给我留了(宵夜|水果)"]
        elif rule["id"] == "zh.event.friends_only_declared":
            rule["polarity"] = "neutral"
    (target / "events.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return target


def archive_from(text: str, book: RuleBook) -> tuple[RecordedCaseFile, tuple[RecordedEntry, ...]]:
    analyzer = NedAnalyzer(book=book)
    result = analyzer.analyze_text(text)
    snapshot = build_case_file_snapshot(
        result, book=book, fingerprint=rules_fingerprint(book.source_dir)
    )
    entries = tuple(
        RecordedEntry(
            entry_id=f"en_{index}",
            entry_kind=item.entry_kind,
            material_index=item.material_index,
            material_kind=item.material_kind,
            reported_content=item.reported_content,
            start_offset=item.start_offset,
            end_offset=item.end_offset,
            polarity=str(item.polarity),
            epistemic_status=str(item.epistemic_status),
            proposition_owner=item.proposition_owner,
            reporter_role=item.reporter_role,
            target=item.target,
            origin_rule_id=item.origin_rule_id,
        )
        for index, item in enumerate(snapshot.materials)
    )
    case_file = RecordedCaseFile(
        case_file_id="cf_old",
        input_text=snapshot.input_text,
        generated_at=str(snapshot.generated_at),
        engine_name=snapshot.engine_name,
        engine_version=snapshot.engine_version,
        rules_version=book.version,
        rules_fingerprint=rules_fingerprint(book.source_dir),
        recognition=str(snapshot.recognition),
        verdict_code=snapshot.verdict_code,
        verdict_text=snapshot.verdict_text,
        signal_type=str(snapshot.signal_type),
    )
    return case_file, entries


def reread_against(text: str, old_book: RuleBook):
    today = NedAnalyzer()
    case_file, entries = archive_from(text, old_book)
    return reread_case_file(
        casebook_id="cb_x",
        casebook_label="小 X",
        case_file=case_file,
        entries=entries,
        engine=today,
        rules_version=today.book.version,
        rules_fingerprint=rules_fingerprint(),
    )


def test_cross_version_produces_the_classes_the_audit_could_not_measure(old_pack: Path) -> None:
    """A controlled older pack: same, changed, missing and new all really happen."""

    old_book = RuleBook.load(old_pack)

    same = reread_against("我们分手了", old_book)
    assert same.counts.same == 1 and same.counts.changed == 0
    assert same.rules_differ_from_archive is True

    renamed = reread_against("她说我想多了", old_book)
    assert renamed.counts.same == 1 and renamed.counts.rule_id_only == 1

    changed = reread_against("她记得我生日，但她说我们只是朋友", old_book)
    assert changed.counts.changed == 1
    changed_row = next(row for row in changed.alignment if row.difference is Difference.CHANGED)
    assert "polarity" in changed_row.changed_fields

    new = reread_against("她记得我生日，但她说我们只是朋友", old_book)
    assert new.counts.new == 1
    assert any(row.difference is Difference.NEW for row in new.alignment)

    missing = reread_against("她给我留了宵夜", old_book)
    assert missing.counts.missing == 1
    assert missing.case_level_changed == ["recognition"]


def test_the_synthetic_ambiguous_fixture_is_labelled_as_synthetic() -> None:
    """No shipped corpus produces this, so it is constructed - and said to be constructed."""

    rows = align(
        (entry(span=(0, 20), content="x" * 20),),
        (material(span=(0, 12), content="x" * 12), material(span=(10, 20), content="x" * 10)),
    )
    assert [row.difference for row in rows] == [Difference.AMBIGUOUS]
