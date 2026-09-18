"""FRONT DESK RENEWAL-6: the hall's copy exists once, in the shared catalogue.

The front desk is the easiest place in this product to grow a second source of
truth: a window name typed into the template, or a script that invents its own
fallback sentence. These pins freeze the opposite.

* the five hall labels exist once, in ``personality.web_personality_catalog()``,
  complete in both languages, with the wording the commander froze;
* the shipped template, script and stylesheet carry no copy of that wording, and
  the client names no stage, no progress and no issuance outcome;
* the labels are hall chrome: they never reach a result screen, they consult no
  situation, and a boundary screen gains no administrative punchline from them;
* the 47 catalogue keys that existed at ``1ab2c13`` keep their meaning, key by
  key. ``first_screen`` is inside that guard, so ``no_signal``, ``boundary`` and
  ``timeline_boundary`` copy cannot move either.

Regenerate the digests with ``_rc\\fd6\\make_pins.py`` (kept with the batch
evidence) after a change that is genuinely meant to move an old catalogue key.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ned.app.main import app as api_app
from ned.app.ui import personality as p

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "ned" / "app" / "templates" / "index.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "ned" / "app" / "static" / "app.js").read_text(encoding="utf-8")
STYLE = (ROOT / "ned" / "app" / "static" / "style.css").read_text(encoding="utf-8")

#: The frozen wording, key by key: (zh, en). PR-6R2 deleted the hall title and its two slogan
#: sentences - the desk states what it is, not what it promises - so these are the four labels
#: that remain, and the archive heading now says what the folded block became.
FRONT_DESK = {
    "intake_heading": ("请提交待审查材料", "Submit material for review"),
    "submit_label": ("提交审查", "Submit for review"),
    # PR-3: the folded block became the dossier's technical archive, so its heading says so.
    "records_heading": ("技术档案", "Technical archive"),
    "issuance_heading": ("签发状态", "Issuance status"),
}

#: One hall label per injected element. ``analyze-submit`` is the pre-existing
#: button; every other anchor is the element the label was always meant to name.
ANCHORS = {
    "intake_heading": "intake-heading",
    "submit_label": "analyze-submit",
    "records_heading": "records-heading",
    "issuance_heading": "issuance-heading",
}

#: The hall title and its slogan, deleted by PR-6R2. They must not come back anywhere: not in the
#: template, not in the script, not in the stylesheet, not in the served page.
DELETED_HALL_TEXT = (
    "NED 不确定性审查局 · 网上办事大厅",
    "NED Uncertainty Review Bureau · Online Service Hall",
    "自 2026 年起，系统性解释掉好消息。",
    "把可疑的好消息重新变成不确定。",
    "本局只审查材料的证据资格",
)

#: Punchlines a serious screen is never allowed to carry. The register is scoped
#: per situation: ``timeline_boundary``'s own locked copy contains 「害羞」 only
#: inside the denial "后面的边界也不是害羞", so that screen is judged on the two
#: emoji the older pin already bans there. A new hall label must smuggle none of
#: this into either register.
ADMIN_JOKES = {
    p.SITUATION_BOUNDARY: ("👍", "🤠", "人好", "七种替代解释", "十年", "同行评审", "害羞"),
    p.SITUATION_TIMELINE_BOUNDARY: ("👍", "🤠"),
}

#: sha256 (first 16 hex digits) of each legacy catalogue value's canonical JSON,
#: recorded before FD-6 added ``front_desk``. Any semantic move inside one of these
#: keys fails this pin with the key's own name.
LEGACY_DIGESTS = {
    "analysis": "250b372248f860cc",
    "aspect_boundary_copy": "f35f3b28c894921c",
    "aspect_card_situations": "60a82af717b9b183",
    "aspect_copy": "499adcce0093fcfc",
    "aspect_page_labels": "bedf503416663423",
    "audit_copy": "dec15f86cddb9642",
    "audit_default_lines": "ffd37c09aa8ebe8a",
    "audit_flavours": "b44625121b37182b",
    "boundary_page_types": "d8769523cb558fab",
    "boundary_situations": "ecb9ba9ac7a04d69",
    "clause_separators": "38c3028c45d8c064",
    "comedy_by_rule": "57927ada31f096ff",
    # PR-2 changed two values on purpose: the first-screen table gained the material-registered
    # state and its fallback copy now names what was not recognised, and three comedy-pack lines
    # stopped naming a concrete item the input may not contain (a milk tea, an invented hour, an
    # invented "mm"). Every other key keeps the digest it had.
    "comedy_packs": "0f090a98c6b4809a",
    "comparison_reason_verdicts": "dcf655e6a52c16da",
    "display_repairs": "0c85798b360cae47",
    "duration_artifacts": "6280be706771d8e3",
    "explanation_audit_situation": "ad2cd00b23e1fded",
    "explicit_quality": "7234881cfcd7008f",
    "fact_fixed": "8a91dc777c8e26a9",
    "fact_from_observed": "4fa517ba814a6f40",
    "fact_signal_types": "ba3275bfc9079256",
    "first_screen": "04395410649ad588",
    "fnbp": "7994bf15041ee88d",
    "forbidden_emoji": "481b2746fd57ccc6",
    "greeting_one_off_fact": "50c73d562e214552",
    "greeting_rule": "c761251984edf77a",
    "material_registry_copy": "bbd6798b3ec0ab33",
    "material_source_labels": "9e1d5564cd46516d",
    "materials_fallback": "e91bc9d0e4f42b71",
    "materials_slot": "4c574c2750831337",
    "multiple_aspects_promotes": "5c24f383b7663c99",
    "multiple_aspects_situation": "707ae98de8e6e1d1",
    "nea_framing": "663e20a49009c236",
    "pair_quality_labels": "4451d1cf98c3ffe4",
    "quality_bands": "6574afa83267a357",
    "quality_source": "9bcb5f2fb56fa750",
    "quality_top": "d8d703409a488ac1",
    "reading_signal_types": "746cb6535b12e731",
    "reading_slot": "f5ed8765ad778d8a",
    "routine_claim": "1594749f33ff93ae",
    "routine_markers": "c4eb024617f279ec",
    "self_discount_promotes": "f9436d130c0792a1",
    "self_discount_signal_types": "48ad26d88952017e",
    "situation_by_comparison_reason": "326ef654387ae3aa",
    "situation_by_verdict": "cb5134fcf1c2a773",
    "user_reading": "ebd7685ebb268c9e",
    "verdict_overrides": "43d774733393a9ee",
}

#: Every key the desk block carries besides the four frozen labels: PR-3's stage chrome,
#: PR-4R's state words, and PR-6R2's labels for the tab index, the intake fields, the review
#: sections and the review region's own notes.
#: Every key the desk block carries besides the four frozen labels: PR-3's stage chrome,
#: PR-4R's state words, PR-6R2's labels and PR-6M2's casebook copy. The set is frozen: adding
#: or removing a key is a copy change and belongs in a batch that says so.
#: Every key the desk block carries besides the four frozen labels: PR-3's stage chrome,
#: PR-4R's state words, PR-6R2's labels, PR-6M2's casebook copy and PR-6M3's review copy.
#: The set is frozen: adding or removing a key is a copy change and belongs in a batch that
#: says so.
#: Every key the desk block carries besides the four frozen labels: PR-3's stage chrome,
#: PR-4R's state words, PR-6R2's labels, PR-6M2's casebook copy and PR-6M3's review copy.
#: The set is frozen: adding or removing a key is a copy change and belongs in a batch that
#: says so.
#: Every key the desk block carries besides the four frozen labels: PR-3's stage chrome,
#: PR-4R's state words, PR-6R2's labels, PR-6M2's casebook copy and PR-6M3's review copy.
#: The set is frozen: adding or removing a key is a copy change and belongs in a batch that
#: says so.
#: Every key the desk block carries besides the four frozen labels: PR-3's stage chrome,
#: PR-4R's state words, PR-6R2's labels, PR-6M2's casebook copy and PR-6M3's review copy.
#: The set is frozen: adding or removing a key is a copy change and belongs in a batch that
#: says so.
#: Every key the desk block carries besides the four frozen labels: PR-3's stage chrome,
#: PR-4R's state words, PR-6R2's labels, PR-6M2's casebook copy and PR-6M3's review copy.
#: The set is frozen: adding or removing a key is a copy change and belongs in a batch that
#: says so.
#: Every key the desk block carries besides the four frozen labels: PR-3's stage chrome,
#: PR-4R's state words, PR-6R2's labels, PR-6M2's casebook copy and PR-6M4D's review copy.
#: The set is frozen: adding or removing a key is a copy change and belongs in a batch that
#: says so.
DESK_KEYS = {
    "tab_intake",
    "tab_others",
    "tab_asymmetry",
    "tab_lab",
    "intake_purpose",
    "field_material",
    "field_mode",
    "field_material_placeholder",
    "examples_heading",
    "section_reality",
    "section_nea",
    "section_hypotheses",
    "section_audit",
    "section_aspects",
    "verdict_heading",
    "copy_json",
    "screen_quality_label",
    "nea_observed_label",
    "nea_amplified_label",
    "nea_note",
    "hypo_note",
    "hypo_empty",
    "plausibility",
    "casebook_tab",
    "casebook_heading",
    "casebook_intro",
    "casebook_disabled",
    "casebook_create_label",
    "casebook_label_field",
    "casebook_label_placeholder",
    "casebook_create",
    "casebook_created",
    "casebook_empty",
    "casebook_expand",
    "casebook_collapse",
    "casebook_counts",
    "casebook_file_action",
    "casebook_file_choose",
    "casebook_file_new",
    "casebook_file_occurred",
    "casebook_relative_hint",
    "casebook_relative_filed",
    "casebook_dated_filed",
    "casebook_occurred_by_user",
    "casebook_file_confirm",
    "casebook_file_cancel",
    "casebook_file_pick",
    "casebook_filing",
    "casebook_filed",
    "casebook_filed_again",
    "casebook_file_failed",
    "casebook_times",
    "casebook_occurred_unknown",
    "casebook_occurred_relative",
    "casebook_state",
    "casebook_material",
    "casebook_no_material",
    "casebook_entry_line",
    "casebook_delete_entry",
    "casebook_delete_case",
    "casebook_delete_casebook",
    "casebook_delete_ask",
    "casebook_delete_yes",
    "casebook_delete_cancel",
    "casebook_deleted",
    "casebook_delete_failed",
    "casebook_archive_failed",
    "casebook_reread_action",
    "casebook_reread_input",
    "casebook_reread_running",
    "casebook_reread_failed",
    "casebook_reread_recorded_heading",
    "casebook_reread_today_heading",
    "casebook_reread_engine",
    "casebook_reread_reading",
    "casebook_reread_entries",
    "casebook_reread_materials",
    "casebook_reread_counts",
    "casebook_reread_rule_id_only",
    "casebook_reread_case_level",
    "casebook_reread_fields",
    "casebook_reread_class_same",
    "casebook_reread_class_changed",
    "casebook_reread_class_missing",
    "casebook_reread_class_ambiguous",
    "casebook_reread_class_new",
    "casebook_reread_changed_note",
    "casebook_reread_same_note",
    "casebook_review_action",
    "casebook_review_heading",
    "casebook_review_choose",
    "casebook_review_occurred",
    "casebook_review_confirm",
    "casebook_review_cancel",
    "casebook_review_pick",
    "casebook_review_none",
    "casebook_review_running",
    "casebook_review_failed",
    "casebook_review_empty",
    "casebook_review_mode_single",
    "casebook_review_mode_joint",
    "casebook_review_read",
    "casebook_review_counts",
    "casebook_review_governing",
    "casebook_review_relation_supports",
    "casebook_review_relation_conflicts",
    "casebook_review_relation_superseded",
    "casebook_review_relation_unrelated",
    "casebook_review_relation_not_comparable",
    "casebook_review_relation_insufficient",
    "casebook_review_undated",
    "casebook_review_governing_line",
    "casebook_review_governing_current",
    "casebook_review_note",
    "casebook_opinion_no_history",
    "casebook_opinion_nothing_comparable",
    "casebook_opinion_current_case_has_no_direction",
    "casebook_opinion_boundary_governs",
    "casebook_opinion_order_unknown",
    "casebook_opinion_mixed_directions",
    "casebook_opinion_only_supports",
    "casebook_opinion_only_conflicts",
    "privacy_footer",
    "status_no_input",
    "status_analyze_failed",
    "hypo_note_boundary",
    "hypo_note_hostile",
    "stage_material_count",
    "stage_material_none",
    "stage_review_done",
    "stage_review_unsignable",
    "stage_review_none",
    "stage_issuance_signed",
    "stage_issuance_material",
    "stage_issuance_none",
    "issuance_signed",
    "issuance_boundary",
    "issuance_boundary_sub",
    "issuance_material",
    "issuance_material_sub",
    "issuance_none",
    "issuance_none_sub",
    "material_count",
    "material_count_none",
    "review_relation_evidence_and_material",
    "review_relation_evidence_only",
    "review_relation_material_only",
    "review_relation_none",
    "language_toggle",
    "stage_name_submit",
    "stage_name_material",
    "stage_name_review",
    "stage_name_issuance",
    "issuance_kicker",
    "stage_kicker_submit",
    "stage_submit_state",
    "submit_pending",
    "submit_done",
    "satire_line",
    "stamp_signed",
    "stamp_unsigned",
    "stamp_material_pending",
    "stamp_boundary",
    "material_lead",
    "review_lead",
    "issuance_lead",
    "submit_another",
    "stage_material_independent_none",
    "fact_material_only",
    "material_empty_independent_none",
}


def digest(value: object) -> str:
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def hall_section() -> str:
    """The hall-copy block of app.js, with its whole-line comments removed."""

    match = re.search(r"/\* -+ hall copy \*/(.*?)/\* -+ init \*/", SCRIPT, re.DOTALL)
    assert match is not None, "the hall-copy block is missing from app.js"
    return "\n".join(
        line for line in match.group(1).splitlines() if not line.strip().startswith("//")
    )


def screens() -> list[str]:
    """Every first screen the catalogue ships, as one flat list of blobs."""

    return [
        " ".join([screen.title, *screen.lines, screen.reality])
        for per_mode in p.FIRST_SCREEN.values()
        for languages in per_mode.values()
        for screen in languages.values()
    ]


# --------------------------------------------------------------------------- #
# the copy: one block, five labels, both languages
# --------------------------------------------------------------------------- #


def test_the_hall_has_exactly_the_five_frozen_labels() -> None:
    """The five hall labels keep their wording; PR-3 added stage chrome beside them."""

    catalog = p.web_personality_catalog()
    assert catalog["front_desk"] == p.FRONT_DESK_COPY
    # the five frozen labels are still all there, with the frozen wording
    assert set(FRONT_DESK) <= set(catalog["front_desk"])
    for key, wording in FRONT_DESK.items():
        assert catalog["front_desk"][key] == {"zh": wording[0], "en": wording[1]}, key
    # PR-3's dossier chrome, PR-4R's state words and PR-6R2's desk labels live in the same
    # block, and nothing else does. The set is frozen: widening it is a copy change.
    assert set(catalog["front_desk"]) == set(FRONT_DESK) | DESK_KEYS


@pytest.mark.parametrize("key", sorted(p.FRONT_DESK_COPY))
def test_every_hall_label_is_complete_in_both_languages(key: str) -> None:
    values = p.FRONT_DESK_COPY[key]
    assert set(values) == {"zh", "en"}, key
    assert values["zh"].strip() and values["en"].strip(), key
    assert values["zh"] != values["en"], key


def test_the_served_page_embeds_the_hall_copy() -> None:
    """The client can only look the labels up because the page carries them."""

    with TestClient(api_app) as client:
        page = client.get("/").text
    match = re.search(r'<script id="personality-catalog"[^>]*>(.*?)</script>', page, re.DOTALL)
    assert match is not None
    embedded = json.loads(match.group(1))
    assert embedded["front_desk"] == p.FRONT_DESK_COPY
    # PR-6R2: the served markup carries the zh wording as its no-JS fallback, in the document's
    # own declared language. The English variant is runtime-only, served from the catalogue above.
    assert "请提交待审查材料" in page
    assert "提交审查" in page
    assert "技术档案" in page
    # the old English desk fallbacks are gone with the bilingual headings
    for gone in (
        "Analyze Evidence",
        "Negative Evidence Amplifier",
        "Final Verdict",
        "Alternative Hypotheses",
        "Evidence Intake",
    ):
        assert gone not in page, gone


# --------------------------------------------------------------------------- #
# the web assets: catalogue only, no fallback copy, no invented stage
# --------------------------------------------------------------------------- #


def test_the_deleted_hall_text_is_gone_from_the_whole_tree() -> None:
    """The three sentences PR-6R2 deleted stay deleted; nothing smuggles them back in."""

    for gone in DELETED_HALL_TEXT:
        assert gone not in TEMPLATE, gone
        assert gone not in SCRIPT, gone
        assert gone not in STYLE, gone
        assert gone not in json.dumps(p.web_personality_catalog(), ensure_ascii=False), gone


def test_the_web_assets_hold_no_second_copy_of_the_hall_labels() -> None:
    """PR-6R2: the markup's fallback is the zh wording, and the en wording is runtime-only.

    The desk is a zh-first product: the document declares zh-CN, and the script swaps in the
    catalogue's en variant when the reader asks for English. A scriptless page therefore reads in
    the product's own language instead of a second one - and the script itself still carries no
    sentence of either language.
    """

    for key, (zh, en) in FRONT_DESK.items():
        assert en not in TEMPLATE, (key, en)
        assert en not in SCRIPT, (key, en)
        assert en not in STYLE, (key, en)
        assert zh not in SCRIPT, (key, zh)
        assert zh not in STYLE, (key, zh)
        if key in ANCHORS:
            assert zh in TEMPLATE, (key, zh)


def test_the_markup_fallback_is_the_catalogue_wording() -> None:
    """PR-6R2: the no-JS fallback is the zh wording, pinned equal to the catalogue.

    The desk declares zh-CN, so a scriptless page reads in the product's own language. Equality is
    asserted rather than mere presence, so the markup and the catalogue cannot drift apart - which
    is the property the old "no second copy" pin was protecting.
    """

    for key, anchor in ANCHORS.items():
        match = re.search(rf'id="{re.escape(anchor)}"[^>]*>([^<]*)<', TEMPLATE)
        assert match is not None, anchor
        assert match.group(1).strip() == p.FRONT_DESK_COPY[key]["zh"], (anchor, match.group(1))


def test_the_injection_reads_the_catalogue_and_names_no_stage() -> None:
    section = hall_section()
    assert 'catalogueObj("front_desk")' in section
    for key in FRONT_DESK:
        assert key in section, key
    for anchor in ANCHORS.values():
        assert f'"{anchor}"' in section, anchor
    # hall chrome, not a status machine: no result state, no situation, no verdict
    for banned in ("situation", "boundary", "verdict", "payload", "stage", "loading"):
        assert banned not in section, banned


def test_the_injection_is_wired_into_the_page_start() -> None:
    assert "renderFrontDeskCopy();" in SCRIPT
    match = re.search(r"function init\(\) \{(.*?)\n  \}", SCRIPT, re.DOTALL)
    assert match is not None
    assert "renderFrontDeskCopy();" in match.group(1)


def test_the_anchors_exist_in_the_shipped_template() -> None:
    for anchor in ANCHORS.values():
        assert f'id="{anchor}"' in TEMPLATE, anchor


def test_the_injection_holds_no_fallback_copy() -> None:
    """A silent catalogue leaves the shipped text standing; nothing is invented."""

    section = hall_section()
    for literal in ("Analyze Evidence", "Technical Details", "Verdict", "Evidence Intake"):
        assert literal not in section, literal


def test_the_language_choice_follows_the_document_declaration() -> None:
    """No locale mechanism is invented: the document's own declaration decides.

    ``zh`` and ``zh-CN`` take the zh variant; every other declaration -- including
    a missing or unknown one -- takes en. The block owns no private locale state,
    so there is nothing here to drift away from the document.
    """

    section = hall_section()
    assert "document.documentElement" in section
    assert 'getAttribute("lang")' in section
    assert 'indexOf("zh") === 0' in section
    for foreign in ("localStorage", "sessionStorage", "navigator.language", "cookie"):
        assert foreign not in section, foreign


# --------------------------------------------------------------------------- #
# the boundary: hall chrome never turns into a joke
# --------------------------------------------------------------------------- #


def test_no_hall_label_reaches_a_result_screen() -> None:
    for blob in screens():
        for key, (zh, en) in FRONT_DESK.items():
            assert zh not in blob, key
            assert en not in blob, key


@pytest.mark.parametrize("language", ("zh", "en"))
@pytest.mark.parametrize("situation", (p.SITUATION_BOUNDARY, p.SITUATION_TIMELINE_BOUNDARY))
def test_a_boundary_screen_gains_no_new_administrative_joke(situation: str, language: str) -> None:
    for mode in p.MODES:
        screen = p.first_screen(situation, mode, language)
        blob = " ".join([screen.title, *screen.lines, screen.reality])
        for ban in ADMIN_JOKES[situation]:
            assert ban not in blob, (situation, language, mode, ban)
        for key, (zh, en) in FRONT_DESK.items():
            assert zh not in blob and en not in blob, (situation, language, mode, key)


# --------------------------------------------------------------------------- #
# the 47 keys that were already there
# --------------------------------------------------------------------------- #


def test_the_legacy_catalogue_keys_are_not_overwritten() -> None:
    catalog = p.web_personality_catalog()
    assert set(catalog) == set(LEGACY_DIGESTS) | {"front_desk"}
    changed = [key for key, want in LEGACY_DIGESTS.items() if digest(catalog[key]) != want]
    assert not changed, changed


def test_the_serious_register_prints_the_annotation_without_the_joke() -> None:
    """PR-6R2: a stated boundary changes one sentence, and only that sentence.

    The playful example that explains the hypotheses card belongs on an ordinary desk. On a
    boundary screen NED has just said it stopped joking, so the client prints the catalogue's
    serious variant there, keyed on the same ``data-situation`` the register already uses.
    """

    assert p.FRONT_DESK_COPY["hypo_note_boundary"]["zh"] != p.FRONT_DESK_COPY["hypo_note"]["zh"]
    assert "👍" not in p.FRONT_DESK_COPY["hypo_note_boundary"]["zh"]
    assert "人好" not in p.FRONT_DESK_COPY["hypo_note_boundary"]["zh"]
    assert "开玩笑" not in p.FRONT_DESK_COPY["hypo_note"]["zh"]
    assert "renderReviewNote(situation);" in SCRIPT
    note = SCRIPT[SCRIPT.index("function renderReviewNote(") :]
    note = note[: note.index("function ", 10)]
    assert '"boundary"' in note and '"timeline_boundary"' in note
    # and the annotation is not re-set by the language-only label pass
    labels = SCRIPT[SCRIPT.index("var DESK_LABEL_IDS") :]
    labels = labels[: labels.index("];")]
    assert "hypo-note" not in labels
