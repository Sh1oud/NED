"""A fingerprint of the rule pack that produced an archived reading.

``RuleBook.version`` only mirrors ``signals.json`` (``ned/app/core/rules.py``), so an edit to the
material, event or verdict packs is invisible in every version channel the product exposes today.
An archived entry has to be able to say *which* rules read it, so the store keeps a hash of the
whole pack directory instead of trusting a version string.

This is a read of shipped data only: no network, no clock, no state.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ned.app.config import rules_dir

#: Files that take part in the fingerprint. Rule packs are the only inputs to a reading.
PACK_SUFFIX = ".json"


def rules_fingerprint(directory: Path | None = None) -> str:
    """``sha256`` over every rule pack, in file-name order.

    The file name is hashed together with its bytes, so renaming a pack changes the fingerprint
    even when the content is identical - the pack a reading came from is part of the provenance.
    """

    base = Path(directory) if directory is not None else rules_dir()
    digest = hashlib.sha256()
    packs = sorted(path for path in base.glob("*" + PACK_SUFFIX) if path.is_file())
    for pack in packs:
        digest.update(pack.name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(pack.read_bytes())
        digest.update(b"\x00")
    return "rp_" + digest.hexdigest()[:32]


__all__ = ["PACK_SUFFIX", "rules_fingerprint"]
