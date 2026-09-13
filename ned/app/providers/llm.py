"""Declared-but-unimplemented LLM provider.

NED v0.1 never calls a remote model. This class exists so the provider interface
is exercised by a second implementation and so a future contributor has an
obvious place to plug one in — behind an opt-in flag, with a privacy warning,
and without changing the API contract.

It deliberately raises rather than pretending to work: an unavailable provider
must fail loudly, never quietly return filler.
"""

from __future__ import annotations

from ned.app.core.models import AlternativeExplanation
from ned.app.core.rules import RuleBook
from ned.app.providers.base import (
    ExplanationContext,
    ProviderUnavailableError,
    register_provider,
)


class LLMProvider:
    """Not implemented in v0.1. Kept honest by raising."""

    name = "llm"
    kind = "llm"
    offline = False

    def __init__(self, book: RuleBook) -> None:
        self.book = book

    def explain(self, context: ExplanationContext) -> list[AlternativeExplanation]:
        raise ProviderUnavailableError(
            "The LLM provider is not implemented in NED v0.1. NED is local-first: "
            "no text is ever sent to a third party. To experiment locally, implement "
            "LLMProvider.explain() in ned/app/providers/llm.py and register it with "
            "--provider llm; keep it opt-in and document the privacy change."
        )


register_provider("llm", LLMProvider)

__all__ = ["LLMProvider"]
