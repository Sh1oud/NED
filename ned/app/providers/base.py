"""Provider protocol and registry.

A provider turns a parsed analysis context into a list of alternative
explanations. Implementations must be offline-safe by default and must never
present their output as fact.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ned.app.core.models import AlternativeExplanation, Mode, SignalType
from ned.app.core.rules import RuleBook


class ProviderUnavailableError(RuntimeError):
    """Raised when a provider is configured but cannot run in this build."""


class ExplanationContext(BaseModel):
    """Everything a provider needs, and nothing it should not have.

    Note what is *absent*: no identity, no conversation history beyond the
    strength summary, no storage handle. Providers get the text they were asked
    about and the numbers NED computed.
    """

    model_config = ConfigDict(extra="forbid")

    text: str
    language: str
    mode: Mode
    positive_mass: float = Field(ge=0, le=100)
    signal_type: SignalType = SignalType.NONE
    signal_label: str = ""
    escape_capacity: float = Field(default=0.0, ge=0, le=1)
    limit: int = Field(default=3, ge=1, le=10)


@runtime_checkable
class ExplanationProvider(Protocol):
    """Structural type every explanation provider must satisfy."""

    name: str
    kind: str
    offline: bool

    def explain(self, context: ExplanationContext) -> list[AlternativeExplanation]:
        """Return alternative explanations, best first."""
        ...


PROVIDERS: dict[str, type[object]] = {}


def register_provider(key: str, provider_cls: type[object]) -> None:
    """Register a provider class under ``key``."""

    PROVIDERS[key] = provider_cls


def available_providers() -> list[str]:
    """Keys of every registered provider."""

    return sorted(PROVIDERS)


def get_provider(key: str, book: RuleBook) -> ExplanationProvider:
    """Instantiate a registered provider."""

    if key not in PROVIDERS:
        raise KeyError(f"unknown provider: {key!r} (available: {', '.join(available_providers())})")
    provider_cls = PROVIDERS[key]
    return provider_cls(book)  # type: ignore[call-arg,return-value]


__all__ = [
    "PROVIDERS",
    "ExplanationContext",
    "ExplanationProvider",
    "ProviderUnavailableError",
    "available_providers",
    "get_provider",
    "register_provider",
]
