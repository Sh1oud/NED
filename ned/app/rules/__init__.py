"""JSON rule packs.

Every judgement NED makes is data. Override the whole directory with the
``NED_RULES_DIR`` environment variable to run NED with your own beliefs.
"""

from __future__ import annotations

from pathlib import Path

RULES_DIR = Path(__file__).resolve().parent

__all__ = ["RULES_DIR"]
