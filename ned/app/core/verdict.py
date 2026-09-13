"""The verdict engine.

Verdicts are matched, not written in code: :mod:`ned.app.rules.verdicts.json`
holds an ordered table of rules, each with a small declarative ``when``
predicate over the computed metrics. Adding a new verdict is a JSON pull
request.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from ned.app.core.models import Verdict
from ned.app.core.rules import RuleBook, VerdictRule, format_template, resolve_verdict_text

_OPERATORS = {
    "gte": lambda actual, bound: actual >= bound,
    "lte": lambda actual, bound: actual <= bound,
    "gt": lambda actual, bound: actual > bound,
    "lt": lambda actual, bound: actual < bound,
    "eq": lambda actual, bound: actual == bound,
    "ne": lambda actual, bound: actual != bound,
}


def _normalise(value: Any) -> Any:
    """Unwrap enums so comparisons work with plain strings."""

    if isinstance(value, Enum):
        return value.value
    return value


def _compare(operator: str, actual: Any, bound: Any) -> bool:
    compare = _OPERATORS.get(operator)
    if compare is None:
        return False
    if operator in ("eq", "ne"):
        left, right = _normalise(actual), _normalise(bound)
        result = left == right
        return result if operator == "eq" else not result
    try:
        left = float(actual)
        right = float(bound)
    except (TypeError, ValueError):
        return False
    return bool(compare(left, right))


def matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    """Evaluate a declarative condition against a flat analysis context."""

    for key, expected in condition.items():
        if key not in context:
            return False
        actual = context[key]
        if isinstance(expected, dict):
            for operator, bound in expected.items():
                if not _compare(operator, actual, bound):
                    return False
        elif isinstance(expected, list):
            allowed = {_normalise(item) for item in expected}
            if _normalise(actual) not in allowed:
                return False
        elif isinstance(expected, bool):
            if bool(actual) is not expected:
                return False
        elif _normalise(actual) != _normalise(expected):
            return False
    return True


class VerdictEngine:
    """Turns metrics into the one thing users actually read."""

    def __init__(self, book: RuleBook) -> None:
        self.book = book

    def decide(self, context: dict[str, Any]) -> Verdict:
        """Return the first matching verdict rule."""

        mode = str(_normalise(context.get("mode", "normal")))
        language = str(_normalise(context.get("language", "en")))
        for rule in self.book.verdicts:
            if mode not in [str(item) for item in rule.modes]:
                continue
            if not matches(rule.when, context):
                continue
            return self._render(rule, language, mode, context)
        return Verdict(
            code="ned.undefined",
            text=format_template(
                self.book.escape_messages.get("capacity_exhausted", "证据不足。👍"), context
            ),
            severity="info",
            emoji="👍",
            rule_id="fallback",
        )

    @staticmethod
    def _render(rule: VerdictRule, language: str, mode: str, context: dict[str, Any]) -> Verdict:
        return Verdict(
            code=rule.id,
            text=resolve_verdict_text(rule.texts, language, mode, context),
            severity=rule.severity,
            emoji=rule.emoji,
            rule_id=rule.id,
        )

    def fnbp_verdict(self, key: str, language: str, values: dict[str, Any]) -> Verdict:
        """Verdict for the FNBP lab module (rules live in the same pack)."""

        spec = self.book.fnbp.get(key) or self.book.fnbp.get("degraded")
        if spec is None:
            return Verdict(
                code="fnbp.unknown", text="怎么又不是她效应", severity="chaos", emoji="💥"
            )
        return Verdict(
            code=spec.code,
            text=format_template(spec.texts.get(language) or spec.texts.get("default", ""), values),
            severity=spec.severity,
            emoji=spec.emoji,
            rule_id=f"fnbp.{key}",
        )


__all__ = ["VerdictEngine", "matches"]
