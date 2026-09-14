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
from ned.app.cli import screen_context, screen_fact
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
    """The screen a result gets, promotion included.

    This mirrors the shared contract in ``personality.screen_situation``: the
    verdict names the base screen, and the reader's own discount of real positive
    evidence promotes the generic positive screen to its own.
    """

    signal_types = [span.signal_type.value for span in result.evidence]
    return p.screen_situation(
        p.resolve_situation(result.verdict.code),
        self_discount=any(item in p.SELF_DISCOUNT_SIGNAL_TYPES for item in signal_types),
        positive_evidence=any(span.polarity == "positive" for span in result.evidence),
    )


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


# --------------------------------------------------------------------------- #
# self_discount_positive: the reader has already done NED's job
# --------------------------------------------------------------------------- #

GENERIC_POSITIVE = "她说喜欢我"
SELF_DISCOUNT_POSITIVE = "她说喜欢我，她可能只是人好"
SELF_DISCOUNT_LONG = "她说爱我爱得死去活来，她可能只是人好"
SELF_DISCOUNT_BOUNDARY = "她说喜欢我，但后来让我别再联系她，可能只是人好"
SELF_DISCOUNT_HOSTILE = "她怒骂我，但我想也许只是人好"
SELF_DISCOUNT_ONLY = "可能只是人好"

SIGNED_OFF = "你已经会用了"


def screen_for(result: Any, *, basis: bool | None = None) -> Any:
    """The first screen a result actually gets, promotion included."""

    resolved = basis_of(result) if basis is None else basis
    return p.first_screen(situation_of(result), result.mode, "zh", basis=resolved)


def test_a_plain_affection_stays_a_generic_positive(analyzer: NedAnalyzer) -> None:
    """A. no self-discount, no promotion."""

    result = analyzer.analyze_text(GENERIC_POSITIVE, mode="normal")
    assert situation_of(result) == p.SITUATION_POSITIVE
    blob = screen_for(result)
    text = " ".join([blob.title, *blob.lines, blob.reality])
    assert SIGNED_OFF not in text
    assert "申请人" not in text


def test_a_no_discount_is_reported_honestly(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(GENERIC_POSITIVE, mode="normal")
    assert not any(span.signal_type.value == "self_discount" for span in result.evidence)
    for mode in p.MODES:
        promoted = analyzer.analyze_text(GENERIC_POSITIVE, mode=mode)  # type: ignore[arg-type]
        assert situation_of(promoted) == p.SITUATION_POSITIVE, mode


@pytest.mark.parametrize("mode", p.MODES)
def test_b_a_self_discount_is_answered_as_such(analyzer: NedAnalyzer, mode: str) -> None:
    """B. the discount the reader wrote is the joke NED answers."""

    result = analyzer.analyze_text(SELF_DISCOUNT_POSITIVE, mode=mode)  # type: ignore[arg-type]
    assert basis_of(result) is True
    assert situation_of(result) == p.SITUATION_SELF_DISCOUNT_POSITIVE
    screen = screen_for(result)
    assert screen.title != p.first_screen(p.SITUATION_POSITIVE, mode, "zh").title


def test_b_extreme_signs_the_application_off(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(SELF_DISCOUNT_POSITIVE, mode="extreme")
    _screen, text = screen_text(result, "extreme")
    assert SIGNED_OFF in text
    assert "👍" in text
    assert "你：可能只是人好。" in text


def test_c_the_evidence_reading_does_not_move(analyzer: NedAnalyzer) -> None:
    """C + D. the reader's discount is not evidence and changes no number."""

    plain = analyzer.analyze_text(GENERIC_POSITIVE, mode="normal")
    discounted = analyzer.analyze_text(SELF_DISCOUNT_POSITIVE, mode="normal")
    assert discounted.signal_strength == plain.signal_strength
    assert discounted.verdict.code == plain.verdict.code
    assert discounted.positive_evidence_discount == plain.positive_evidence_discount
    assert discounted.ned_reaching_level == plain.ned_reaching_level

    def scoring(evidence: Any) -> list[tuple[str, str, str, float, float]]:
        return [
            (
                span.rule_id,
                span.signal_type.value,
                span.polarity,
                span.base_strength,
                span.information_content,
            )
            for span in evidence
            if span.polarity == "positive"
        ]

    assert scoring(discounted.evidence) == scoring(plain.evidence)
    discount_span = next(span for span in discounted.evidence if span.polarity == "self_discount")
    assert discount_span.signal_type.value == "self_discount"
    assert discount_span.rule_id == "zh.self_discount"


def test_c_the_evidence_and_the_interpretation_stay_separate(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(SELF_DISCOUNT_POSITIVE, mode="normal")
    polarities = {span.polarity for span in result.evidence}
    assert polarities == {"positive", "self_discount"}
    assert result.signal_type.value == "explicit_affection", "the primary signal is the evidence"
    weight = next(span for span in result.evidence if span.polarity == "positive").base_strength
    assert result.signal_strength == weight, "the discount moved the headline number"

    # the pair layer reports the same reading when a pair exists, and it is the
    # reader's layer that carries it, never the evidence layer
    paired = analyzer.analyze_text(SELF_DISCOUNT_BOUNDARY, mode="normal")
    assert paired.asymmetry is not None
    reading = paired.asymmetry.user_interpretation
    assert reading.positive_self_discount_present is True
    assert reading.positive_reading == "可能只是人好"


def test_e_a_boundary_outranks_the_discount(analyzer: NedAnalyzer) -> None:
    """E. the reader's joke never gets to swallow an explicit boundary."""

    result = analyzer.analyze_text(SELF_DISCOUNT_BOUNDARY, mode="normal")
    assert result.verdict.code == "ned.direct_rejection"
    assert situation_of(result) == p.SITUATION_BOUNDARY
    blob = screen_for(result)
    text = " ".join([blob.title, *blob.lines, blob.reality])
    assert SIGNED_OFF not in text
    assert "👍" not in text and "🤠" not in text
    assert "申请人" not in text
    assert "NED 停止狡辩" in text
    shown = p.emoji_discipline(situation_of(result), result.verdict.text)
    assert "🤠" not in shown and "👍" not in shown


def test_e_the_boundary_case_is_the_same_in_every_mode(analyzer: NedAnalyzer) -> None:
    situations = {
        mode: situation_of(analyzer.analyze_text(SELF_DISCOUNT_BOUNDARY, mode=mode))  # type: ignore[arg-type]
        for mode in p.MODES
    }
    assert set(situations.values()) == {p.SITUATION_BOUNDARY}, situations


def test_f_hostility_outranks_the_discount(analyzer: NedAnalyzer) -> None:
    """F. a hostile expression is never answered with the self-service joke."""

    result = analyzer.analyze_text(SELF_DISCOUNT_HOSTILE, mode="normal")
    assert result.verdict.code == "nea.hostile_expression_insufficient"
    assert situation_of(result) == p.SITUATION_HOSTILE
    blob = screen_for(result)
    text = " ".join([blob.title, *blob.lines, blob.reality])
    assert SIGNED_OFF not in text
    assert "申请人" not in text
    assert "敌意" in text


def test_f_hostility_keeps_its_own_screen_in_every_mode(analyzer: NedAnalyzer) -> None:
    situations = {
        mode: situation_of(analyzer.analyze_text(SELF_DISCOUNT_HOSTILE, mode=mode))  # type: ignore[arg-type]
        for mode in p.MODES
    }
    assert set(situations.values()) == {p.SITUATION_HOSTILE}, situations


def test_g_the_three_modes_say_different_things(analyzer: NedAnalyzer) -> None:
    """G. the same discount, three registers."""

    screens = {}
    for mode in p.MODES:
        result = analyzer.analyze_text(SELF_DISCOUNT_POSITIVE, mode=mode)  # type: ignore[arg-type]
        screen = screen_for(result)
        screens[mode] = (screen.title, *screen.lines)
    assert len(set(screens.values())) == 3, screens
    assert screens["normal"][0] == "SELF-DISCOUNT RECEIVED"
    assert screens["scientific"][0] == "REVIEWER COMMENT RECEIVED"
    assert screens["extreme"][0] == "SELF-SERVICE DENIAL"


def test_g_the_long_input_gets_the_same_screen(analyzer: NedAnalyzer) -> None:
    """The reported case: strong declaration plus the reader's own discount."""

    result = analyzer.analyze_text(SELF_DISCOUNT_LONG, mode="extreme")
    assert situation_of(result) == p.SITUATION_SELF_DISCOUNT_POSITIVE
    screen = screen_for(result)
    assert SIGNED_OFF in " ".join(screen.lines)
    assert len(screen.lines) == 3


def test_h_the_web_and_the_cli_read_one_source(client: TestClient) -> None:
    """H. the same promotion rule ships to both surfaces."""

    catalog = p.web_personality_catalog()
    assert catalog["self_discount_signal_types"] == list(p.SELF_DISCOUNT_SIGNAL_TYPES)
    assert catalog["self_discount_promotes"] == list(p.SELF_DISCOUNT_PROMOTES)
    assert p.SITUATION_SELF_DISCOUNT_POSITIVE in catalog["first_screen"]
    page = client.get("/").text
    match = re.search(r'<script id="personality-catalog"[^>]*>(.*?)</script>', page, re.DOTALL)
    assert match is not None
    assert (
        json.loads(match.group(1))["first_screen"][p.SITUATION_SELF_DISCOUNT_POSITIVE]
        == (p.web_personality_catalog()["first_screen"][p.SITUATION_SELF_DISCOUNT_POSITIVE])
    )
    script = (ROOT / "ned" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert "self_discount_promotes" in script


def test_h_the_cli_context_agrees_with_the_shared_rule(analyzer: NedAnalyzer) -> None:
    """The CLI surface and the catalogue must promote exactly the same cases."""

    from ned.app.cli import screen_context

    for text, mode in (
        (GENERIC_POSITIVE, "normal"),
        (SELF_DISCOUNT_POSITIVE, "normal"),
        (SELF_DISCOUNT_POSITIVE, "extreme"),
        (SELF_DISCOUNT_BOUNDARY, "normal"),
        (SELF_DISCOUNT_HOSTILE, "normal"),
        (SELF_DISCOUNT_ONLY, "normal"),
    ):
        result = analyzer.analyze_text(text, mode=mode)  # type: ignore[arg-type]
        assert screen_context(result)[0] == situation_of(result), (text, mode)


def test_h_the_cli_prints_the_promoted_screen(analyzer: NedAnalyzer) -> None:
    result = runner.invoke(cli_app, ["analyze", SELF_DISCOUNT_POSITIVE, "--mode", "extreme"])
    assert result.exit_code == 0
    assert "SELF-SERVICE DENIAL" in result.stdout
    assert SIGNED_OFF in result.stdout


def test_i_the_first_screen_never_shows_a_basis_field_name(analyzer: NedAnalyzer) -> None:
    """I. the joke must not leak the machinery that produced it."""

    for text in (SELF_DISCOUNT_POSITIVE, SELF_DISCOUNT_BOUNDARY, SELF_DISCOUNT_HOSTILE):
        for mode in p.MODES:
            result = analyzer.analyze_text(text, mode=mode)  # type: ignore[arg-type]
            blob = screen_for(result)
            shown = " ".join([blob.title, *blob.lines, blob.reality])
            for field in (*INTERNAL_FIELDS, "self_discount", "interpretive_basis", "basis"):
                assert field not in shown, (text, mode, field)


def test_j_the_promotion_cannot_fire_without_the_basis(analyzer: NedAnalyzer) -> None:
    """J. no discount in the text, no self-service screen."""

    for text in (GENERIC_POSITIVE, SELF_DISCOUNT_ONLY, "她主动找我聊了两个小时"):
        for mode in p.MODES:
            result = analyzer.analyze_text(text, mode=mode)  # type: ignore[arg-type]
            promoted = situation_of(result)
            assert promoted != p.SITUATION_SELF_DISCOUNT_POSITIVE, (text, mode)
            blob = screen_for(result)
            shown = " ".join([blob.title, *blob.lines, blob.reality])
            assert SIGNED_OFF not in shown, (text, mode)


def test_j_the_rule_only_promotes_the_screens_it_names() -> None:
    """The promotion is data, and it is allowed on two screens, for two reasons.

    ``positive`` is promoted because the discount deserves its own answer.
    ``self_discount_only`` is corrected because that screen asserts there is no
    positive evidence, and here there is.
    """

    assert p.SELF_DISCOUNT_PROMOTES == (p.SITUATION_POSITIVE,)
    promotable = {p.SITUATION_POSITIVE, p.SITUATION_SELF_DISCOUNT_ONLY}
    for base in p.FIRST_SCREEN:
        promoted = p.screen_situation(base, self_discount=True, positive_evidence=True)
        expected = p.SITUATION_SELF_DISCOUNT_POSITIVE if base in promotable else base
        assert promoted == expected, base


def test_j_the_rule_never_fires_without_both_conditions() -> None:
    base = p.SITUATION_POSITIVE
    assert p.screen_situation(base, self_discount=False, positive_evidence=True) == base
    assert p.screen_situation(base, self_discount=True, positive_evidence=False) == base
    assert (
        p.screen_situation(base, self_discount=True, positive_evidence=True)
        == p.SITUATION_SELF_DISCOUNT_POSITIVE
    )


def test_the_self_service_joke_attacks_the_discount_not_the_reader() -> None:
    """The line may not claim she likes you, or that you are deluded."""

    for language in ("zh", "en"):
        for mode in p.MODES:
            screen = p.first_screen(p.SITUATION_SELF_DISCOUNT_POSITIVE, mode, language)
            shown = " ".join([screen.title, *screen.lines, screen.reality])
            for banned in ("她一定", "她肯定", "她其实", "自欺", "骗自己", "已经确定", "结局"):
                assert banned not in shown, (language, mode, banned)


# --------------------------------------------------------------------------- #
# QA patch: the fact aligns with the screen, and a lone discount gets a screen
# --------------------------------------------------------------------------- #

MIXED_BOUNDARY = "她说喜欢我，但后来让我别再联系她"
MIXED_BOUNDARY_DISCOUNT = "她说喜欢我，但后来让我别再联系她，可能只是人好"
PLAIN_BOUNDARY = "她说别再联系我了。"
DISCOUNT_ONLY = "可能只是人好"


def cli_fact(result: Any) -> str:
    """The fact line exactly as the CLI composes it."""

    situation, _basis, _language = screen_context(result)
    return screen_fact(result, situation)


def test_a_a_lone_discount_gets_its_own_screen(analyzer: NedAnalyzer) -> None:
    """A. the only thing submitted was the rejection rationale."""

    result = analyzer.analyze_text(DISCOUNT_ONLY, mode="normal")
    assert result.verdict.code == "ned.self_discount_noted"
    assert situation_of(result) == p.SITUATION_SELF_DISCOUNT_ONLY
    screen = screen_for(result)
    blob = " ".join([screen.title, *screen.lines, screen.reality])
    assert screen.title == "SELF-DISCOUNT NOTED"
    assert "驳回理由已经提前准备好了。👍" in blob
    # the old landing was the generic comparison decline, which is off topic here
    assert "不足以支持一次对称比较" not in blob
    assert "不评估你的证据标准" not in blob
    assert "NO ADMISSIBLE COMPARISON" not in blob


@pytest.mark.parametrize("mode", p.MODES)
def test_a_the_lone_discount_speaks_in_all_three_registers(
    analyzer: NedAnalyzer, mode: str
) -> None:
    result = analyzer.analyze_text(DISCOUNT_ONLY, mode=mode)  # type: ignore[arg-type]
    screen = screen_for(result)
    titles = {
        "normal": "SELF-DISCOUNT NOTED",
        "scientific": "REVIEW COMMENT PRE-FILED",
        "extreme": "PREEMPTIVE DENIAL",
    }
    assert screen.title == titles[mode]
    assert len(screen.lines) >= 2


def test_a_the_lone_discount_never_invents_the_other_person(analyzer: NedAnalyzer) -> None:
    for mode in p.MODES:
        result = analyzer.analyze_text(DISCOUNT_ONLY, mode=mode)  # type: ignore[arg-type]
        screen = screen_for(result)
        blob = " ".join([screen.title, *screen.lines, screen.reality])
        for banned in ("她一定", "她肯定", "她其实", "她喜欢", "她不喜欢", "自欺", "骗自己"):
            assert banned not in blob, (mode, banned)


def test_b_a_discount_with_evidence_is_not_stolen_by_the_lone_discount(
    analyzer: NedAnalyzer,
) -> None:
    """B. positive evidence present, so it is the other screen."""

    result = analyzer.analyze_text(SELF_DISCOUNT_POSITIVE, mode="normal")
    assert situation_of(result) == p.SITUATION_SELF_DISCOUNT_POSITIVE
    assert situation_of(result) != p.SITUATION_SELF_DISCOUNT_ONLY
    blob = " ".join([screen_for(result).title, *screen_for(result).lines])
    assert "正向证据尚未提交" not in blob


def test_b_the_two_discount_screens_are_distinct_in_every_mode() -> None:
    for mode in p.MODES:
        only = p.first_screen(p.SITUATION_SELF_DISCOUNT_ONLY, mode, "zh")
        with_evidence = p.first_screen(p.SITUATION_SELF_DISCOUNT_POSITIVE, mode, "zh")
        assert only.title != with_evidence.title, mode
        assert only.lines != with_evidence.lines, mode


def test_the_lone_discount_guard_holds_at_rule_level() -> None:
    """The invariant: a lone discount means no positive evidence."""

    assert (
        p.screen_situation(
            p.SITUATION_SELF_DISCOUNT_ONLY, self_discount=True, positive_evidence=True
        )
        == p.SITUATION_SELF_DISCOUNT_POSITIVE
    )
    assert (
        p.screen_situation(
            p.SITUATION_SELF_DISCOUNT_ONLY, self_discount=True, positive_evidence=False
        )
        == p.SITUATION_SELF_DISCOUNT_ONLY
    )
    assert p.SITUATION_BY_VERDICT["ned.self_discount_noted"] == p.SITUATION_SELF_DISCOUNT_ONLY


def test_c_the_boundary_fact_describes_the_boundary(analyzer: NedAnalyzer) -> None:
    """C. the screen is about the boundary, so the fact must be too."""

    result = analyzer.analyze_text(MIXED_BOUNDARY, mode="normal")
    assert result.verdict.code == "ned.direct_rejection"
    assert situation_of(result) == p.SITUATION_BOUNDARY
    fact = cli_fact(result)
    assert "拒绝" in fact or "边界" in fact, fact
    assert fact == "明确拒绝 / 边界表达"


def test_c_the_positive_evidence_is_still_in_technical_details(analyzer: NedAnalyzer) -> None:
    """The mixed input keeps every span; only the headline moved."""

    result = analyzer.analyze_text(MIXED_BOUNDARY, mode="normal")
    kinds = [span.signal_type.value for span in result.evidence]
    assert "direct_rejection" in kinds
    assert "explicit_affection" in kinds
    positives = [span for span in result.evidence if span.polarity == "positive"]
    assert positives and positives[0].information_content > 0


def test_c_a_plain_boundary_keeps_its_richer_sentence(analyzer: NedAnalyzer) -> None:
    """No regression: when the boundary already leads, nothing is rewritten."""

    result = analyzer.analyze_text(PLAIN_BOUNDARY, mode="normal")
    assert cli_fact(result) == result.raw_interpretation
    assert cli_fact(result) == "对方直接、明确地表达了拒绝或边界。"


def test_c_the_boundary_copy_is_untouched_by_the_fact_change(analyzer: NedAnalyzer) -> None:
    for text in (PLAIN_BOUNDARY, MIXED_BOUNDARY, MIXED_BOUNDARY_DISCOUNT):
        for mode in p.MODES:
            result = analyzer.analyze_text(text, mode=mode)  # type: ignore[arg-type]
            assert situation_of(result) == p.SITUATION_BOUNDARY, (text, mode)
            screen = screen_for(result)
            assert screen.title == "EXPLICIT BOUNDARY 🚧"
            assert screen.lines == (
                "明确边界。NED 停止狡辩。🚧",
                "不确定性，不等于否认明确证据。",
            )
            assert screen.reality == "说出口的边界是一个行为，不是推断。NED 不对这条证据降权。"


def test_c_the_boundary_screen_still_refuses_to_joke(analyzer: NedAnalyzer) -> None:
    for text in (MIXED_BOUNDARY, MIXED_BOUNDARY_DISCOUNT):
        result = analyzer.analyze_text(text, mode="normal")
        screen = screen_for(result)
        blob = " ".join([screen.title, *screen.lines, screen.reality])
        assert "👍" not in blob and "🤠" not in blob
        shown = p.emoji_discipline(p.SITUATION_BOUNDARY, result.verdict.text)
        assert "👍" not in shown and "🤠" not in shown


def test_d_a_hostile_screen_shows_the_hostility(analyzer: NedAnalyzer) -> None:
    """D. the same rule on the hostile rung."""

    result = analyzer.analyze_text(SELF_DISCOUNT_HOSTILE, mode="normal")
    assert situation_of(result) == p.SITUATION_HOSTILE
    assert "敌意" in cli_fact(result)
    assert situation_of(result) != p.SITUATION_SELF_DISCOUNT_ONLY


def test_d_the_rule_says_which_evidence_decides_which_screen() -> None:
    assert p.fact_signal_types(p.SITUATION_BOUNDARY) == ("direct_rejection",)
    assert p.fact_signal_types(p.SITUATION_HOSTILE) == ("hostile_expression",)
    for situation in p.FIRST_SCREEN:
        if situation not in p.FACT_SIGNAL_TYPES:
            assert p.fact_signal_types(situation) == ()


def test_e_a_lone_discount_creates_no_evidence(analyzer: NedAnalyzer) -> None:
    """E. no external positive evidence may appear out of nowhere."""

    result = analyzer.analyze_text(DISCOUNT_ONLY, mode="normal")
    assert [span.signal_type.value for span in result.evidence] == ["self_discount"]
    assert not any(span.polarity == "positive" for span in result.evidence)
    assert result.signal_strength == 0.0
    assert (
        result.asymmetry is None or result.asymmetry.evidence_profile.negative_raw_strength is None
    )


def test_f_the_web_and_the_cli_share_the_fact_rule(client: TestClient) -> None:
    """F. one source for the screen, the fact and the promotion."""

    catalog = p.web_personality_catalog()
    assert catalog["fact_signal_types"] == {
        key: list(value) for key, value in p.FACT_SIGNAL_TYPES.items()
    }
    assert p.SITUATION_SELF_DISCOUNT_ONLY in catalog["first_screen"]
    page = client.get("/").text
    match = re.search(r'<script id="personality-catalog"[^>]*>(.*?)</script>', page, re.DOTALL)
    assert match is not None
    embedded = json.loads(match.group(1))
    assert embedded["fact_signal_types"] == catalog["fact_signal_types"]
    assert (
        embedded["first_screen"][p.SITUATION_SELF_DISCOUNT_ONLY]
        == (catalog["first_screen"][p.SITUATION_SELF_DISCOUNT_ONLY])
    )
    script = (ROOT / "ned" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert "fact_signal_types" in script


def test_f_the_cli_prints_the_lone_discount_screen() -> None:
    result = runner.invoke(cli_app, ["analyze", DISCOUNT_ONLY, "--mode", "extreme"])
    assert result.exit_code == 0
    assert "PREEMPTIVE DENIAL" in result.stdout
    assert "你甚至还没提交正向证据。" in result.stdout
    assert "「人好」已经在等着了。👍" in result.stdout


def test_g_technical_details_is_still_collapsed(structure: _Structure) -> None:
    assert structure.by_id["technical-details"]["open"] is False
    assert structure.by_id["asym-technical-details"]["open"] is False


def test_the_generic_positive_fact_is_unaffected(analyzer: NedAnalyzer) -> None:
    """The fact rule may not touch screens it does not name."""

    for text, expected in (
        (GENERIC_POSITIVE, "对方据称表达了喜欢（转述）。"),
        ("她主动找我聊了两个小时", "双方进行了持续时间较长的互动。"),
        ("她就回了一个嗯。", "对方的回复被描述为简短或冷淡。"),
    ):
        result = analyzer.analyze_text(text, mode="normal")
        assert cli_fact(result) == result.raw_interpretation == expected, text


# --------------------------------------------------------------------------- #
# Phase 1: latency presentation safety, and no_signal may not overclaim
# --------------------------------------------------------------------------- #

LATENCY_LONG = "他今天一整天都没回我消息"
LATENCY_NO_DURATION = "没回我消息"
LATENCY_CANONICAL = "五分钟没回复"
LATENCY_DEMO = "消息发出去五分钟没回复。"
NEUTRAL_INPUT = "今天天气真好"
UNRECOGNISED_INPUT = "我表白了，被拒绝了"

#: What a user must never see on a latency screen, whatever the input.
BROKEN_DURATION_TOKENS = ("—未回复", "—未有回复", "— 未回复", "— 未有回复", "— without a reply")


def shown_strings(result: Any) -> tuple[str, ...]:
    """Every engine string a screen would put in front of a user."""

    situation, _basis, language = screen_context(result)
    screen = p.first_screen(situation, "normal", language)
    return (
        screen.title,
        *screen.lines,
        screen.reality,
        screen_fact(result, situation),
        p.repair_display_text(result.verdict.text),
        p.repair_display_text(result.reality_check),
        p.repair_display_text(result.raw_interpretation),
    )


def test_a_a_long_silence_never_claims_a_short_one(analyzer: NedAnalyzer) -> None:
    """A. the reported defect: an all-day silence rendered as five minutes."""

    result = analyzer.analyze_text(LATENCY_LONG, mode="normal")
    assert result.verdict.code == "nea.latency_insufficient"
    shown = shown_strings(result)
    for token in (*BROKEN_DURATION_TOKENS, "短时间", "五分钟", "5 分钟", "short interval"):
        assert not any(token in item for item in shown), token


def test_a_a_long_silence_states_an_observation_not_a_verdict(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(LATENCY_LONG, mode="normal")
    screen = screen_for(result)
    assert screen.title == "ADVERSE PRELIMINARY RULING"
    assert "终审庭" in " ".join(screen.lines)
    assert "时长与上下文" in screen.reality


@pytest.mark.parametrize("text", [LATENCY_LONG, LATENCY_NO_DURATION, "昨晚到现在没回", "no reply"])
def test_c_no_input_produces_a_broken_duration_slot(analyzer: NedAnalyzer, text: str) -> None:
    """C. the placeholder must never reach the screen, in either language."""

    result = analyzer.analyze_text(text, mode="normal")
    if result.verdict.code != "nea.latency_insufficient":
        return
    shown = shown_strings(result)
    for token in BROKEN_DURATION_TOKENS:
        assert not any(token in item for item in shown), (text, token)
    repaired = p.repair_display_text(result.reality_check)
    if result.language == "en":
        assert "one unanswered message" in repaired, text
    else:
        assert "只有一次未回复" in repaired, text


def test_c_the_fact_comes_from_the_neutral_reading(analyzer: NedAnalyzer) -> None:
    """The engine's latency sentence always says "a short interval"; it is not usable."""

    for text in (LATENCY_LONG, LATENCY_NO_DURATION):
        result = analyzer.analyze_text(text, mode="normal")
        situation, _basis, _language = screen_context(result)
        fact = screen_fact(result, situation)
        assert fact == result.observed_evidence or fact == result.signal_label, text
        assert "短时间" not in fact, text


def test_b_the_canonical_five_minute_case_is_untouched(analyzer: NedAnalyzer) -> None:
    """B. the approved demo screen keeps its two lines and its engine reading."""

    result = analyzer.analyze_text(LATENCY_DEMO, mode="normal")
    screen = screen_for(result)
    assert screen.title == "ADVERSE PRELIMINARY RULING"
    assert screen.lines == ("坏消息信息量：有限。", "关系终审庭已经擅自开庭。👍")
    assert "5 分钟" in p.repair_display_text(result.verdict.text)
    assert "5 分钟" in p.repair_display_text(result.reality_check)
    assert p.has_missing_duration(result.verdict.text) is False


def test_the_repair_table_is_case_insensitive_and_targeted() -> None:
    """Shipped sentences start with a capital; the repair must still match."""

    assert p.repair_display_text("Reject. — without a reply is not evidence. 👍") == (
        "Reject. one unanswered message is not evidence. 👍"
    )
    assert p.repair_display_text("The only datum is — without a reply.") == (
        "The only datum is one unanswered message."
    )
    assert p.repair_display_text("That is not bad news; it is simply no news.") == (
        "That is not bad news; NED simply had no classification for it."
    )
    assert p.repair_display_text("The sender has not replied within a short interval.") == (
        "A reply delay has been recorded."
    )
    # ordinary copy passes through untouched
    for text in (
        "好消息已送外审；坏消息编辑部直录。",
        "明确边界。NED 停止狡辩。🚧",
        "Reject. 5 分钟未回复不构成证据。👍",
    ):
        assert p.repair_display_text(text) == text


def test_the_repair_never_touches_user_text(analyzer: NedAnalyzer) -> None:
    """Only engine strings are repaired: the input is never rewritten."""

    text = "他说 —未回复 — 未有回复 短时间 五分钟"
    result = analyzer.analyze_text(text, mode="normal")
    assert result.input == text

    script = (ROOT / "ned" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert "repairDisplayText(d.reality_check)" in script
    assert "repairDisplayText(d.raw_interpretation)" in script
    assert "repairDisplayText(d.input)" not in script


# --------------------------------------------------------------------------- #
# no_signal: NED may report its own blind spot, never the reader's emptiness
# --------------------------------------------------------------------------- #

OVERRCLAIM = "这不是坏消息，只是没有消息。"
CAPABILITY = "当前支持的信号类型"


@pytest.mark.parametrize(
    "text", [NEUTRAL_INPUT, UNRECOGNISED_INPUT, "他把我微信删了", "她说她需要一点空间"]
)
def test_d_a_the_fallback_screen_names_neds_own_limit(analyzer: NedAnalyzer, text: str) -> None:
    """D + E + F. One honest fallback for both genuinely empty and unrecognised input."""

    result = analyzer.analyze_text(text, mode="normal")
    assert result.verdict.code == "ned.no_signal", text
    screen = screen_for(result)
    blob = " ".join([screen.title, *screen.lines, screen.reality])
    assert screen.title == "MATERIALS RECEIVED"
    assert "不知道该送哪个窗口" in blob
    assert CAPABILITY in blob
    assert "不代表输入本身没有意义" in blob
    assert OVERRCLAIM not in blob


def test_e_the_overclaim_is_repaired_in_technical_details_too(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(UNRECOGNISED_INPUT, mode="normal")
    repaired = p.repair_display_text(result.reality_check)
    assert OVERRCLAIM not in repaired
    assert "没有可解释的分类" in repaired
    assert p.repair_display_text(result.verdict.text) == result.verdict.text


def test_e_an_unrecognised_input_is_still_not_classified(analyzer: NedAnalyzer) -> None:
    """Phase 1 does not implement coverage: the input stays unsupported, honestly."""

    result = analyzer.analyze_text(UNRECOGNISED_INPUT, mode="normal")
    assert result.evidence == []
    assert result.signal_strength == 0.0
    assert situation_of(result) == p.SITUATION_NO_SIGNAL


def test_d_the_fallback_is_the_same_in_every_mode() -> None:
    screens = {mode: p.first_screen(p.SITUATION_NO_SIGNAL, mode, "zh") for mode in p.MODES}
    assert screens["normal"] == screens["scientific"] == screens["extreme"]


def test_f_the_capability_safe_copy_ships_to_both_surfaces(client: TestClient) -> None:
    catalog = p.web_personality_catalog()
    assert p.SITUATION_NO_SIGNAL in catalog["first_screen"]
    page = client.get("/").text
    match = re.search(r'<script id="personality-catalog"[^>]*>(.*?)</script>', page, re.DOTALL)
    assert match is not None
    embedded = json.loads(match.group(1))
    assert embedded["display_repairs"] == catalog["display_repairs"]
    assert embedded["duration_artifacts"] == catalog["duration_artifacts"]
    assert embedded["fact_from_observed"] == [p.SITUATION_LATENCY]
    script = (ROOT / "ned" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert "display_repairs" in script and "fact_from_observed" in script


def test_g_the_engine_still_reports_what_it_reports(analyzer: NedAnalyzer) -> None:
    """G. the repairs are display-only: the payload keeps the engine's own strings."""

    result = analyzer.analyze_text(LATENCY_LONG, mode="normal")
    assert "—未回复" in result.verdict.text, "the engine string is untouched"
    assert "—未有回复" in result.reality_check
    assert result.raw_interpretation == "对方在短时间内没有回复。"

    no_signal = analyzer.analyze_text(UNRECOGNISED_INPUT, mode="normal")
    assert OVERRCLAIM in no_signal.reality_check


def test_h_technical_details_is_still_folded(structure: _Structure) -> None:
    assert structure.by_id["technical-details"]["open"] is False
    assert structure.by_id["asym-technical-details"]["open"] is False


# --------------------------------------------------------------------------- #
# Part A — quote fidelity: the quote is the reader's words, or there is none
# --------------------------------------------------------------------------- #

QUOTE_CASES = (
    ("她说喜欢我，可能只是人好", "可能只是人好"),
    ("她说喜欢我，可能只是出于礼貌", "可能只是出于礼貌"),
    ("她每天陪我聊天到很晚，我觉得可能只是习惯了", "可能只是习惯了"),
    ("她说喜欢我，她可能只是心软", "可能只是心软"),
    ("她说喜欢我，也许只是怕我难过", "也许只是怕我难过"),
)

REALITY_CLAIMS = ("证据是真的", "The evidence is real", "事实证明", "文本证明对方")


def reading_for(result: Any) -> str:
    """The same derivation the CLI and the web page use."""

    for span in result.evidence:
        if span.signal_type.value in p.SELF_DISCOUNT_SIGNAL_TYPES:
            found = p.captured_reading(result.input, span.start, span.end)
            if found:
                return found
    attached = result.asymmetry.user_interpretation if result.asymmetry is not None else None
    return attached.positive_reading if attached is not None and attached.positive_reading else ""


def screen_text(result: Any, mode: str | None = None) -> tuple[Any, str]:
    situation, basis, language = screen_context(result)
    resolved = mode or result.mode
    screen = p.first_screen(situation, resolved, language, basis=basis, reading=reading_for(result))
    return screen, " ".join([screen.title, *screen.lines, screen.reality])


@pytest.mark.parametrize(("text", "expected"), QUOTE_CASES)
def test_a2_the_quote_is_exactly_what_the_reader_wrote(
    analyzer: NedAnalyzer, text: str, expected: str
) -> None:
    result = analyzer.analyze_text(text, mode="extreme")
    _screen, blob = screen_text(result, "extreme")
    assert f"你：{expected}。" in blob, blob
    assert blob.count("你：") == 1


def test_a2_the_old_literal_is_not_quoted_back(analyzer: NedAnalyzer) -> None:
    """The defect: NED quoting a phrase the reader never wrote."""

    result = analyzer.analyze_text("她说喜欢我，可能只是出于礼貌", mode="extreme")
    _, blob = screen_text(result, "extreme")
    assert "你：可能只是出于礼貌。" in blob
    assert "你：可能只是人好。" not in blob


def test_a2_the_readers_own_words_survive_verbatim(analyzer: NedAnalyzer) -> None:
    """The quote is a substring of the input, not a paraphrase."""

    for text in ("她说喜欢我，可能只是出于礼貌", "她说喜欢我，她可能只是心软"):
        result = analyzer.analyze_text(text, mode="extreme")
        reading = reading_for(result)
        assert reading and reading in text, (text, reading)


def test_a2_a_truncated_reason_is_completed(analyzer: NedAnalyzer) -> None:
    """The engine's span ends at 习惯; the quote must not."""

    result = analyzer.analyze_text("她每天陪我聊天到很晚，我觉得可能只是习惯了", mode="extreme")
    assert reading_for(result) == "可能只是习惯了"


def test_a2_no_reading_means_no_quotation(analyzer: NedAnalyzer) -> None:
    """A screen that would have to invent a quote says it without one."""

    from ned.app.ui.personality import SITUATION_SELF_DISCOUNT_POSITIVE

    screen = p.first_screen(SITUATION_SELF_DISCOUNT_POSITIVE, "extreme", "zh", basis=True)
    forced = p.first_screen(
        SITUATION_SELF_DISCOUNT_POSITIVE, "extreme", "zh", basis=True, reading=""
    )
    assert forced.lines == screen.lines
    blob = " ".join(forced.lines)
    assert "你：" not in blob
    assert "降权理由也已经一并提交。" in blob
    assert "NED：很好，你已经会用了。👍" in blob


def test_a2_the_scientific_quote_is_dynamic_too(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她说喜欢我，可能只是出于礼貌", mode="scientific")
    _, blob = screen_text(result, "scientific")
    assert "审稿意见：可能只是出于礼貌。" in blob
    assert "审稿意见：可能只是人好。" not in blob


def test_a3_no_second_person_without_a_basis(analyzer: NedAnalyzer) -> None:
    """§A3: no basis, no user line."""

    for text in ("她说喜欢我", "她每天陪我聊天到很晚", "他主动约我周末看电影"):
        result = analyzer.analyze_text(text, mode="extreme")
        _, blob = screen_text(result, "extreme")
        assert "你：" not in blob, text


def test_a3_self_discount_only_needs_no_quote(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("可能只是在同情我", mode="extreme")
    assert situation_of(result) == p.SITUATION_SELF_DISCOUNT_ONLY
    _, blob = screen_text(result, "extreme")
    assert "你：" not in blob


def test_a3_boundary_and_hostile_still_win_with_a_discount_present(
    analyzer: NedAnalyzer,
) -> None:
    boundary = analyzer.analyze_text("我本来觉得可能只是人好，但她后来让我别再联系", mode="extreme")
    hostile = analyzer.analyze_text("她怒骂我，但我想也许只是人好", mode="extreme")
    assert situation_of(boundary) == p.SITUATION_BOUNDARY
    assert situation_of(hostile) == p.SITUATION_HOSTILE
    for result in (boundary, hostile):
        _, blob = screen_text(result, "extreme")
        assert "你：" not in blob
        assert "你已经会用了" not in blob


def test_a1_ned_never_claims_to_have_verified_reality() -> None:
    """No display copy may assert that the evidence is real."""

    catalog = p.web_personality_catalog()
    blob = json.dumps(catalog, ensure_ascii=False)
    for claim in REALITY_CLAIMS:
        assert claim not in blob, claim
    source = (ROOT / "ned" / "app" / "ui" / "personality.py").read_text(encoding="utf-8")
    for claim in REALITY_CLAIMS:
        assert claim not in source, claim


def test_a1_the_first_line_claims_strength_instead(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她说喜欢我，可能只是人好", mode="extreme")
    _, blob = screen_text(result, "extreme")
    assert "这条正向证据很强。" in blob


def test_a1_the_generic_positive_screen_reports_rather_than_certifies() -> None:
    screen = p.first_screen(p.SITUATION_POSITIVE, "normal", "zh")
    assert "输入里报告了正向证据" in screen.reality
    assert "证据是真的" not in screen.reality


def test_a4_the_bible_documents_the_dynamic_slot() -> None:
    bible = (ROOT / "docs" / "PERSONALITY_BIBLE.md").read_text(encoding="utf-8")
    assert "{captured_self_discount_reading}" in bible
    assert "证据是真的。" not in bible.split("## 5. Canonical Copy")[1].split("### 5.2")[0]
    assert "动态 quote slot" in bible


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
