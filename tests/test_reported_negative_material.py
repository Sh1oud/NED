"""PHASE 3.5B-2: the first material family and the coupling correction.

A report is not a conclusion. "她说讨厌我" is material - the input reports her attitude.
"我觉得她讨厌我" is still the reader's own conclusion and stays evidence. The material
layer reads the input itself: nothing here becomes an EvidenceSpan, adds a boundary or
carries a weight. Freeze both halves of that sentence; either half alone is a bug.
"""

from __future__ import annotations

import pytest
from ned.app.core import material
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import AnalysisResult, ObservedMaterial
from ned.app.core.parser import detect
from ned.app.core.rules import RuleBook

BOOK = RuleBook.load()
ANALYZER = NedAnalyzer(book=BOOK)

AS2_POSITIVES = (
    "她说讨厌我",
    "她明确说讨厌我",
    "她跟我说她讨厌我",
    "她说她不喜欢我",
    "她告诉我她很烦我",
)

HARD_NEGATIVES = (
    # the reader, or nobody, authors the proposition
    "我讨厌她",
    "她觉得她讨厌我",
    # uncertainty is not a report
    "她可能讨厌我",
    "她是不是讨厌我",
    "她可能会说讨厌我",
    "她是不是说讨厌我",
    # a named third party is not the described person
    "朋友说她讨厌我",
    "她妈妈说她讨厌我",
    "她妈妈觉得她讨厌我",
    "同学告诉我她讨厌我",
    # owner conflict: her frame, somebody else's proposition
    "她说他讨厌我",
    # the reader is the target, not the author
    "她说我讨厌她",
    "她说“我讨厌她”",
    # the reported attitude is negated, or only possible
    "她说她不讨厌我",
    "她说不是讨厌我",
    "她说她没有讨厌我",
    "她说她可能讨厌我",
)


def _ids(text: str) -> list[str]:
    return [span.rule_id for span in detect(text, BOOK)]


def _materials(text: str) -> list[ObservedMaterial]:
    return ANALYZER.analyze_text(text, mode="normal").materials


@pytest.mark.parametrize("text", AS2_POSITIVES)
def test_a_reported_negative_attitude_is_material(text: str) -> None:
    records = _materials(text)
    assert len(records) == 1, text
    record = records[0]
    assert record.material_kind == "reported_negative_interpersonal"
    assert record.polarity == "negative"
    assert record.source_kind == "attributed_report"
    assert record.epistemic_status == "reported"
    assert record.reporter_role == "described_person"
    assert record.proposition_owner == "described_person"
    assert record.target == "reader"
    assert record.origin_rule_id == "zh.material.reported_negative_attitude"
    assert record.reported_content
    assert text[record.start : record.end] == record.reported_content


@pytest.mark.parametrize("text", HARD_NEGATIVES)
def test_a_hard_negative_is_not_material(text: str) -> None:
    assert _materials(text) == [], text


@pytest.mark.parametrize("text", AS2_POSITIVES + HARD_NEGATIVES)
def test_material_never_enters_the_evidence_pipeline(text: str) -> None:
    result = ANALYZER.analyze_text(text, mode="normal")
    assert [span.rule_id for span in result.evidence] == _ids(text)
    assert not [span.rule_id for span in result.evidence if span.rule_id.startswith("zh.material.")]


def test_a_reader_conclusion_stays_a_reader_conclusion() -> None:
    """A: reported vs reader conclusion."""

    assert _materials("我觉得她讨厌我") == []
    assert "zh.self_negative_belief" in _ids("我觉得她讨厌我")
    assert "zh.self_negative_belief" not in _ids("她说讨厌我")
    assert _materials("她说讨厌我")


def test_an_owner_conflict_is_a_relay_not_a_material() -> None:
    """B: aligned owner vs owner conflict."""

    assert _materials("她跟我说她讨厌我")
    assert _materials("她跟我说他讨厌我") == []


def test_a_named_reporter_is_a_relay_not_a_material() -> None:
    """C: attributed vs relay."""

    assert _materials("她说她不喜欢我")
    assert _materials("朋友说她不喜欢我") == []


def test_an_uncertain_frame_is_not_a_report() -> None:
    """D: certain vs uncertain."""

    assert _materials("她说讨厌我")
    assert _materials("她可能会说讨厌我") == []


def test_a_negated_attitude_is_not_the_attitude() -> None:
    """E: negative vs negated negative."""

    reported = _materials("她说她讨厌我")
    assert reported and reported[0].polarity == "negative"
    assert _materials("她说她不讨厌我") == []


def test_material_does_not_become_a_boundary_or_a_verdict() -> None:
    """F: material is not a verdict, and it does not move the existing ones."""

    for text in AS2_POSITIVES:
        result = ANALYZER.analyze_text(text, mode="normal")
        assert result.materials
        assert "zh.direct_rejection" not in _ids(text)
        assert result.verdict.code
    boundary = ANALYZER.analyze_text("她说不要再联系我", mode="normal")
    assert "zh.direct_rejection" in _ids("她说不要再联系我")
    assert boundary.verdict.code == "ned.direct_rejection"
    # PR-2 registers the stated no-contact shape in the contact/access family, so that
    # "别再联系我了" and "不想联系我了" are heard the same way. A material record is not
    # evidence: the boundary verdict above is untouched, and the material stays material.
    assert boundary.materials
    assert all(item.origin_rule_id.startswith("zh.event.") for item in boundary.materials)
    assert [span.rule_id for span in boundary.evidence] == ["zh.direct_rejection"]


def test_the_coupling_shape_registers_material() -> None:
    """MATERIAL-COUPLING-CORE-1: the material half holds, the evidence half does not.

    The reported proposition is registered as material. The ownership firewall still files
    the same trigger as the reader's own conclusion, and that half cannot be closed from
    the rule pack: any pack-level guard for it also swallows the pinned reader conclusion
    "我和她说她不喜欢我". It needs a firewall change, which is its own order.
    """

    text = "她跟我说她讨厌我"
    result = ANALYZER.analyze_text(text, mode="normal")
    assert len(result.materials) == 1
    assert result.materials[0].reported_content == "她讨厌我"


def test_inline_whitespace_has_no_vote_in_the_material_layer() -> None:
    for text in ("她跟我说她讨厌我", "她跟我说她 讨厌我", "她跟我说 她讨厌我"):
        assert len(_materials(text)) == 1, text


def test_the_readers_own_frame_is_not_a_report() -> None:
    """The reader speaks this frame: the words are the reader's, not a report about her."""

    assert _materials("我跟她说她讨厌我") == []


def test_material_ids_are_stable_and_book_driven() -> None:
    first = _materials("她说讨厌我")
    second = _materials("她说讨厌我")
    assert first and [item.material_id for item in first] == [item.material_id for item in second]
    assert material.register_materials("她说讨厌我") == []
    assert len(material.register_materials("她说讨厌我", book=BOOK)) == 1


def test_the_payload_gains_materials_only_for_a_material_input() -> None:
    quiet = ANALYZER.analyze_text("她主动找我聊天了", mode="normal")
    assert isinstance(quiet, AnalysisResult)
    assert "materials" not in quiet.model_dump()
    loud = ANALYZER.analyze_text("她说讨厌我", mode="normal")
    payload = loud.model_dump()["materials"][0]
    assert payload["material_kind"] == "reported_negative_interpersonal"
    assert set(payload) == set(ObservedMaterial.model_fields)
