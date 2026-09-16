"""PHASE 3.5B-2C-3A: which report acts the first material rule may register.

``report_event`` answers what happened - who spoke, what was said, whether the report was
asserted at all - and it deliberately accepts far more report acts than a material rule is
allowed to register. 承认, 表示, 解释, 回复, 回答, 讲, 称, 答, 问, 提, 通知 and 告知 are all
structurally valid, asserted reports, and this material layer still refuses every one of them.

That refusal is not a grammar accident: it is the rule's own decision, taken in one place
from one field, ``allowed_report_heads``. Freeze both halves. If the shared resolver ever
stops resolving these heads, the first half breaks; if the material layer ever starts
registering them without a new and explicit approval, the second half breaks.
"""

from __future__ import annotations

import pytest
from ned.app.core import boundary, material, report_event
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import ObservedMaterial
from ned.app.core.rules import RuleBook

BOOK = RuleBook.load()
ANALYZER = NedAnalyzer(book=BOOK)

#: The exact approved set. Widening it is a product decision, never a refactor.
ALLOWED_HEADS = ("说", "告诉", "嘀咕", "抱怨")

#: Every input here must keep registering exactly one material.
ELIGIBLE = (
    # the legacy AS-2 positives, whose frames normalize onto 说 / 告诉
    "她说讨厌我",
    "她说她讨厌我",
    "她明确说她讨厌我",
    "她跟我说她讨厌我",
    "她说她不喜欢我",
    "她告诉我她很烦我",
    "她告诉我她讨厌我",
    # a clause break and a delivery modifier are the frame's business, not the content's
    "她跟我说，她讨厌我",
    "她刚才说她讨厌我",
    "她跟我小声说她讨厌我",
    # the 3B directed message heads
    "她跟我嘀咕她讨厌我",
    "她跟我嘀咕 她讨厌我",
    "她跟我抱怨她讨厌我",
    "她跟我抱怨 她讨厌我",
)

#: (resolved head, input). The resolver must still resolve them; material must stay empty.
INELIGIBLE = (
    ("承认", "她承认她讨厌我"),
    ("表示", "她表示她讨厌我"),
    ("解释", "她解释她讨厌我"),
    ("回复", "她回复她讨厌我"),
    ("回答", "她回答她讨厌我"),
    ("讲", "她讲她讨厌我"),
    ("称", "她称她讨厌我"),
    ("答", "她答她讨厌我"),
    ("问", "她问她讨厌我"),
    ("提", "她提她讨厌我"),
    ("通知", "她通知我她讨厌我"),
    ("告知", "她告知我她讨厌我"),
)

REPORTED = "她讨厌我"


def _materials(text: str) -> list[ObservedMaterial]:
    return ANALYZER.analyze_text(text, mode="normal").materials


def _sentence(head: str) -> str:
    """One well-formed report for ``head``, shaped the way the resolver expects it."""

    if head in boundary.OBJECT_RECEIVER_VERBS:
        return f"她{head}我{REPORTED}"
    if head in boundary.DIRECTED_MESSAGE_HEADS:
        return f"她跟我{head}{REPORTED}"
    return f"她{head}{REPORTED}"


@pytest.mark.parametrize("text", ELIGIBLE)
def test_an_eligible_report_act_registers_material(text: str) -> None:
    records = _materials(text)
    assert len(records) == 1, text
    record = records[0]
    assert text[record.start : record.end] == record.reported_content
    resolved = report_event.resolve_report_event(text, record.start, record.end)
    assert resolved.frame.speech_verb in ALLOWED_HEADS, text


@pytest.mark.parametrize(("head", "text"), INELIGIBLE)
def test_an_ineligible_report_act_is_not_material(head: str, text: str) -> None:
    index = text.index(REPORTED)
    resolved = report_event.resolve_report_event(text, index, len(text))
    # Half one: this really is a structurally valid, asserted report by the described person.
    assert resolved.frame.speech_verb == head, text
    assert resolved.actuality == "ASSERTED", text
    assert resolved.proposition_owner == "她", text
    # Half two: and it is still refused, because this rule may not register that report act.
    assert _materials(text) == [], text


def test_only_the_approved_heads_are_ever_eligible() -> None:
    """Exhaustive over the resolver's own head vocabulary."""

    heads = (
        set(boundary.SIMPLE_SPEECH_VERBS)
        | set(boundary.OBJECT_RECEIVER_VERBS)
        | set(boundary.DIRECTED_MESSAGE_HEADS)
    )
    assert heads >= set(ALLOWED_HEADS)
    for head in sorted(heads):
        text = _sentence(head)
        got = len(_materials(text))
        if head in ALLOWED_HEADS:
            assert got == 1, (head, text)
        else:
            assert got == 0, (head, text)


def test_the_eligible_head_set_is_exactly_the_approved_one() -> None:
    rules = material.material_rules(BOOK)
    assert len(rules) == 1
    assert rules[0].allowed_report_heads == ALLOWED_HEADS


def test_the_heads_are_eligibility_and_never_content_vocabulary() -> None:
    """The heads gate the resolved report act; they are not stuffed back into the pattern."""

    rule = material.material_rules(BOOK)[0]
    pattern = material.compile_material_rule(rule).pattern
    for head in rule.allowed_report_heads:
        assert head not in pattern, head


def test_a_pack_without_the_eligibility_field_defaults_to_empty() -> None:
    """Fail closed at the schema: an older pack must not inherit the whole grammar."""

    payload = material.material_rules(BOOK)[0].model_dump()
    payload.pop("allowed_report_heads")
    assert material.MaterialRule.model_validate(payload).allowed_report_heads == ()


def test_a_rule_without_eligibility_registers_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail closed at recognition: the empty set refuses every report act."""

    rule = material.material_rules(BOOK)[0]
    unfenced = rule.model_copy(update={"allowed_report_heads": ()})
    monkeypatch.setattr(material, "material_rules", lambda book=None: (unfenced,))
    for text in ("她说她讨厌我", "她说讨厌我", "她告诉我她很烦我"):
        assert material.register_materials(text, book=BOOK) == [], text
    monkeypatch.undo()
    # The real pack still registers, so the guard above is about the field, not the input.
    assert material.register_materials("她说她讨厌我", book=BOOK)
