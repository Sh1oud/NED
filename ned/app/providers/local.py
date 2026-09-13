"""The offline rule-based provider (the only one that runs in v0.1)."""

from __future__ import annotations

from ned.app.core.models import AlternativeExplanation
from ned.app.core.rules import RuleBook
from ned.app.core.theories import SemanticEscapeModule
from ned.app.providers.base import ExplanationContext, register_provider


class LocalRuleProvider:
    """Generates alternative explanations from the JSON escape ladder.

    Deterministic, offline, and inspectable: every hypothesis it emits carries
    the ``rule_id`` of the rule that produced it.
    """

    name = "local-rule"
    kind = "local-rule"
    offline = True

    def __init__(self, book: RuleBook) -> None:
        self.book = book
        self.escapes = SemanticEscapeModule(book)

    def explain(self, context: ExplanationContext) -> list[AlternativeExplanation]:
        return self.escapes.generate(
            text=context.text,
            mass=context.positive_mass,
            mode_id=context.mode,
            language=context.language,
            capacity=context.escape_capacity,
            limit=context.limit,
            signal_type=context.signal_type,
        )


register_provider("local", LocalRuleProvider)

__all__ = ["LocalRuleProvider"]
