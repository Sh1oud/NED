"""NED must still have a personality.

These tests protect the product invariants of ``docs/PERSONALITY_BIBLE.md`` §10:
the engine may be as rigorous as it likes, but the front page a normal person
sees has to stay a joke that lands — and it must never say something the engine
did not establish.

Nothing here tests the scores. If a value changes here, the personality layer
changed a fact, which is the one thing it is not allowed to do.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ned.app.cli import app as cli_app
from ned.app.core.analyzer import NedAnalyzer
from ned.app.ui import personality as p
from typer.testing import CliRunner

runner = CliRunner()

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "ned" / "app" / "templates" / "index.html"
RULES = ROOT / "ned" / "app" / "rules"

#: The twelve lines the Bible §5 pins. Rewriting one of these is a product
#: decision, not a refactor.
CANONICAL_COPY = (
    "好消息已送外审；坏消息编辑部直录。",
    "正向证据博士论文级审查；负向证据先到先得。",
    "不是没有证据。是 NED 不想承认。👍",
    "收到。现在开始寻找七种替代解释。👍",
    "样本量 n=1。建议再观察十年。👍",
    "明确边界。NED 停止狡辩。🚧",
    "不确定性，不等于否认明确证据。",
    "前面的两个小时没有被历史删除。",
    "后面的边界也不是害羞。🚧",
    "预测不是事实。期待也不是证据。🤠",
    "一次预测成功，不等于发现了规律。🤠",
    "婚姻属于法律关系，不能单独证明爱情。👍",
)

LATENCY_FACT = "消息发出去五分钟没回复。"
LATENCY_CONCLUSION = "消息发出去五分钟没回复，她肯定不想理我。"
STRONG_POSITIVE = "她主动找我聊了两个小时"
BOUNDARY = "她说别再联系我了。"
HOSTILE = "她说你他妈有病吧。"
COLD_REPLY = "她就回了一个嗯。"
STARTED_AGAIN_NO_BASIS = "她主动找我聊了两个小时，但五分钟没回复"
DOUBLE_STANDARD_POSITIVE = "她主动找我聊了两个小时，但可能只是人好。"
DOUBLE_STANDARD_NEGATIVE = "五分钟没回复，她肯定不想理我。"
TIMELINE_POSITIVE = "她主动找我聊了两个小时。"
TIMELINE_NEGATIVE = "她后来明确让我别烦她。"

#: Internal vocabulary that belongs to Technical Details and nowhere else.
INTERNAL_FIELDS = (
    "comparison_applicable",
    "treatment_gap",
    "interpretive_basis",
    "asymmetry_score",
    "categorical",
)

#: Element ids that only ever belong to the folded technical block.
INTERNAL_IDS = (
    "verdict-code",
    "evidence-strength-value",
    "discount-value",
    "amplification-value",
    "reaching-value",
    "asym-profile-comparable",
    "asym-profile-reason",
    "asym-treatment-gap",
    "asym-reading-positive-basis",
    "breakdown-rows",
    "evidence-rows",
)


def situation_of(result: Any) -> str:
    """The screen a result belongs to."""

    return p.resolve_situation(result.verdict.code)


def basis_of(result: Any) -> bool:
    """Whether the reader's own wording is in the input."""

    return p.reading_basis_present(
        signal_types=[span.signal_type.value for span in result.evidence]
    )


def screen_blob(result: Any, *, basis: bool | None = None) -> str:
    """Everything a first screen would show for one result."""

    resolved = basis_of(result) if basis is None else basis
    screen = p.first_screen(situation_of(result), result.mode, "zh", basis=resolved)
    return " ".join([screen.title, *screen.lines, screen.reality])


class _Structure(HTMLParser):
    """A very small structural reader for the shipped template."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, Any]] = []
        self.by_id: dict[str, dict[str, Any]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: (value or "") for key, value in attrs}
        node: dict[str, Any] = {
            "tag": tag,
            "id": attributes.get("id", ""),
            "open": "open" in attributes,
            "children": [],
        }
        if self.stack:
            self.stack[-1]["children"].append(node)
        if node["id"]:
            self.by_id[node["id"]] = node
        if tag not in ("br", "img", "input", "meta", "link", "hr"):
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                return


@pytest.fixture(scope="module")
def structure() -> _Structure:
    parser = _Structure()
    parser.feed(TEMPLATE.read_text(encoding="utf-8"))
    return parser


def contains(node: dict[str, Any], target_id: str) -> bool:
    return any(child["id"] == target_id or contains(child, target_id) for child in node["children"])


# --------------------------------------------------------------------------- #
# A. an explicit boundary never becomes a joke
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", p.MODES)
def test_a_a_boundary_screen_has_no_punchline(analyzer: NedAnalyzer, mode: str) -> None:
    result = analyzer.analyze_text(BOUNDARY, mode=mode)  # type: ignore[arg-type]
    assert situation_of(result) == p.SITUATION_BOUNDARY
    blob = screen_blob(result)
    assert "NED 停止狡辩" in blob
    for banned in ("👍", "🤠", "人好", "七种替代解释", "十年", "同行评审", "害羞"):
        assert banned not in blob, banned


def test_a_the_boundary_verdict_sentence_loses_its_joke_emoji(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(BOUNDARY, mode="normal")
    shown = p.emoji_discipline(situation_of(result), result.verdict.text)
    assert "🚧" in shown
    assert "👍" not in shown and "🤠" not in shown


def test_a_the_boundary_screen_is_the_same_in_every_mode() -> None:
    screens = {mode: p.first_screen(p.SITUATION_BOUNDARY, mode, "zh") for mode in p.MODES}
    assert screens["normal"] == screens["scientific"] == screens["extreme"]


# --------------------------------------------------------------------------- #
# B. no second person without the reader's own words
# --------------------------------------------------------------------------- #


def test_b_five_minutes_of_silence_does_not_invent_a_reader(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(LATENCY_FACT, mode="normal")
    assert situation_of(result) == p.SITUATION_LATENCY
    assert basis_of(result) is False
    blob = screen_blob(result)
    for banned in ("你的大脑", "你又开始了", "你的结论", "你肯定", "你其实"):
        assert banned not in blob, banned
    assert "终审庭" in blob, "the joke must still point at the mechanism"


def test_b_the_policy_verdict_stops_blaming_a_silent_reader(analyzer: NedAnalyzer) -> None:
    """The registered follow-up: a policy verdict must not accuse the reader."""

    result = analyzer.analyze_text(STARTED_AGAIN_NO_BASIS, mode="normal")
    assert result.verdict.code == "nea.you_started_again"
    assert result.asymmetry is not None
    assert result.asymmetry.user_interpretation.status == "not_present"
    assert basis_of(result) is False
    shown = p.verdict_display(result.verdict.code, result.verdict.text, basis=False)
    assert "你又开始了" not in shown
    assert "本机构" in shown, "the sentence must point back at NED"
    assert "你又开始了" not in screen_blob(result)


def test_b_the_policy_verdict_keeps_its_rule_untouched(analyzer: NedAnalyzer) -> None:
    """Only the display changes: the verdict the engine produced is unchanged."""

    result = analyzer.analyze_text(STARTED_AGAIN_NO_BASIS, mode="normal")
    assert result.verdict.text == "Reject. 理由：你又开始了。👍"
    assert result.verdict.severity == "reject"
    assert result.negative_evidence_amplification >= 70
    assert (
        p.verdict_display(result.verdict.code, result.verdict.text, basis=True)
        == result.verdict.text
    )


# --------------------------------------------------------------------------- #
# C. and it is granted when the reader did speak
# --------------------------------------------------------------------------- #


def test_c_a_reader_conclusion_licenses_the_second_person(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(LATENCY_CONCLUSION, mode="normal")
    assert basis_of(result) is True
    assert "你的大脑已经开庭了" in screen_blob(result)
    plain = p.first_screen(p.SITUATION_LATENCY, "normal", "zh", basis=False)
    assert "你的大脑" not in " ".join(plain.lines)


def test_c_the_licence_exists_because_the_words_are_there(analyzer: NedAnalyzer) -> None:
    """Same verdict, different licence: the engine fact is identical."""

    fact = analyzer.analyze_text(LATENCY_FACT, mode="normal")
    conclusion = analyzer.analyze_text(LATENCY_CONCLUSION, mode="normal")
    assert fact.verdict.code == conclusion.verdict.code
    assert basis_of(fact) is False and basis_of(conclusion) is True


# --------------------------------------------------------------------------- #
# D. the flagship mismatch keeps its canonical contrast
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", p.MODES)
def test_d_the_double_standard_keeps_a_canonical_contrast(analyzer: NedAnalyzer, mode: str) -> None:
    result = analyzer.asymmetry.compare(
        positive_text=DOUBLE_STANDARD_POSITIVE,
        negative_text=DOUBLE_STANDARD_NEGATIVE,
        mode=mode,  # type: ignore[arg-type]
    )
    assert result.verdict.code == "interpretation.double_standard_detected"
    blob = " ".join(p.first_screen(p.SITUATION_MISMATCH, mode, "zh").lines)
    assert (
        "好消息已送外审；坏消息编辑部直录。" in blob
        or "正向证据博士论文级审查；负向证据先到先得" in blob
    )


def test_d_the_mismatch_screen_never_shows_a_basis_field_name() -> None:
    screen = p.first_screen(p.SITUATION_MISMATCH, "normal", "zh")
    blob = " ".join([screen.title, *screen.lines, screen.reality])
    for field in INTERNAL_FIELDS:
        assert field not in blob, field


# --------------------------------------------------------------------------- #
# E. a strong positive still gets a personality
# --------------------------------------------------------------------------- #


def test_e_strong_positive_is_answered_with_a_joke(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(STRONG_POSITIVE, mode="normal")
    assert situation_of(result) == p.SITUATION_POSITIVE
    blob = screen_blob(result)
    assert any(marker in blob for marker in ("七种替代解释", "同行评审", "样本量", "👍", "🤠")), (
        blob
    )
    assert blob != result.reality_check, "the screen must not be only analysis prose"


# --------------------------------------------------------------------------- #
# F. the cold reply keeps its number in Technical Details
# --------------------------------------------------------------------------- #


def test_f_cold_reply_first_screen_has_no_internal_number(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(COLD_REPLY, mode="normal")
    assert result.verdict.code == "nea.cold_reply_insufficient"
    blob = screen_blob(result)
    assert "讣告" in blob
    assert re.search(r"\d+\s*/\s*100", blob) is None, blob
    for number in ("22", "45.0", "51.1"):
        assert number not in blob, number


def test_f_the_number_is_still_available_to_the_engine(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(COLD_REPLY, mode="normal")
    assert [span.information_content for span in result.evidence] == [22.0]
    assert result.signal_strength == 45.0


# --------------------------------------------------------------------------- #
# G + H. the first screen is the first screen
# --------------------------------------------------------------------------- #


def test_g_technical_details_is_collapsed(structure: _Structure) -> None:
    details = structure.by_id.get("technical-details")
    assert details is not None, "the analyze report must fold its internals"
    assert details["tag"] == "details"
    assert details["open"] is False, "Technical Details must be collapsed by default"
    asym_details = structure.by_id.get("asym-technical-details")
    assert asym_details is not None and asym_details["tag"] == "details"
    assert asym_details["open"] is False


def test_h_the_internal_readouts_live_inside_technical_details(structure: _Structure) -> None:
    details = structure.by_id["technical-details"]
    asym_details = structure.by_id["asym-technical-details"]
    for internal_id in INTERNAL_IDS:
        assert internal_id in structure.by_id, internal_id
        assert contains(details, internal_id) or contains(asym_details, internal_id), internal_id


def test_h_no_internal_readout_is_inside_a_first_screen(structure: _Structure) -> None:
    first = structure.by_id["first-screen"]
    asym_first = structure.by_id["asym-first-screen"]
    for internal_id in INTERNAL_IDS:
        assert not contains(first, internal_id), internal_id
        assert not contains(asym_first, internal_id), internal_id


def test_h_the_first_screen_carries_the_five_parts(structure: _Structure) -> None:
    for screen_id, prefix in (("first-screen", ""), ("asym-first-screen", "asym-")):
        first = structure.by_id[screen_id]
        for part in (
            "screen-title",
            "screen-fact",
            "screen-quality-row",
            "screen-lines",
            "screen-reality",
        ):
            assert contains(first, prefix + part), (screen_id, part)


# --------------------------------------------------------------------------- #
# I. modes differ in voice, never in facts
# --------------------------------------------------------------------------- #


def test_i_modes_speak_differently(analyzer: NedAnalyzer) -> None:
    screens = {
        mode: screen_blob(analyzer.analyze_text(STRONG_POSITIVE, mode=mode))  # type: ignore[arg-type]
        for mode in p.MODES
    }
    assert len(set(screens.values())) == 3, screens


def test_i_but_the_evidence_profile_does_not_move(analyzer: NedAnalyzer) -> None:
    facts = []
    for mode in p.MODES:
        result = analyzer.analyze_text(STRONG_POSITIVE, mode=mode)  # type: ignore[arg-type]
        facts.append(
            (
                result.signal_strength,
                tuple(span.information_content for span in result.evidence),
                tuple(span.signal_type for span in result.evidence),
            )
        )
    assert len(set(facts)) == 1, facts


def test_i_the_compared_profile_does_not_move_either(analyzer: NedAnalyzer) -> None:
    profiles = []
    for mode in p.MODES:
        result = analyzer.asymmetry.compare(
            positive_text=STRONG_POSITIVE,
            negative_text="五分钟没回复",
            mode=mode,  # type: ignore[arg-type]
        )
        profile = result.evidence_profile
        profiles.append(
            (
                profile.comparable,
                profile.positive_raw_strength,
                profile.negative_raw_strength,
                profile.raw_strength_gap,
                profile.information_gap,
            )
        )
    assert len(set(profiles)) == 1, profiles


# --------------------------------------------------------------------------- #
# J. hostility is acknowledged before it is mocked
# --------------------------------------------------------------------------- #


def test_j_hostile_expression_admits_the_hostility(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(HOSTILE, mode="normal")
    assert situation_of(result) == p.SITUATION_HOSTILE
    blob = screen_blob(result)
    assert "敌意" in blob
    for banned in ("人好", "只是害羞", "可能喜欢你", "其实是在意"):
        assert banned not in blob, banned


def test_j_the_joke_targets_the_over_inference() -> None:
    screen = p.first_screen(p.SITUATION_HOSTILE, "normal", "zh")
    blob = " ".join(screen.lines)
    assert "永远恨你" in blob or "永久" in blob
    assert "扩写" in screen.reality and "永久" in screen.reality


# --------------------------------------------------------------------------- #
# K. a boundary comparison stays serious and numberless
# --------------------------------------------------------------------------- #


def test_k_timeline_and_boundary_decline_the_calculator(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(
        positive_text=TIMELINE_POSITIVE, negative_text=TIMELINE_NEGATIVE
    )
    assert result.verdict.code == "ned.comparison_not_applicable"
    assert result.evidence_profile.comparison_reason == "explicit_boundary_not_comparable"
    situation = p.resolve_situation(result.verdict.code, result.evidence_profile.comparison_reason)
    assert situation == p.SITUATION_TIMELINE_BOUNDARY
    screen = p.first_screen(situation, result.mode, "zh")
    blob = " ".join([screen.title, *screen.lines, screen.reality])
    assert "后面的边界也不是害羞" in blob
    assert "🤠" not in blob
    assert "👍" not in blob
    assert re.search(r"0\.\d{2,}", blob) is None, blob


def test_k_the_declined_pair_has_no_numbers_to_show(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(
        positive_text=TIMELINE_POSITIVE, negative_text=TIMELINE_NEGATIVE
    )
    profile = result.evidence_profile
    assert profile.raw_strength_gap is None
    assert profile.information_gap is None
    assert result.ned_treatment is not None
    assert result.ned_treatment.treatment_gap is None
    assert result.asymmetry_score is None


def test_k_the_boundary_verdict_sentence_is_serious_too(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(
        positive_text=TIMELINE_POSITIVE, negative_text=TIMELINE_NEGATIVE
    )
    situation = p.resolve_situation(result.verdict.code, result.evidence_profile.comparison_reason)
    shown = p.emoji_discipline(situation, result.verdict.text)
    assert "🤠" not in shown and "👍" not in shown
    assert "拒绝本次对称比较" in shown


def test_k_a_comparable_pair_is_not_described_as_a_declined_one(analyzer: NedAnalyzer) -> None:
    """A comparable pair whose reader said nothing is not a refused comparison."""

    result = analyzer.asymmetry.compare(positive_text=STRONG_POSITIVE, negative_text="五分钟没回复")
    assert result.evidence_profile.comparable is True
    situation = p.resolve_situation(result.verdict.code, result.evidence_profile.comparison_reason)
    assert situation == p.SITUATION_PAIR_CLEAN
    blob = " ".join(p.first_screen(situation, "normal", "zh").lines)
    assert "不足以支持一次对称比较" not in blob
    assert "不评估你的证据标准" in blob


# --------------------------------------------------------------------------- #
# L. canonical copy is pinned
# --------------------------------------------------------------------------- #


def _personality_strings() -> str:
    blob: list[str] = []
    for per_mode in p.FIRST_SCREEN.values():
        for per_language in per_mode.values():
            for screen in per_language.values():
                blob.extend([screen.title, screen.reality])
                for lines in (screen.lines, screen.lines_with_basis):
                    blob.append(" ".join(lines))
                    # a canonical sentence may be carried as consecutive lines
                    blob.append("".join(lines))
    blob.extend([p.FNBP_HIT_FEEDBACK["zh"], p.FNBP_MISS_FEEDBACK["zh"], p.NEA_FRAMING["zh"]])
    blob.extend(feedback.zh for feedback in p.ANALYSIS_FEEDBACK)
    blob.extend(message["zh"] for message in p.READING_STATUS_MESSAGES.values())
    blob.append(p.TECHNICAL_REACHING)
    return "\n".join(blob)


def test_l_every_canonical_line_still_exists_somewhere() -> None:
    """Canonical Copy is either personality copy or shipped engine copy."""

    engine = "\n".join(
        (RULES / name).read_text(encoding="utf-8") for name in ("verdicts.json", "escaping.json")
    )
    haystack = _personality_strings() + "\n" + engine
    for line in CANONICAL_COPY:
        assert line in haystack, line
    assert "预测不是事实。期待也不是证据。🤠" in p.FNBP_MISS_FEEDBACK["zh"]
    assert "一次预测成功，不等于发现了规律。🤠" in p.FNBP_HIT_FEEDBACK["zh"]


def test_l_the_embedded_catalogue_is_the_python_source(client: TestClient) -> None:
    """The web page and the CLI read one personality, not two."""

    page = client.get("/").text
    match = re.search(r'<script id="personality-catalog"[^>]*>(.*?)</script>', page, re.DOTALL)
    assert match is not None
    assert json.loads(match.group(1)) == p.web_personality_catalog()


def test_l_the_cli_prints_the_same_first_screen() -> None:
    result = runner.invoke(cli_app, ["analyze", BOUNDARY])
    assert result.exit_code == 0
    assert p.first_screen(p.SITUATION_BOUNDARY, "normal", "zh").title in result.stdout
    assert "NED 停止狡辩" in result.stdout
    assert "不确定性，不等于否认明确证据" in result.stdout


def test_l_the_cli_and_the_catalogue_never_disagree(analyzer: NedAnalyzer) -> None:
    """Every situation the engine can reach has copy in the shipped catalogue."""

    catalog = p.web_personality_catalog()
    shipped = catalog["first_screen"]
    assert isinstance(shipped, dict)
    for situation in shipped:
        assert situation in p.FIRST_SCREEN
    for code in catalog["situation_by_verdict"]:
        assert p.resolve_situation(str(code)) in p.FIRST_SCREEN


# --------------------------------------------------------------------------- #
# interface contract
# --------------------------------------------------------------------------- #


def test_personality_never_extends_an_api_payload(client: TestClient) -> None:
    payload = client.post("/api/analyze", json={"text": COLD_REPLY, "mode": "normal"}).json()
    blob = json.dumps(payload, ensure_ascii=False)
    for key in ("first_screen", "situation", "quality_label", "personality"):
        assert key not in blob, key
    assert "讣告" not in blob
    assert "七种替代解释" not in blob


def test_the_ladder_prefers_the_real_boundary(analyzer: NedAnalyzer) -> None:
    """A boundary beats every lower rung, whatever else the input contains."""

    result = analyzer.analyze_text(
        "她主动找我聊了两个小时，但她说让我别再联系她了。", mode="normal"
    )
    assert situation_of(result) == p.SITUATION_BOUNDARY


def test_unmapped_verdicts_fall_back_instead_of_crashing() -> None:
    assert p.resolve_situation("does.not.exist") == p.SITUATION_NEUTRAL
    screen = p.first_screen(p.SITUATION_NEUTRAL, "unknown-mode", "unknown-language")
    assert screen.title
    assert screen.lines


def test_every_situation_ships_both_languages_and_all_modes() -> None:
    for situation, per_mode in p.FIRST_SCREEN.items():
        for mode in p.MODES:
            assert mode in per_mode, (situation, mode)
            for language in ("zh", "en"):
                screen = per_mode[mode][language]
                assert screen.title and screen.lines and screen.reality, (situation, mode, language)


def test_quality_labels_are_plain_language_not_numbers() -> None:
    assert p.quality_label(5.0) == "很弱"
    assert p.quality_label(22.0) == "较弱"
    assert p.quality_label(34.0) == "有限"
    assert p.quality_label(66.0) == "较强"
    assert p.quality_label(82.32) == "很强"
    assert p.quality_label(None) == "\u2014"
    assert p.explicit_quality_label() == "明确"
    assert p.explicit_quality_label("en") == "explicit"


def test_the_quality_reading_follows_the_moment() -> None:
    """Bad news is read on information content, good news on strength."""

    assert p.QUALITY_SOURCE[p.SITUATION_LATENCY] == "negative_information"
    assert p.QUALITY_SOURCE[p.SITUATION_POSITIVE] == "strength"
    assert p.QUALITY_SOURCE[p.SITUATION_BOUNDARY] == "explicit"
    assert p.QUALITY_SOURCE[p.SITUATION_MISMATCH] == "none"


def test_the_personality_layer_is_not_imported_by_the_engine() -> None:
    """Personality copy can never reach a score."""

    engine_files = list((ROOT / "ned" / "app" / "core").rglob("*.py")) + list(
        (ROOT / "ned" / "app" / "providers").rglob("*.py")
    )
    offenders = [
        path.name
        for path in engine_files
        if "ui.personality" in path.read_text(encoding="utf-8")
        or "from ned.app.ui" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], offenders


# --------------------------------------------------------------------------- #
# Presentation polish: the action and the pair reading name what they compare
# --------------------------------------------------------------------------- #


def test_the_compare_button_names_the_evidence_not_the_reader() -> None:
    page = TEMPLATE.read_text(encoding="utf-8")
    assert "Compare Evidence Standards" not in page
    assert re.search(r'id="asym-submit"[^>]*>Compare Evidence<', page)


def test_the_compare_hint_is_short_and_does_not_default_to_blaming_the_reader() -> None:
    page = TEMPLATE.read_text(encoding="utf-8")
    panel = page.split('id="panel-asymmetry"', 1)[1].split('id="panel-lab"', 1)[0]
    match = re.search(r'<p class="hint">(.*?)</p>', panel, re.DOTALL)
    assert match is not None
    hint = match.group(1)
    assert "the evidence first" in hint
    assert "only judges your reasoning if you actually state it" in hint
    for banned in ("asymmetric", "your standard looks uneven", "double standard"):
        assert banned not in hint.lower(), banned


def test_the_pair_quality_row_labels_both_sides_in_the_markup(structure: _Structure) -> None:
    """Label and value must be siblings, or the reading is ambiguous on screen."""

    for side, label_id, value_id in (
        ("positive", "asym-quality-side-positive", "asym-screen-quality-positive"),
        ("negative", "asym-quality-side-negative", "asym-screen-quality-negative"),
    ):
        wrapper = structure.by_id[f"asym-quality-pair-{side}"]
        assert contains(wrapper, label_id), (side, label_id)
        assert contains(wrapper, value_id), (side, value_id)

    row = structure.by_id["asym-screen-quality-row"]
    assert contains(row, "asym-quality-pair-positive")
    assert contains(row, "asym-quality-pair-negative")
    first = structure.by_id["asym-first-screen"]
    assert contains(first, "asym-screen-quality-row")


def test_the_pair_quality_labels_are_data_in_both_languages() -> None:
    catalog = p.web_personality_catalog()
    assert catalog["pair_quality_labels"] == p.PAIR_QUALITY_LABELS
    assert p.pair_quality_label("zh", "positive") == "正向："
    assert p.pair_quality_label("zh", "negative") == "负向："
    assert p.pair_quality_label("en", "positive") == "POSITIVE "
    assert p.pair_quality_label("en", "negative") == "NEGATIVE "


def test_the_polish_did_not_move_any_reading(analyzer: NedAnalyzer) -> None:
    """The side labels are display only: the quality mapping is untouched."""

    result = analyzer.asymmetry.compare(
        positive_text=TIMELINE_POSITIVE, negative_text=TIMELINE_NEGATIVE
    )
    profile = result.evidence_profile
    assert p.quality_label(profile.positive_raw_strength) == "很强"
    assert profile.negative_class == "boundary"
    assert p.explicit_quality_label() == "明确"


def test_the_timeline_boundary_copy_is_locked() -> None:
    """This screen is canonical: the three lines and the title do not move."""

    screen = p.first_screen(p.SITUATION_TIMELINE_BOUNDARY, "normal", "zh")
    assert screen.title == "TWO FACTS, ONE TIMELINE"
    assert screen.lines == (
        "前面的两个小时没有被历史删除。",
        "后面的边界也不是害羞。🚧",
        "今天这题不允许拿计算器硬算。",
    )
    blob = " ".join([screen.title, *screen.lines, screen.reality])
    assert "🤠" not in blob and "👍" not in blob


def test_the_boundary_reality_check_already_respects_the_boundary(analyzer: NedAnalyzer) -> None:
    """Checked, not rewritten: the engine text must already say the boundary counts."""

    result = analyzer.asymmetry.compare(
        positive_text=TIMELINE_POSITIVE, negative_text=TIMELINE_NEGATIVE
    )
    assert "明确边界应当被尊重" in result.reality_check
    screen = p.first_screen(p.SITUATION_TIMELINE_BOUNDARY, "normal", "zh")
    assert "时间点" in screen.reality


def test_the_boundary_screen_still_has_no_joke_emoji(structure: _Structure) -> None:
    screen = p.first_screen(p.SITUATION_TIMELINE_BOUNDARY, "normal", "zh")
    blob = " ".join([screen.title, *screen.lines, screen.reality])
    assert "🤠" not in blob
    assert structure.by_id["asym-technical-details"]["open"] is False


def test_the_shipped_rule_is_untouched_by_the_attribution_fix() -> None:
    """Only the displayed sentence changed: the rule, its trigger and its priority did not."""

    pack = json.loads((RULES / "verdicts.json").read_text(encoding="utf-8"))
    rules = {rule["id"]: rule for rule in pack["rules"] if "id" in rule}
    rule = rules["nea.you_started_again"]
    assert rule["priority"] == 25
    assert "你又开始了" in rule["texts"]["zh"]
    assert "negative_amplification" in json.dumps(rule["when"], ensure_ascii=False)
    override = p.VERDICT_DISPLAY_OVERRIDES["nea.you_started_again"]["without_basis"]
    assert override["zh"] != rule["texts"]["zh"]
    assert "你又开始了" not in override["zh"]
