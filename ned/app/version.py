"""Single source of truth for NED's identity and version.

Nothing else in the project may hardcode a version string: ``pyproject.toml``
reads ``__version__`` from this module, and the API, the CLI and the web UI all
read it from here too.
"""

from __future__ import annotations

__version__ = "0.1.9"

#: Bumped only when the REST contract changes in a breaking way.
API_VERSION = "1"

NAME = "NED"
FULL_NAME = "Nov1ce Evidence Denier"
TAGLINE = "When reality becomes suspiciously positive, NED restores uncertainty."
MOTTO = "Everything may be affection. Everything may also be 人好. 👍"
SUBTITLE = "Systematically explaining away good news since 2026."

#: The engine identifier reported by ``/api/health`` and by every analysis.
ENGINE_NAME = "ned-local-rules"

DISCLAIMER = (
    "NED cannot determine whether someone likes you. Humans are not APIs. "
    "No amount of text analysis can replace direct communication and context. "
    "Every alternative explanation below is generated satire, not a psychological finding."
)

PRIVACY_NOTE = "Local-first. Your messages stay on your machine."

__all__ = [
    "API_VERSION",
    "DISCLAIMER",
    "ENGINE_NAME",
    "FULL_NAME",
    "MOTTO",
    "NAME",
    "PRIVACY_NOTE",
    "SUBTITLE",
    "TAGLINE",
    "__version__",
]
