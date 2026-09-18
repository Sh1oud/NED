"""PR-6R2: the desk has an identity of its own, and it is still the same product.

The visual pass is CSS, so pytest cannot look at it - but the contract the stylesheet declares
can be frozen, and that is what these pins do:

* the palette is a warm ink desk, aged paper and one seal. The blue-black page and the teal
  accent are gone from it, and teal is a point colour only;
* every ink/surface pair the desk prints with clears 4.5:1, computed from the stylesheet's own
  declarations - including the archive's faint mono and the four inks the receipt may rule in;
* the surface hierarchy is real: the desk, the paper that is in the file and the archive are
  three different colours, and the archive is the darkest page on the screen;
* the identity layer is presentation only: no fixed or sticky positioning, no text in a
  pseudo-element, no id it cannot find in the template, and every PR-3/PR-4R behaviour contract
  (tap-target floors, the counter action's order, the rail's columns, the archive's fold) is
  still standing behind it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE = (ROOT / "ned" / "app" / "static" / "style.css").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "ned" / "app" / "templates" / "index.html").read_text(encoding="utf-8")

MARKER = "PR-6R2 — FRONT DESK IDENTITY"
IDENTITY = STYLE[STYLE.index(MARKER) :]

#: (ink, surface) pairs the desk really prints, and the floor every one of them must clear.
CONTRAST_PAIRS = (
    ("--text", "--ink-900"),
    ("--text-dim", "--ink-850"),
    ("--text-faint", "--ink-850"),
    ("--text-faint", "--ink-800"),
    ("--text-faint", "#231f19"),
    ("--text-dim", "#14110d"),
    ("--text-faint", "#14110d"),
    ("--paper-ink", "--paper-100"),
    ("--paper-ink", "--paper-200"),
    ("--paper-ink", "--paper-300"),
    ("--paper-faint", "--paper-100"),
    ("--paper-faint", "--paper-200"),
    ("--paper-faint", "--paper-300"),
    ("--paper-100", "--ink-800"),
    ("--paper-200", "--ink-800"),
    ("--seal-bright", "--ink-800"),
    ("--seal-bright", "--ink-850"),
    ("--steel", "--ink-800"),
    ("--accent-point", "--ink-850"),
    ("--seal", "--paper-100"),
    ("--seal-dim", "--paper-100"),
    ("--seal-dim", "--paper-200"),
    # the four inks a ruling may be printed in, on the receipt's shaded plate
    ("#255a6b", "--paper-200"),
    ("#255a6b", "--paper-300"),
    ("#6f450c", "--paper-200"),
    ("#6f450c", "--paper-300"),
    ("--seal-dim", "--paper-300"),
    ("#5e3f80", "--paper-200"),
    ("#5e3f80", "--paper-300"),
)

MIN_CONTRAST = 4.5


def root_values() -> dict[str, str]:
    block = re.search(r":root\s*\{(.*?)\}", STYLE, re.S)
    assert block is not None, "the stylesheet has no :root block"
    return dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", block.group(1)))


VALUES = root_values()


def resolve(name: str) -> str:
    value = VALUES[name].strip()
    alias = re.fullmatch(r"var\((--[a-z0-9-]+)\)", value)
    return resolve(alias.group(1)) if alias else value


def rgb(value: str) -> tuple[float, float, float]:
    hexed = re.search(r"#([0-9a-fA-F]{6})", value)
    if hexed:
        digits = hexed.group(1)
        return tuple(int(digits[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    parts = re.search(r"rgba?\(([^)]+)\)", value)
    assert parts is not None, value
    numbers = parts.group(1).split(",")
    return (float(numbers[0]), float(numbers[1]), float(numbers[2]))


def luminance(colour: tuple[float, float, float]) -> float:
    def channel(value: float) -> float:
        value = value / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(colour[0]) + 0.7152 * channel(colour[1]) + 0.0722 * channel(colour[2])


def contrast(ink: str, surface: str) -> float:
    a = luminance(rgb(ink if ink.startswith("#") else resolve(ink)))
    b = luminance(rgb(surface if surface.startswith("#") else resolve(surface)))
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


# --------------------------------------------------------------------------- #
# the palette: a warm ink desk, aged paper, one seal
# --------------------------------------------------------------------------- #


def test_the_palette_is_the_archive_desk_and_not_a_blue_black_tool() -> None:
    assert resolve("--bg") == "#17130f", "the page is warm charcoal, not blue-black"
    assert resolve("--ink-900") == "#17130f"
    assert resolve("--ink-950") == "#100d0b"
    assert resolve("--paper-100") == "#efe6d5"
    assert resolve("--paper-ink") == "#241d15"
    # the accent is a point colour and nothing more
    assert resolve("--accent") == "#4fb3a3"
    assert resolve("--accent-point") == "#4fb3a3"
    # neither the declared palette nor the identity layer carries the instrument colours
    declared = " ".join(VALUES.values())
    for gone in ("#0b0d10", "#5eead4", "#2dd4bf", "#7dd3fc", "#c084fc"):
        assert gone not in declared, gone
    for gone in ("#0b0d10", "#5eead4", "#2dd4bf", "#7dd3fc", "#c084fc", "#f87171"):
        assert gone not in IDENTITY, gone


def test_the_framework_variables_the_first_pass_dropped_are_declared_again() -> None:
    """``--max`` silently un-capped the page, ``--sev`` flattened every severity mark."""

    for name in ("--max", "--steel", "--info", "--chaos", "--sev", "--sev-reject"):
        assert name in VALUES, name
    assert resolve("--max") == "1100px"
    assert resolve("--sev") == resolve("--info")
    # nothing in the sheet uses a variable the sheet never declares
    used = set(re.findall(r"var\((--[a-z0-9-]+)", STYLE))
    assert not (used - set(VALUES)), sorted(used - set(VALUES))


def test_teal_is_a_point_colour_not_a_surface() -> None:
    """The rail's active stage and the focus ring may be teal; the identity layer floods nothing."""

    floods = re.findall(r"background[^;]*var\(--accent(?:-point)?\)[^;]*;", IDENTITY)
    assert not floods, floods


# --------------------------------------------------------------------------- #
# the ink: every printed pair clears 4.5:1
# --------------------------------------------------------------------------- #


def test_every_declared_ink_and_surface_pair_clears_aa() -> None:
    worst = min((contrast(ink, surface), ink, surface) for ink, surface in CONTRAST_PAIRS)
    assert worst[0] >= MIN_CONTRAST, "{} on {} is only {:.2f}:1".format(*worst)


# --------------------------------------------------------------------------- #
# the surfaces: three levels, and the archive is the darkest page
# --------------------------------------------------------------------------- #


def test_the_surface_hierarchy_is_real() -> None:
    desk = luminance(rgb(resolve("--ink-900")))
    raised = luminance(rgb(resolve("--ink-800")))
    paper = luminance(rgb(resolve("--paper-100")))
    shaded = luminance(rgb(resolve("--paper-200")))
    archive = luminance(rgb("#14110d"))
    assert desk < raised < paper, "the desk, its raised plates and paper are three levels"
    assert shaded < paper, "the file's paper has a shaded shade"
    assert archive < desk, "the archive is the coldest, darkest page on the screen"
    assert len({resolve("--ink-900"), resolve("--paper-100"), "#14110d"}) == 3


def test_each_zone_declares_its_own_surface() -> None:
    """Paper for what is in the file, the desk for annotations, ink for the receipt header."""

    for zone, surface in (
        ("#stage-block-submit .intake-card", "--paper-"),
        ("#material-registry", "--paper-"),
        ("#first-screen", "--paper-"),
        ("#issuance-card.card.verdict-card", "--paper-"),
        ("#final-verdict", "--paper-"),
        ("#technical-details", "--ink-950"),
    ):
        rule = re.search(re.escape(zone) + r"\s*\{(.*?)\}", IDENTITY, re.S)
        assert rule is not None, zone
        assert surface in rule.group(1), (zone, surface)
    # the marginalia stay on the desk, so the eye never loses the file
    marginalia = re.search(r"\.review-grid \.card\s*\{(.*?)\}", IDENTITY, re.S)
    assert marginalia is not None
    assert "var(--ink-850)" in marginalia.group(1)
    assert "paper" not in marginalia.group(1)


def test_a_stated_boundary_is_marked_by_the_seal_and_not_by_colour_alone() -> None:
    """Boundary keeps its own colder paper, a seal edge, and the state word it always had."""

    boundary = re.search(r'#first-screen\[data-situation="boundary"\]\s*\{(.*?)\}', IDENTITY, re.S)
    assert boundary is not None
    assert "var(--seal)" in boundary.group(1)
    assert "cold" in boundary.group(1) or "#eae4d5" in boundary.group(1)
    receipt = re.search(r'#analyze-results\[data-situation="boundary"\] #final-verdict', IDENTITY)
    assert receipt is not None
    # the state words themselves are the primary signal; colour only underlines them
    for word in ("已签", "未签", "边界", "材料在卷"):
        assert word in (ROOT / "ned" / "app" / "ui" / "personality.py").read_text(
            encoding="utf-8"
        ), word


# --------------------------------------------------------------------------- #
# presentation only: no behaviour, no position, no invented status
# --------------------------------------------------------------------------- #


def test_the_identity_layer_pins_nothing_to_the_viewport() -> None:
    assert "position: fixed" not in IDENTITY
    assert "position: sticky" not in IDENTITY


def test_no_pseudo_element_prints_a_status_of_its_own() -> None:
    contents = re.findall(r"content:\s*([^;]+);", IDENTITY)
    assert contents, "the identity layer draws its decoration with pseudo-elements"
    for content in contents:
        assert content.strip() in {'""', "''"}, content


def test_the_identity_layer_only_touches_ids_the_page_really_has() -> None:
    ids = set(re.findall(r'id="([^"]+)"', TEMPLATE))
    selectors = re.sub(r"#[0-9a-fA-F]{3,8}\b", "", IDENTITY)
    anchors = set(re.findall(r"#([a-z][a-z0-9-]+)", selectors))
    assert anchors, "the identity layer must be anchored to the page's own ids"
    for anchor in anchors:
        assert anchor in ids, anchor


def test_the_behaviour_contracts_are_still_standing() -> None:
    # the phone: the primary action stays reachable and keeps its tap floor
    assert "#analyze-submit { width: 100%; min-height: 48px; }" in STYLE
    assert "min-height: 48px" in IDENTITY or "min-height: 48px" in STYLE
    assert ".hall-directory .tab,\n  .btn,\n  .chip {\n    min-height: 44px;\n  }" in STYLE
    # the counter action keeps its place above the fold on a phone
    assert ".row-inline .field-actions {\n    order: -1;\n  }" in STYLE
    # the rail keeps its four columns, then two, then one
    assert (
        ".stage-rail {\n  display: grid;\n  grid-template-columns: repeat(4, minmax(0, 1fr));"
        in STYLE
    )
    assert ".stage-rail { grid-template-columns: repeat(2, minmax(0, 1fr)); }" in STYLE
    assert ".stage-rail { grid-template-columns: 1fr; gap: 6px; }" in STYLE
    # the registry's rows stack on a phone again, the identity layer's 96px rule notwithstanding
    stacked = re.search(
        r"@media \(max-width: 720px\) \{\n  /\* the registry's rows stack.*?"
        r"#material-registry \.audit-rows \{ grid-template-columns: minmax\(0, 1fr\); \}",
        IDENTITY,
        re.S,
    )
    assert stacked is not None, "the registry's mobile rows must still stack"
    # the archive still folds, and the seal sits square on a phone
    assert "#issuance-stamp { transform: none; }" in IDENTITY
    for width in (900, 720, 520, 460, 380):
        assert f"@media (max-width: {width}px)" in STYLE, width
    assert "prefers-reduced-motion" in STYLE
    # the masthead is the one display voice, and mono keeps to the file's numbers
    assert re.search(r"\.masthead-name \{\n  font-family: var\(--display\)", IDENTITY)
    assert re.search(r"#final-verdict \.verdict-text \{\n  font-family: var\(--display\)", IDENTITY)
    assert re.search(r"#technical-details \.label,", IDENTITY)
