"""REST API tests (run against the real FastAPI app, no network)."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient
from ned.app.version import __version__


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == __version__
    assert payload["local_only"] is True
    assert payload["uptime_seconds"] >= 0
    assert payload["engine"] == "ned-local-rules"


def test_version(client: TestClient) -> None:
    response = client.get("/api/version")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "NED"
    assert payload["full_name"] == "Nov1ce Evidence Denier"
    assert payload["version"] == __version__
    assert payload["api_version"] == "1"
    assert payload["tagline"].startswith("When reality becomes suspiciously positive")
    assert payload["motto"].endswith("👍")


def test_modes(client: TestClient) -> None:
    payload = client.get("/api/modes").json()
    assert {mode["id"] for mode in payload} == {"normal", "scientific", "extreme"}


def test_examples(client: TestClient) -> None:
    payload = client.get("/api/examples").json()
    assert len(payload["cases"]) >= 8
    assert all({"id", "text", "mode"} <= set(case) for case in payload["cases"])


def test_providers(client: TestClient) -> None:
    payload = client.get("/api/providers").json()
    assert payload["available"] == ["llm", "local"]
    assert payload["active"] == "local"
    assert payload["offline"] is True


def test_rules_provenance(client: TestClient) -> None:
    payload = client.get("/api/rules").json()
    assert payload["signal_rules"] >= 30
    assert payload["verdict_rules"] >= 10
    assert payload["rules_version"]


def test_easter_eggs(client: TestClient) -> None:
    payload = client.get("/api/easter-eggs").json()
    assert payload["eggs"]
    assert "never change the verdict" in payload["note"]


@pytest.mark.parametrize("mode", ["normal", "scientific", "extreme"])
def test_analyze_all_modes(client: TestClient, mode: str) -> None:
    response = client.post("/api/analyze", json={"text": "我想你了", "mode": mode})
    assert response.status_code == 200
    payload = response.json()
    assert payload["input"] == "我想你了"
    assert payload["mode"] == mode
    assert payload["verdict"]["text"]
    assert payload["engine"]["provider"] == "local-rule"
    assert payload["engine"]["offline"] is True
    assert payload["disclaimer"]
    assert 0 <= payload["ned_reaching_level"] <= 100


def test_analyze_returns_structured_json_not_prose(client: TestClient) -> None:
    payload = client.post("/api/analyze", json={"text": "我喜欢你", "mode": "extreme"}).json()
    for key in (
        "signal_type",
        "signal_strength",
        "raw_interpretation",
        "alternative_explanations",
        "positive_evidence_discount",
        "negative_evidence_amplification",
        "ned_reaching_level",
        "reality_check",
        "verdict",
        "mode",
        "breakdown",
        "evidence",
    ):
        assert key in payload, key
    assert isinstance(payload["alternative_explanations"], list)
    assert isinstance(payload["verdict"], dict)


def test_analyze_with_history(client: TestClient) -> None:
    payload = client.post(
        "/api/analyze",
        json={
            "text": "我们已经结婚了",
            "mode": "extreme",
            "history": ["我喜欢你", "我想和你谈恋爱", "做我男朋友吧"],
        },
    ).json()
    assert payload["verdict"]["code"] == "ned.capacity_exhausted"
    assert payload["ned_reaching_level"] == 100.0
    assert payload["reaching_label"] == "人好。👍"


def test_analyze_accepts_english(client: TestClient) -> None:
    payload = client.post("/api/analyze", json={"text": "I miss you"}).json()
    assert payload["language"] == "en"
    assert payload["signal_type"] == "missing_you"


def test_analyze_rejects_blank_text(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"text": "   "})
    assert response.status_code == 422


def test_analyze_rejects_empty_body_field(client: TestClient) -> None:
    assert client.post("/api/analyze", json={}).status_code == 422


def test_analyze_rejects_unknown_mode(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"text": "我想你了", "mode": "chaos"})
    assert response.status_code == 422


def test_analyze_rejects_unknown_fields(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"text": "我想你了", "target": "her"})
    assert response.status_code == 422


def test_analyze_rejects_oversized_input(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"text": "想" * 9000})
    assert response.status_code == 422


def test_asymmetry_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/asymmetry",
        json={"positive_text": "她主动找我聊了两个小时", "negative_text": "五分钟没回复"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_profile"]["comparable"] is True
    assert payload["evidence_profile"]["information_gap"] > 0.8
    assert payload["ned_treatment"]["positive_discount"] == 35.0
    assert payload["ned_treatment"]["treatment_gap"] > 0.6
    assert payload["user_interpretation"]["status"] == "not_present"
    assert payload["user_interpretation"]["interpretive_score"] is None
    assert payload["asymmetry_score_is_legacy"] is True
    assert payload["asymmetry_score"] >= 75  # legacy composite, kept for compatibility
    assert payload["verdict"]["code"] == "evidence.reading_not_present"
    assert payload["reality_check"]


def test_asymmetry_endpoint_requires_input(client: TestClient) -> None:
    response = client.post("/api/asymmetry", json={"mode": "normal"})
    assert response.status_code == 422
    assert "supply" in response.json()["detail"]


def test_asymmetry_endpoint_accepts_free_text(client: TestClient) -> None:
    payload = client.post(
        "/api/asymmetry", json={"text": "她主动找我聊了两个小时，但五分钟没回复"}
    ).json()
    assert payload["asymmetry_score"] > 0


def test_fnbp_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/fnbp",
        json={"expected_sender": "Fuyuki", "actual_senders": ["张三", "李四"], "notifications": 4},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["prediction_misses"] == 4
    assert payload["mispredict_rate"] == 100.0
    assert payload["pipeline_flushes"] == 4
    assert len(payload["per_notification"]) == 4
    assert payload["verdict"]["text"] == "怎么又不是她效应"
    assert "虚构" in payload["codename_note"]
    assert "不是现实中的人物" in payload["codename_note"]


def test_fnbp_endpoint_hits_when_the_sender_matches(client: TestClient) -> None:
    payload = client.post(
        "/api/fnbp",
        json={"expected_sender": "Fuyuki", "actual_senders": ["Fuyuki"], "notifications": 3},
    ).json()
    assert payload["prediction_hits"] == 3
    assert payload["verdict"]["code"] == "fnbp.hit"
    assert payload["wasted_cycles"] == 0


def test_personality_layer_does_not_extend_api_json(client: TestClient) -> None:
    """Personality copy belongs only to the human-readable web and CLI layers."""

    payloads = (
        client.post("/api/analyze", json={"text": "marry me", "mode": "extreme"}).json(),
        client.post(
            "/api/asymmetry",
            json={"positive_text": "她主动找我聊了两个小时", "negative_text": "五分钟没回复"},
        ).json(),
        client.post("/api/fnbp", json={"notifications": 2}).json(),
    )
    for payload in payloads:
        assert "personality" not in payload


def test_openapi_schema_is_available(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/analyze" in schema["paths"]
    assert "/api/asymmetry" in schema["paths"]
    assert schema["info"]["title"].startswith("NED")


def test_web_ui_renders(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.text
    assert "Nov1ce Evidence Denier" in body
    assert "Systematically explaining away good news since 2026." in body
    assert "restores uncertainty" in body
    assert "人好" in body
    assert "Local-first" in body
    assert "Paste a message or describe what happened" in body
    assert "Analyze Evidence" in body
    assert "Alternative Hypotheses" in body
    assert "NED Reaching Level" in body
    assert 'id="personality-catalog"' in body
    assert 'id="reaching-personality"' in body
    assert 'id="fnbp-personality"' in body
    assert "Reality Check" in body
    assert "Final Verdict" in body
    assert "Negative Evidence Amplifier" in body
    assert __version__ in body
    assert "{{" not in body, "Jinja placeholder left unrendered"


def test_web_ui_has_the_blocks_the_script_writes_into(client: TestClient) -> None:
    """The template must expose every element the client script looks up."""

    body = client.get("/").text
    for element_id in (
        "nea-block",
        "nea-observed",
        "nea-amplified",
        "engine-notes-block",
        "mode-notes",
        "egg-list",
        "reaching-bar",
        "reaching-value",
        "reaching-personality",
        "asym-profile-comparable",
        "asym-treatment-gap",
        "asym-reading-status",
        "fnbp-personality",
        "hypotheses-list",
        "evidence-rows",
        "breakdown-rows",
        "copy-json",
        "fnbp-personality",
        "fnbp-personality-title",
        "fnbp-personality-zh",
        "fnbp-personality-en",
    ):
        assert f'id="{element_id}"' in body, element_id


def test_web_ui_lists_every_mode(client: TestClient) -> None:
    body = client.get("/").text
    for mode in ("Normal", "Scientific", "Nov1ce Extreme"):
        assert mode in body


def test_static_assets_are_served(client: TestClient) -> None:
    css = client.get("/static/style.css")
    js = client.get("/static/app.js")
    assert css.status_code == 200
    assert js.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert "javascript" in js.headers["content-type"]
    assert "/api/analyze" in js.text
    assert "prefers-reduced-motion" in css.text


def test_static_path_traversal_is_refused(client: TestClient) -> None:
    response = client.get("/static/../main.py")
    assert response.status_code in (400, 404)


def test_api_does_not_store_input(client: TestClient) -> None:
    """NED has no persistence layer: repeated calls leave no trace on disk."""

    marker = "这句话不应该被保存下来-9f3a"
    response = client.post("/api/analyze", json={"text": marker})
    assert response.status_code == 200
    # No database, no log file inside the package directory.
    from pathlib import Path

    import ned

    package_dir = Path(ned.__file__).resolve().parent
    for path in package_dir.rglob("*"):
        if path.is_file() and path.suffix in {".db", ".sqlite", ".log", ".jsonl"}:
            raise AssertionError(f"unexpected storage artefact: {path}")
    assert marker not in " ".join(path.name for path in package_dir.rglob("*") if path.is_file())


def test_web_ui_fnbp_reminder_is_in_the_lab_panel(client: TestClient) -> None:
    """The FNBP reminder must be rendered in the Lab panel, under its verdict.

    Regression guard: it shipped inside the Asymmetry panel, so running the
    branch predictor never displayed the reminder.
    """

    body = client.get("/").text
    lab = body.split('id="panel-lab"', 1)[1]
    asymmetry = body.split('id="panel-asymmetry"', 1)[1].split('id="panel-lab"', 1)[0]

    assert 'id="fnbp-verdict-text"' in lab, "the FNBP verdict must stay in the Lab panel"
    assert 'id="fnbp-personality"' in lab, "the FNBP reminder must be inside the Lab panel"
    assert 'id="fnbp-personality-title"' in lab
    assert 'id="fnbp-personality-zh"' in lab
    assert 'id="fnbp-personality-en"' in lab
    assert 'id="fnbp-personality"' not in asymmetry, (
        "the reminder must not be in the Asymmetry panel"
    )
    assert lab.index('id="fnbp-verdict-text"') < lab.index('id="fnbp-personality"'), (
        "the reminder must come after the verdict"
    )


def test_web_ui_ships_both_fnbp_reminder_messages(client: TestClient) -> None:
    """Both FNBP messages must reach the page, and the script must write them."""

    body = client.get("/").text
    match = re.search(r'<script id="personality-catalog"[^>]*>(.*?)</script>', body, re.DOTALL)
    assert match, "the personality catalog script tag is missing"
    catalog = json.loads(match.group(1))

    hit = catalog["fnbp"]["hit"]
    miss = catalog["fnbp"]["miss"]
    assert hit["title"] == "🎯 命中了。"
    assert "一次预测成功，不等于发现了规律" in hit["zh"]
    assert hit["en"] == "One successful prediction does not mean a pattern has been discovered."
    assert miss["title"] == "NED 提醒："
    assert "预测不是事实。期待也不是证据" in miss["zh"]
    assert miss["en"] == "Prediction is not reality. Expectation is not evidence."

    app_js = client.get("/static/app.js").text
    assert "renderFnbpPersonality(d.prediction_misses)" in app_js
    assert "fnbp-personality-zh" in app_js


def test_web_ui_frames_the_amplified_reading(client: TestClient) -> None:
    """The inflated reading must be framed as the interpretation under test."""

    body = client.get("/").text
    section = body.split('id="nea-block"', 1)[1].split("</section>", 1)[0]

    assert 'id="nea-amplified"' in section, "the amplified reading must stay in the NEA card"
    assert 'id="nea-framing"' in section, "the framing line must live in the NEA card"
    assert section.index('id="nea-amplified"') < section.index('id="nea-framing"'), (
        "the framing line must come after the amplified reading"
    )
    assert "measure it" not in section, (
        "the framing line replaces the older, redundant note sentence"
    )


def test_web_ui_ships_the_amplified_reading_framing(client: TestClient) -> None:
    """Both framing languages must reach the page."""

    match = re.search(
        r'<script id="personality-catalog"[^>]*>(.*?)</script>', client.get("/").text, re.DOTALL
    )
    assert match, "the personality catalog script tag is missing"
    framing = json.loads(match.group(1))["nea_framing"]

    assert framing["en"] == (
        "This is the exaggerated interpretation NED is checking — not its conclusion."
    )
    assert framing["zh"] == "这是 NED 正在检查的夸大解读，不是 NED 的结论。"


def test_the_web_script_writes_the_framing_line(client: TestClient) -> None:
    script = client.get("/static/app.js").text
    assert "nea-framing" in script
    assert "nea_framing" in script
