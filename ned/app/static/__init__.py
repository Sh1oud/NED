"""Static assets for the NED web UI (CSS and vanilla JavaScript only)."""

from __future__ import annotations

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent

__all__ = ["STATIC_DIR"]
