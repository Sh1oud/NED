"""FRONT DESK RENEWAL-5: responsive and accessibility contract for the hall.

These pins protect real contracts rather than an implementation: the responsive
tiers exist, the front-desk chrome never smuggles copy into CSS, motion stays under
the user's reduced-motion preference, and the serious/normal distinction is never
carried by colour alone.
"""

from __future__ import annotations

import re
from pathlib import Path

import ned.app.ui.personality as p

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "ned" / "app" / "static" / "style.css").read_text(encoding="utf-8")

TIERS = (900, 720, 460, 380)


def _front_desk_css() -> str:
    """The front-desk sections of the stylesheet, concatenated."""

    parts = re.split(r"/\* -+ front desk:", CSS)
    return "".join(parts[1:]) if len(parts) > 1 else ""


def test_the_responsive_tiers_exist() -> None:
    for tier in TIERS:
        assert f"@media (max-width: {tier}px)" in CSS, tier


def test_the_front_desk_never_smuggles_copy_into_css() -> None:
    front_desk = _front_desk_css()
    assert front_desk, "the front-desk sections are missing"
    offenders = re.findall(r'content:\s*"[^"]+"', front_desk)
    assert not offenders, offenders


def test_motion_stays_under_the_user_preference() -> None:
    assert "prefers-reduced-motion" in CSS
    # the reduced-motion block itself names the animation properties, so it is
    # removed before asking whether the front desk *forces* motion
    front_desk = re.sub(r"@media \(prefers-reduced-motion[^{]*\{[^}]*\}", "", _front_desk_css())
    assert not re.search(r"animation:\s*(?!none)", front_desk), front_desk[-200:]


def test_the_tap_target_floor_and_hint_survive() -> None:
    front_desk = _front_desk_css()
    assert "min-height: 44px" in front_desk
    assert ".hint" in CSS


def test_seriousness_is_never_carried_by_colour_alone() -> None:
    """The boundary screens say so in words; the register only agrees with them."""

    for mode in ("normal", "extreme", "scientific"):
        boundary = p.first_screen(p.SITUATION_BOUNDARY, mode, "zh").title
        positive = p.first_screen(p.SITUATION_POSITIVE, mode, "zh").title
        assert boundary and positive and boundary != positive, mode
    assert 'data-situation="boundary"' in CSS
