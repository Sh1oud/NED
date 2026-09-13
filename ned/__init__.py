"""NED - Nov1ce Evidence Denier.

An offline, satirical "emotional evidence de-weighting engine".

The public Python surface is deliberately small; most people should use the
CLI (``ned``) or the REST API (``ned serve``).
"""

from __future__ import annotations

from ned.app.version import FULL_NAME, TAGLINE, __version__

__all__ = ["FULL_NAME", "TAGLINE", "__version__"]
