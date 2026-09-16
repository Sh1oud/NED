"""PHASE 3.5B-1: the observed-material primitive contract.

A material record says what the input reports. It never says what is true, never carries a
weight and never becomes a verdict - and the registry is empty until a material family
exists, so every existing input keeps its behaviour.
"""

from __future__ import annotations

import pydantic
import pytest
from ned.app.core import material
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import AnalysisResult, ObservedMaterial
from ned.app.core.parser import detect
from ned.app.core.rules import RuleBook

BOOK = RuleBook.load()
ANALYZER = NedAnalyzer(book=BOOK)

SAMPLE = (
    "她主动找我聊天了",
    "她三天没回我消息了",
    "她说她不想谈恋爱",
    "我觉得她不喜欢我",
    "让我滚",
    "朋友说她讨厌我",
    "她可能讨厌我",
    "今天天气不错",
)


def test_verified_is_not_constructible() -> None:
    """The type system refuses VERIFIED: a report can never be promoted into reality."""

    with pytest.raises(pydantic.ValidationError):
        ObservedMaterial(
            material_id="x",
            material_kind="reported_negative_interpersonal",
            reported_content="讨厌我",
            epistemic_status="verified",  # type: ignore[arg-type]
        )


def test_source_kind_is_separate_from_epistemic_status() -> None:
    record = ObservedMaterial(
        material_id="x",
        material_kind="reported_negative_interpersonal",
        reported_content="讨厌我",
        source_kind="attributed_report",
    )
    assert record.source_kind == "attributed_report"
    assert record.epistemic_status == "reported"
    with pytest.raises(pydantic.ValidationError):
        ObservedMaterial(
            material_id="x",
            material_kind="k",
            reported_content="c",
            source_kind="verified",  # type: ignore[arg-type]
        )


def test_a_material_has_no_qualification_weight_or_verdict() -> None:
    fields = set(ObservedMaterial.model_fields)
    for forbidden in (
        "qualification_status",
        "weight",
        "strength",
        "confidence",
        "probability",
        "support_score",
        "verdict",
        "verdict_hint",
        "verified",
        "relationship_score",
    ):
        assert forbidden not in fields, forbidden
    assert "epistemic_status" in fields and "source_kind" in fields


def test_the_registry_is_empty_at_this_stage() -> None:
    assert material.register_materials("她说讨厌我") == []
    assert material.register_materials("她主动找我聊天了", book=BOOK) == []


def test_material_ids_are_deterministic() -> None:
    first = material.material_id("k", 3, 6, "zh.example")
    second = material.material_id("k", 3, 6, "zh.example")
    assert first == second
    assert first.startswith("mat_")
    assert first != material.material_id("k", 4, 6, "zh.example")


def test_an_empty_material_list_travels_safely() -> None:
    result = ANALYZER.analyze_text("她主动找我聊天了", mode="normal")
    assert isinstance(result, AnalysisResult)
    assert result.materials == []
    assert "materials" not in result.model_dump()


def test_an_empty_material_list_does_not_change_existing_behaviour() -> None:
    for text in SAMPLE:
        result = ANALYZER.analyze_text(text, mode="normal")
        assert result.materials == []
        assert result.verdict.code
        assert result.material_aspects is None or result.material_aspects.materials
        assert [span.rule_id for span in result.evidence] == [
            span.rule_id for span in detect(text, BOOK)
        ]
