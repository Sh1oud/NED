"""Explanation providers.

NED's alternative explanations come from a *provider*, so the rule engine is
not the only possible source. v0.1 ships one working provider (the offline rule
engine) and one deliberately unimplemented stub for a future LLM provider, so
that the interface is proven to be pluggable without shipping any network code.
"""

from __future__ import annotations

from ned.app.providers.base import (
    PROVIDERS,
    ExplanationContext,
    ExplanationProvider,
    available_providers,
    get_provider,
    register_provider,
)
from ned.app.providers.llm import LLMProvider, ProviderUnavailableError
from ned.app.providers.local import LocalRuleProvider

__all__ = [
    "PROVIDERS",
    "ExplanationContext",
    "ExplanationProvider",
    "LLMProvider",
    "LocalRuleProvider",
    "ProviderUnavailableError",
    "available_providers",
    "get_provider",
    "register_provider",
]
