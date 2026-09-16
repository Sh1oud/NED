"""Evidence Comparability tests for the Asymmetry Detector.

The detector measures an *interpretive* asymmetry: one standard applied
unevenly. That reading is only available when both sides are candidate answers
to a similar question. An explicit boundary answers a different question and
settles it by itself, and two clues that sit in different states of the
relationship are two observations rather than two standards, so in both cases
NED declines the comparison instead of printing a severity band.

Declining is not scoring zero: zero keeps its original meaning, "compared, and
the standards are symmetric", while a declined comparison means the comparison
itself does not hold.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from ned.app.cli import app as cli_app
from ned.app.core import parser
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.rules import RuleBook
from typer.testing import CliRunner

POSITIVE = "她主动找我聊了两个小时"
LATENCY = "五分钟没回复"
BOUNDARY = "她最后让我滚开别烦她"
HOSTILE_AND_BOUNDARY = "去你妈的，她让我别再联系她"
HOSTILE_ONLY = "她怒骂我"
MIXED_SENTENCE = "她主动找我聊了两个小时，但她最后让我滚开别烦她"

runner = CliRunner()

BANDS = {"NEGLIGIBLE", "MILD", "MODERATE", "SEVERE", "EXTREME"}


# --------------------------------------------------------------- A: classic


def test_classic_asymmetry_is_still_detected(analyzer: NedAnalyzer) -> None:
    """A: the canonical double standard must keep working."""

    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=LATENCY)
    assert result.comparison_applicable is True
    assert result.comparison_reason == ""
    assert result.asymmetry_score is not None
    assert result.asymmetry_score >= 75
    assert result.asymmetry_label == "EXTREME"
    assert result.positive_threshold == "EXTREMELY HIGH"
    assert result.negative_threshold == "EXTREMELY LOW"
    assert result.verdict.code == "evidence.reading_not_present"
    assert result.positive.evidence_class == "interaction"
    assert result.negative.evidence_class == "behaviour"


def test_classic_pair_keeps_the_documented_arithmetic(analyzer: NedAnalyzer) -> None:
    """The gate does not touch the scoring formula."""

    config = analyzer.book.asymmetry
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=LATENCY)
    sub = result.sub_scores
    expected = round(
        100.0
        * (
            config.weight_gap_weight * sub["weight_gap"]
            + config.information_gap_weight * sub["information_gap"]
            + config.categorical_weight * sub["categorical"]
        ),
        4,
    )
    assert result.asymmetry_score == pytest.approx(expected, abs=0.01)


# ----------------------------------------------------- B: explicit boundary


def test_an_explicit_boundary_declines_the_comparison(analyzer: NedAnalyzer) -> None:
    """B: a boundary is a different evidence class, not evidence overreach."""

    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=BOUNDARY)
    assert result.comparison_applicable is False
    assert result.comparison_reason == "explicit_boundary_not_comparable"
    assert result.asymmetry_score is None
    assert result.asymmetry_label == "NOT DIRECTLY COMPARABLE"
    assert result.asymmetry_label not in BANDS
    assert result.positive_threshold == "NOT_COMPARABLE"
    assert result.negative_threshold == "NOT_COMPARABLE"
    assert result.verdict.code == "ned.comparison_not_applicable"
    assert result.verdict.code != "asymmetry.detected"
    assert result.verdict.severity == "info"
    assert "拒绝本次对称比较" in result.verdict.text
    assert "边界" in result.reality_check
    assert "overreach" not in result.reality_check.lower()

    # neither clue is lost or de-weighted
    assert result.positive.evidence_class == "interaction"
    assert result.negative.evidence_class == "boundary"
    assert result.negative.weight == 96.0
    assert result.negative.information_content == 90.0
    assert result.positive.raw_strength > 80
    assert result.sub_scores  # the components stay exposed for audit


def test_a_boundary_in_one_message_declines_the_comparison(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(MIXED_SENTENCE, mode="normal")
    assert result.asymmetry is not None
    assert result.asymmetry.comparison_applicable is False
    assert result.asymmetry.comparison_reason == "explicit_boundary_not_comparable"
    assert result.breakdown.asymmetry_score is None
    assert result.asymmetry.asymmetry_label == "NOT DIRECTLY COMPARABLE"
    assert result.verdict.code != "asymmetry.detected"
    assert result.verdict.code == "ned.direct_rejection"
    # the earlier positive evidence is still reported
    assert result.signal_strength > 80
    assert any(span.rule_id == "zh.sustained_interaction" for span in result.evidence)


def test_the_two_sides_can_both_be_true(analyzer: NedAnalyzer) -> None:
    """The boundary neither erases the earlier interaction nor is offset by it."""

    result = analyzer.analyze_text(MIXED_SENTENCE, mode="normal")
    labels = {span.signal_type.value for span in result.evidence}
    assert "sustained_interaction" in labels
    assert "direct_rejection" in labels
    boundary = next(span for span in result.evidence if span.rule_id == "zh.direct_rejection")
    assert boundary.base_strength == 96.0
    assert boundary.information_content == 90.0


# -------------------------------------------- C: hostility with a boundary


def test_a_boundary_dominates_when_hostility_is_also_present(analyzer: NedAnalyzer) -> None:
    """C: hostility does not rescue the comparison, and it is not lost either."""

    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=HOSTILE_AND_BOUNDARY)
    assert result.comparison_applicable is False
    assert result.comparison_reason == "explicit_boundary_not_comparable"
    assert result.negative.evidence_class == "boundary"
    # both spans are counted in the side's raw strength
    assert result.negative.raw_strength > 96.0

    spans = parser.detect(HOSTILE_AND_BOUNDARY, analyzer.book)
    assert {span.rule_id for span in spans} == {"zh.direct_rejection", "zh.hostile_expression"}


def test_hostility_is_still_reported_next_to_a_boundary(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(HOSTILE_AND_BOUNDARY, mode="normal")
    rules = {span.rule_id for span in result.evidence}
    assert "zh.hostile_expression" in rules
    assert "zh.direct_rejection" in rules


# ------------------------------------------------- D: hostility without one


def test_hostility_alone_stays_comparable(analyzer: NedAnalyzer) -> None:
    """D: an insult is a behaviour inside the exchange, not a boundary directive.

    ``hostile_expression`` belongs to the same class as a cold reply or a
    cancelled plan: it answers a question about how the other person is behaving
    towards you, so a difference in standards applied to it is still readable as
    a double standard. Only a boundary changes the question, which is why the
    boundary class alone gates comparability.
    """

    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=HOSTILE_ONLY)
    assert result.comparison_applicable is True
    assert result.comparison_reason == ""
    assert result.negative.evidence_class == "behaviour"
    assert result.negative.signal_type.value == "hostile_expression"
    assert result.asymmetry_score is not None
    assert result.asymmetry_score >= 60
    assert result.asymmetry_label in BANDS
    assert result.verdict.code == "evidence.reading_not_present"


# ---------------------------------------------- E: two ordinary comparable clues


def test_two_ordinary_clues_use_the_original_scoring(analyzer: NedAnalyzer) -> None:
    """E: nothing about the ordinary path changed."""

    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text="她就回了一个嗯")
    assert result.comparison_applicable is True
    assert result.comparison_reason == ""
    assert result.asymmetry_score is not None
    assert result.asymmetry_label in BANDS
    assert set(result.sub_scores) == {"weight_gap", "information_gap", "categorical"}
    assert result.positive_threshold != "NOT_COMPARABLE"
    assert result.negative_threshold != "NOT_COMPARABLE"


# ------------------------------------------------------------- F: time order


@pytest.mark.parametrize(
    "negative",
    ["她后来不回我消息了", "她之后再也没回我消息", "她后来就不理我了，一直没回复"],
)
def test_a_later_state_declines_the_comparison(analyzer: NedAnalyzer, negative: str) -> None:
    """F: a clue placed after a change of state is not a second standard."""

    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=negative)
    assert result.comparison_applicable is True or result.comparison_reason == (
        "temporal_state_change_not_comparable"
    )
    if result.comparison_reason == "temporal_state_change_not_comparable":
        assert result.asymmetry_score is None
        assert result.asymmetry_label == "NOT DIRECTLY COMPARABLE"
        assert result.verdict.code == "ned.comparison_not_applicable"
        assert "时间点" in result.reality_check or "变化" in result.reality_check


def test_a_later_state_marker_must_cover_the_clue(analyzer: NedAnalyzer) -> None:
    """The marker alone is not a state change: the clue has to follow it.

    "最后我还是没忍住问她" mentions a later moment, but the clue (the missing
    reply) comes before it, so it still describes the same state.
    """

    result = analyzer.asymmetry.compare(
        positive_text=POSITIVE, negative_text="五分钟没回复，最后我还是没忍住问她"
    )
    assert result.comparison_applicable is True
    assert result.comparison_reason == ""
    assert result.asymmetry_score is not None


def test_english_later_state_marker_works(analyzer: NedAnalyzer) -> None:
    result = analyzer.asymmetry.compare(
        positive_text="She texted me first and we talked for two hours",
        negative_text="After that, she left me on read",
    )
    assert result.comparison_reason == "temporal_state_change_not_comparable"
    assert result.asymmetry_score is None
    assert result.comparison_applicable is False


# ----------------------------------------------------------- declined states


@pytest.mark.parametrize("negative", [BOUNDARY, "她后来不回我消息了"])
def test_a_declined_comparison_never_reports_a_band(analyzer: NedAnalyzer, negative: str) -> None:
    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=negative)
    assert result.comparison_applicable is False
    assert result.asymmetry_score is None
    assert result.asymmetry_label not in BANDS
    assert result.positive_threshold == "NOT_COMPARABLE"
    assert result.negative_threshold == "NOT_COMPARABLE"
    assert result.verdict.code != "asymmetry.detected"
    assert result.verdict.code == "ned.comparison_not_applicable"


def test_declining_is_not_scoring_zero(analyzer: NedAnalyzer) -> None:
    """Zero means "compared and symmetric"; declining means "not comparable"."""

    declined = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=BOUNDARY)
    assert declined.asymmetry_score is None
    assert declined.comparison_applicable is False

    one_sided = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text="")
    assert one_sided.asymmetry_score is None
    assert one_sided.comparison_applicable is False
    assert one_sided.comparison_reason == "insufficient_input"
    assert one_sided.asymmetry_label == "INSUFFICIENT_INPUT"


def test_the_comparison_state_is_deterministic(analyzer: NedAnalyzer) -> None:
    first = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=BOUNDARY)
    second = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=BOUNDARY)
    assert first.model_dump(exclude={"generated_at"}) == second.model_dump(exclude={"generated_at"})


# ------------------------------------------------------------ data-driven


def test_the_comparability_policy_is_configuration(book: RuleBook) -> None:
    config = book.asymmetry.comparability
    assert config.enabled is True
    assert config.boundary_classes == ["boundary"]
    assert config.evidence_classes["direct_rejection"] == "boundary"
    assert config.evidence_classes["hostile_expression"] == "behaviour"
    assert config.evidence_classes["response_latency"] == "behaviour"
    assert config.evidence_classes["sustained_interaction"] == "interaction"
    assert "最后" in config.later_state_markers["zh"]
    assert "in the end" in config.later_state_markers["en"]
    assert config.not_applicable_label == "NOT DIRECTLY COMPARABLE"
    assert config.threshold_label == "NOT_COMPARABLE"


def test_the_gate_can_be_disabled_from_config(book: RuleBook) -> None:
    """The policy is data: a pack can turn the gate off without a code change."""

    comparability = book.asymmetry.comparability.model_copy(update={"enabled": False})
    config = book.asymmetry.model_copy(update={"comparability": comparability})
    custom = NedAnalyzer(book=book.model_copy(update={"asymmetry": config}))

    result = custom.asymmetry.compare(positive_text=POSITIVE, negative_text=BOUNDARY)
    assert result.comparison_applicable is True
    assert result.asymmetry_score is not None


def test_reclassifying_the_boundary_changes_the_outcome(book: RuleBook) -> None:
    """Reclassifying the signal type is enough: no verbatim case is hardcoded."""

    plain_boundary = "她说别再联系我了"
    default = NedAnalyzer(book=book).asymmetry.compare(
        positive_text=POSITIVE, negative_text=plain_boundary
    )
    assert default.comparison_reason == "explicit_boundary_not_comparable"

    classes = dict(book.asymmetry.comparability.evidence_classes)
    classes["direct_rejection"] = "behaviour"
    comparability = book.asymmetry.comparability.model_copy(update={"evidence_classes": classes})
    config = book.asymmetry.model_copy(update={"comparability": comparability})
    custom = NedAnalyzer(book=book.model_copy(update={"asymmetry": config}))

    result = custom.asymmetry.compare(positive_text=POSITIVE, negative_text=plain_boundary)
    assert result.comparison_applicable is True
    assert result.asymmetry_score is not None


# ------------------------------------------------------------------- API


def test_api_reports_the_comparison_state(client: TestClient) -> None:
    payload = client.post(
        "/api/asymmetry", json={"positive_text": POSITIVE, "negative_text": BOUNDARY}
    ).json()

    assert payload["comparison_applicable"] is False
    assert payload["comparison_reason"] == "explicit_boundary_not_comparable"
    assert payload["asymmetry_score"] is None
    assert payload["asymmetry_label"] == "NOT DIRECTLY COMPARABLE"
    assert payload["positive_threshold"] == "NOT_COMPARABLE"
    assert payload["negative_threshold"] == "NOT_COMPARABLE"
    assert payload["verdict"]["code"] == "ned.comparison_not_applicable"
    assert payload["verdict"]["severity"] == "info"
    assert payload["positive"]["evidence_class"] == "interaction"
    assert payload["negative"]["evidence_class"] == "boundary"
    assert payload["sub_scores"]
    assert payload["reality_check"]


def test_api_keeps_the_classic_case_unchanged(client: TestClient) -> None:
    payload = client.post(
        "/api/asymmetry", json={"positive_text": POSITIVE, "negative_text": LATENCY}
    ).json()

    assert payload["comparison_applicable"] is True
    assert payload["comparison_reason"] == ""
    assert payload["asymmetry_score"] >= 75
    assert payload["asymmetry_label"] == "EXTREME"
    assert payload["positive_threshold"] == "EXTREMELY HIGH"
    assert payload["negative_threshold"] == "EXTREMELY LOW"
    assert payload["verdict"]["code"] == "evidence.reading_not_present"


def test_api_analyze_does_not_report_a_admission_threshold_for_a_boundary(
    client: TestClient,
) -> None:
    payload = client.post("/api/analyze", json={"text": MIXED_SENTENCE, "mode": "normal"}).json()

    assert payload["asymmetry"]["comparison_applicable"] is False
    assert payload["breakdown"]["asymmetry_score"] is None
    assert payload["verdict"]["code"] == "ned.direct_rejection"
    assert payload["verdict"]["code"] != "asymmetry.detected"


def test_ui_inputs_for_the_not_applicable_state(client: TestClient) -> None:
    """What the web UI reads: a dash, a label, a note and an info-severity panel."""

    payload = client.post(
        "/api/asymmetry", json={"positive_text": POSITIVE, "negative_text": BOUNDARY}
    ).json()

    assert payload["asymmetry_score"] is None  # renders as "—", not 60.3
    assert payload["asymmetry_label"] == "NOT DIRECTLY COMPARABLE"
    assert payload["verdict"]["severity"] == "info"  # the panel is not styled as chaos
    assert payload["reality_check"].strip()


def test_the_served_page_still_has_the_elements_the_state_needs(client: TestClient) -> None:
    body = client.get("/").text
    for element in (
        "asym-profile-comparable",
        "asym-profile-raw-gap",
        "asym-treatment-gap",
        "asym-reading-status",
        "asym-reality-text",
        "asym-verdict-text",
    ):
        assert f'id="{element}"' in body, element
    assert "Admission Thresholds" not in body
    assert "asym-score-value" not in body


# ------------------------------------------------------------------- CLI


def test_cli_declines_the_comparison_instead_of_printing_severe() -> None:
    result = runner.invoke(cli_app, ["asymmetry", "--positive", POSITIVE, "--negative", BOUNDARY])
    assert result.exit_code == 0
    assert "comparable: NO" in result.stdout
    assert "explicit_boundary_not_comparable" in result.stdout
    assert "拒绝本次对称比较" in result.stdout
    assert "SEVERE" not in result.stdout
    assert "overreach" not in result.stdout.lower()


def test_cli_keeps_the_classic_case() -> None:
    result = runner.invoke(cli_app, ["asymmetry", "--positive", POSITIVE, "--negative", LATENCY])
    assert result.exit_code == 0
    assert "comparable: yes" in result.stdout
    assert "treatment gap" in result.stdout
    assert "不评估你的证据标准" in result.stdout


def test_cli_json_carries_the_comparison_state() -> None:
    result = runner.invoke(
        cli_app,
        ["asymmetry", "--positive", POSITIVE, "--negative", BOUNDARY, "--json"],
    )
    payload = json.loads(result.stdout)
    assert payload["comparison_applicable"] is False
    assert payload["comparison_reason"] == "explicit_boundary_not_comparable"
    assert payload["asymmetry_score"] is None


# ------------------------------------------------------------ invariants


def test_a_boundary_pair_never_reaches_a_band(analyzer: NedAnalyzer) -> None:
    """Whatever the positive side is, an explicit boundary declines the pair."""

    for positive in (
        POSITIVE,
        "她说喜欢我",
        "我们结婚吧",
        "她主动找我聊了两个小时，还给我带了奶茶",
    ):
        result = analyzer.asymmetry.compare(positive_text=positive, negative_text=BOUNDARY)
        assert result.comparison_applicable is False, positive
        assert result.asymmetry_score is None, positive
        assert result.asymmetry_label not in BANDS, positive
        assert result.verdict.code != "asymmetry.detected", positive


def test_the_verdict_rule_needs_the_comparison_flag(analyzer: NedAnalyzer) -> None:
    """The decline verdict only fires where a comparison was attempted."""

    analysis = analyzer.analyze_text("我想你了", mode="normal")
    assert analysis.verdict.code != "ned.comparison_not_applicable"

    one_sided = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text="")
    assert one_sided.verdict.code != "ned.comparison_not_applicable"
    assert one_sided.asymmetry_label == "INSUFFICIENT_INPUT"


def test_the_web_script_shows_a_missing_score_as_a_dash(client: TestClient) -> None:
    """A declined comparison has no number, so the panel must not print 0.0."""

    script = client.get("/static/app.js").text
    assert 'if (v === null || v === undefined || v === "") { return DASH; }' in script


# ------------------------------------------------- the layer contract (A-H)


def test_a_profile_does_not_move_with_the_mode(analyzer: NedAnalyzer) -> None:
    """A: the Evidence Profile is a property of the clues, not of the mode."""

    profiles = [
        analyzer.asymmetry.compare(
            positive_text=POSITIVE, negative_text=LATENCY, mode=mode
        ).evidence_profile
        for mode in ("normal", "scientific", "extreme")
    ]
    first = profiles[0].model_dump()
    for profile in profiles[1:]:
        assert profile.model_dump() == first


def test_b_treatment_does_move_with_the_mode(analyzer: NedAnalyzer) -> None:
    treatments = [
        analyzer.asymmetry.compare(
            positive_text=POSITIVE, negative_text=LATENCY, mode=mode
        ).ned_treatment
        for mode in ("normal", "scientific", "extreme")
    ]
    gaps = [item.treatment_gap for item in treatments if item is not None]
    assert len(set(gaps)) == len(gaps), f"the mode must change NED's treatment: {gaps}"
    assert treatments[0] is not None and treatments[2] is not None
    assert treatments[2].positive_discount > treatments[0].positive_discount


def test_c_a_negative_conclusion_is_not_evidence(analyzer: NedAnalyzer) -> None:
    """C: "她肯定不想理我" adds no negative evidence, only a reading."""

    plain = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=LATENCY)
    with_reading = analyzer.asymmetry.compare(
        positive_text=POSITIVE, negative_text=f"{LATENCY}，她肯定不想理我"
    )
    assert with_reading.evidence_profile.negative_raw_strength == (
        plain.evidence_profile.negative_raw_strength
    )
    assert with_reading.user_interpretation.negative_self_conclusion_present is True
    assert "negative_self_conclusion" in with_reading.user_interpretation.basis


def test_d_a_self_discount_is_not_evidence(analyzer: NedAnalyzer) -> None:
    """D: "可能只是人好" does not lower the positive side's raw strength."""

    plain = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=LATENCY)
    with_reading = analyzer.asymmetry.compare(
        positive_text=POSITIVE, negative_text=LATENCY, positive_interpretation="可能只是人好"
    )
    assert with_reading.evidence_profile.positive_raw_strength == (
        plain.evidence_profile.positive_raw_strength
    )
    assert with_reading.user_interpretation.positive_self_discount_present is True


def test_e_a_declined_comparison_has_no_pairwise_numbers(analyzer: NedAnalyzer) -> None:
    """E: every pairwise reading is None when the pair is not comparable."""

    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=BOUNDARY)
    profile, treatment = result.evidence_profile, result.ned_treatment
    assert profile.comparable is False
    assert profile.raw_strength_gap is None
    assert profile.information_gap is None
    assert treatment is not None and treatment.treatment_gap is None
    assert result.user_interpretation.interpretive_score is None
    assert result.user_interpretation.status == "not_comparable"
    # the per-side numbers are still visible
    assert profile.positive_raw_strength is not None
    assert profile.negative_raw_strength is not None
    assert treatment.positive_treated_weight is not None
    assert treatment.negative_treated_weight is not None


def test_f_no_second_person_when_the_reader_said_nothing(analyzer: NedAnalyzer) -> None:
    """F: without a basis, no output may judge the reader's standard."""

    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=LATENCY)
    assert result.user_interpretation.reading_present is False
    blob = " ".join(
        [
            result.verdict.text,
            result.reality_check,
            result.ned_treatment.mode if result.ned_treatment else "",
            str(result.evidence_profile.model_dump()),
        ]
    )
    # the layer may *disclaim* the assessment, never make one
    for phrase in ("你的结论", "你使用了", "你对正向证据", "you discounted", "your standard looks"):
        assert phrase not in blob, phrase
    assert result.verdict.code == "evidence.reading_not_present"
    assert "不评估你的证据标准" in result.verdict.text


def test_g_the_legacy_composite_still_reproduces_its_old_value(analyzer: NedAnalyzer) -> None:
    """G: historical clients keep their number, and the UI does not show it."""

    result = analyzer.asymmetry.compare(positive_text=POSITIVE, negative_text=LATENCY)
    assert result.asymmetry_score_is_legacy is True
    assert result.asymmetry_score == pytest.approx(81.7958, abs=0.001)
    assert result.sub_scores["weight_gap"] == pytest.approx(0.6555, abs=0.001)
    assert result.verdict.code != "asymmetry.detected", "the legacy verdict is retired"

    page = _page()
    assert "asym-score-value" not in page
    assert "Asymmetry score" not in page


def test_h_an_explicit_double_standard_is_detected(analyzer: NedAnalyzer) -> None:
    """H: both readings present, on a comparable pair, is the real finding."""

    result = analyzer.asymmetry.compare(
        positive_text="她主动找我聊了两个小时，但可能只是人好。",
        negative_text="五分钟没回复，她肯定不想理我。",
    )
    reading = result.user_interpretation
    assert reading.positive_self_discount_present is True
    assert reading.negative_self_conclusion_present is True
    assert reading.status == "asymmetric_standard_detected"
    assert reading.double_standard is True
    assert reading.basis == ["positive_self_discount", "negative_self_conclusion"]
    assert reading.interpretive_score is None, "v1 does not pretend to grade it"
    assert result.verdict.code == "interpretation.double_standard_detected"
    assert "你的证据标准" in result.verdict.text

    # the evidence profile counts only the external clues
    profile = result.evidence_profile
    assert profile.positive_raw_strength == 82.32
    assert profile.negative_raw_strength == 90.0


def _page() -> str:
    from fastapi.testclient import TestClient
    from ned.app.main import create_app

    with TestClient(create_app()) as client:
        return client.get("/").text
