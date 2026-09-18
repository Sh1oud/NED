"""M3: the explicit review path on ``/api/analyze``.

The contract of the batch is measured here on real payloads: with no casebook in the request the
response is exactly what it always was, and with a casebook the response gains one parallel key
and moves nothing else.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ned.app.core.analyzer import NedAnalyzer
from ned.app.main import create_app
from ned.app.store import CASEBOOK_ENV, CASEBOOK_PATH_ENV

CURRENT = "她今天又主动找我"
#: Everything the current case keeps for itself. None of it may move because of a casebook.
PROTECTED = (
    "input",
    "mode",
    "language",
    "signal_type",
    "signal_label",
    "signal_strength",
    "raw_interpretation",
    "alternative_explanations",
    "positive_evidence_discount",
    "negative_evidence_amplification",
    "ned_reaching_level",
    "reaching_label",
    "reality_check",
    "asymmetry_reality_check",
    "verdict",
    "mode_notes",
    "evidence",
    "observed_evidence",
    "irrational_amplification",
    "asymmetry",
    "interpretation_audit",
    "material_aspects",
    "materials",
    "recognition",
    "easter_eggs",
    "engine",
    "breakdown",
)


@pytest.fixture
def casebook_path(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = workdir / "data" / "casebook.sqlite3"
    monkeypatch.setenv(CASEBOOK_ENV, "on")
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(target))
    return target


@pytest.fixture
def client(casebook_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def off_client(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv(CASEBOOK_ENV, raising=False)
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(workdir / "data" / "casebook.sqlite3"))
    with TestClient(create_app()) as test_client:
        yield test_client


def make_casebook(client: TestClient, label: str = "小 A") -> str:
    response = client.post("/api/casebook", json={"label": label})
    assert response.status_code == 201, response.text
    return response.json()["casebook_id"]


def archive(
    client: TestClient,
    casebook_id: str,
    text: str,
    *,
    occurred: str | None = None,
    precision: str = "day",
) -> dict:
    body: dict[str, object] = {"text": text, "mode": "normal", "action_id": uuid.uuid4().hex}
    if occurred is not None:
        body["occurred"] = {
            "occurred_at": occurred,
            "occurred_precision": precision,
            "occurred_source": "user",
        }
    response = client.post(f"/api/casebook/{casebook_id}/archive", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def analyse(client: TestClient, text: str = CURRENT, **extra: object) -> dict:
    response = client.post("/api/analyze", json={"text": text, "mode": "normal", **extra})
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------- the default path ---
def test_the_default_path_gains_no_key(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    archive(client, casebook_id, "她说喜欢我", occurred="2026-07-12")

    payload = analyse(client)
    assert "casebook_review" not in payload
    assert "casebook" not in payload


def test_the_default_path_is_identical_with_the_casebook_on_and_off(
    casebook_path: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Semantic delta zero: a switched-on casebook changes nothing unless it is asked for."""

    with TestClient(create_app()) as on_client:
        casebook_id = make_casebook(on_client)
        archive(on_client, casebook_id, "她说喜欢我", occurred="2026-07-12")
        on_payload = analyse(on_client)

    monkeypatch.delenv(CASEBOOK_ENV, raising=False)
    with TestClient(create_app()) as off_client:
        off_payload = analyse(off_client)

    on_payload.pop("generated_at")
    off_payload.pop("generated_at")
    assert on_payload == off_payload


def test_no_database_is_touched_when_no_casebook_is_asked_for(
    casebook_path: Path, client: TestClient
) -> None:
    """A corrupt casebook cannot break an ordinary analysis: it is never opened."""

    casebook_path.parent.mkdir(parents=True, exist_ok=True)
    casebook_path.write_bytes(b"not a database at all" * 100)

    payload = analyse(client)
    assert "casebook_review" not in payload
    assert payload["verdict"]["code"]


# ------------------------------------------------------------- the explicit path ---
def test_an_explicit_review_is_additive_only(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    archive(client, casebook_id, "她说喜欢我", occurred="2026-07-12")
    archive(client, casebook_id, "她明确说只想做朋友", occurred="2026-08-03")

    plain = analyse(client)
    joint = analyse(client, casebook={"casebook_id": casebook_id})

    review = joint.pop("casebook_review")
    moved = [key for key in PROTECTED if plain.get(key) != joint.get(key)]
    assert moved == [], moved
    # Nothing else may differ either: the engine's own timestamp, and the review.
    different = {key for key in set(plain) | set(joint) if plain.get(key) != joint.get(key)}
    assert different == {"generated_at"}, different
    assert plain["verdict"] == joint["verdict"]
    assert review["casebook_label"] == "小 A"
    assert review["counts"]["superseded"] == 1
    assert review["summary_code"] == "boundary_governs"


def test_the_current_case_verdict_is_untouched_even_when_history_disagrees(
    client: TestClient,
) -> None:
    casebook_id = make_casebook(client)
    archive(client, casebook_id, "她说我们只是朋友", occurred="2026-08-03")

    plain = analyse(client, "她给我带了早餐")
    joint = analyse(client, "她给我带了早餐", casebook={"casebook_id": casebook_id})
    assert joint["verdict"] == plain["verdict"]
    assert joint["evidence"] == plain["evidence"]
    assert joint["materials"] == plain["materials"]
    assert joint["breakdown"] == plain["breakdown"]
    assert joint["recognition"] == plain["recognition"]
    assert joint["ned_reaching_level"] == plain["ned_reaching_level"]
    assert joint["casebook_review"]["counts"]["conflicts"] == 1


def test_the_reader_own_event_time_can_make_the_order_known(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    archive(client, casebook_id, "她说喜欢我", occurred="2026-07-12")

    undated = analyse(client, "她明确说只想做朋友", casebook={"casebook_id": casebook_id})
    assert undated["casebook_review"]["items"][0]["relation"] == "conflicts"

    dated = analyse(
        client,
        "她明确说只想做朋友",
        casebook={
            "casebook_id": casebook_id,
            "occurred": {
                "occurred_at": "2026-08-03",
                "occurred_precision": "day",
                "occurred_source": "user",
            },
        },
    )
    review = dated["casebook_review"]
    assert review["items"][0]["relation"] == "superseded"
    assert review["governing"]["item_kind"] == "current_case"


def test_the_review_reads_only_the_casebook_it_was_given(client: TestClient) -> None:
    x = make_casebook(client, "小 X")
    y = make_casebook(client, "小 Y")
    archive(client, x, "她说喜欢我")
    archive(client, y, "她妈妈反对我们在一起")

    review_x = analyse(client, casebook={"casebook_id": x})["casebook_review"]
    joined = json.dumps(review_x, ensure_ascii=False)
    assert "她妈妈反对我们在一起" not in joined
    # every row belongs to a case file of the casebook that was asked for, and to no other
    own = {
        case_file["case_file_id"]
        for case_file in client.get(f"/api/casebook/{x}").json()["case_files"]
    }
    foreign = {
        case_file["case_file_id"]
        for case_file in client.get(f"/api/casebook/{y}").json()["case_files"]
    }
    assert own and foreign and not (own & foreign)
    assert {item["case_file_id"] for item in review_x["items"]} <= own

    review_y = analyse(client, casebook={"casebook_id": y})["casebook_review"]
    assert review_y["casebook_label"] == "小 Y"
    assert {item["case_file_id"] for item in review_y["items"]} <= foreign
    assert {item["case_file_id"] for item in review_y["items"]}.isdisjoint(own)


def test_a_request_cannot_smuggle_a_verdict_into_the_review(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    response = client.post(
        "/api/analyze",
        json={
            "text": CURRENT,
            "casebook": {"casebook_id": casebook_id, "verdict": {"code": "ped.ren_hao"}},
        },
    )
    assert response.status_code == 422


def test_an_unknown_casebook_is_a_404_not_a_silent_single_case(client: TestClient) -> None:
    response = client.post(
        "/api/analyze", json={"text": CURRENT, "casebook": {"casebook_id": "cb_nope"}}
    )
    assert response.status_code == 404
    assert "cb_nope" in response.json()["detail"]


def test_a_switched_off_casebook_refuses_an_explicit_review(off_client: TestClient) -> None:
    response = off_client.post(
        "/api/analyze", json={"text": CURRENT, "casebook": {"casebook_id": "cb_anything"}}
    )
    assert response.status_code == 403
    assert "NED_CASEBOOK" in response.json()["detail"]


def test_a_review_writes_nothing(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    archive(client, casebook_id, "她说喜欢我", occurred="2026-07-12")
    before = client.get("/api/casebook/status").json()

    analyse(client, casebook={"casebook_id": casebook_id})
    analyse(client, casebook={"casebook_id": casebook_id})

    after = client.get("/api/casebook/status").json()
    assert (after["casebooks"], after["case_files"], after["entries"]) == (
        before["casebooks"],
        before["case_files"],
        before["entries"],
    )


def test_the_review_carries_counts_and_no_score(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    archive(client, casebook_id, "她说喜欢我")
    review = analyse(client, casebook={"casebook_id": casebook_id})["casebook_review"]
    assert review["scored"] is False
    assert set(review["counts"]) == {
        "supports",
        "conflicts",
        "superseded",
        "unrelated",
        "not_comparable",
        "insufficient",
    }
    flat = json.dumps(review, ensure_ascii=False).lower()
    for forbidden in ("percent", 'score"', "ratio", "trend", "average", "weight"):
        assert forbidden not in flat, forbidden


def test_the_review_uses_the_recorded_reading_not_a_new_one(client: TestClient) -> None:
    """M3 is ``as_recorded``: the row reports the signal the archive stored."""

    casebook_id = make_casebook(client)
    archive(client, casebook_id, "她记得我生日")
    review = analyse(client, casebook={"casebook_id": casebook_id})["casebook_review"]
    item = review["items"][0]
    assert item["material_kind"] == "memory_care_act"
    assert item["recorded_direction"] == "positive"
    assert item["relation"] == "supports"
    stored = client.get(f"/api/casebook/{casebook_id}").json()["case_files"][0]
    assert item["recorded_signal_type"] == stored["signal_type"]
    assert item["recorded_verdict_code"] == stored["verdict_code"]


def test_the_openapi_contract_stays_additive(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    version = client.get("/api/version").json()["api_version"]
    assert version == "1"
    analyze = schema["paths"]["/api/analyze"]["post"]
    body = analyze["requestBody"]["content"]["application/json"]["schema"]
    request_model = schema["components"]["schemas"][body["$ref"].rsplit("/", 1)[-1]]
    assert "casebook" in request_model["properties"]
    assert "casebook" not in request_model.get("required", [])
    assert "text" in request_model["properties"]
    # the response schema keeps every old property and adds the review as optional
    name = analyze["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    model = schema["components"]["schemas"][name.rsplit("/", 1)[-1]]
    assert "casebook_review" in model["properties"]
    assert "casebook_review" not in model.get("required", [])
    for field in ("verdict", "evidence", "materials", "recognition", "breakdown"):
        assert field in model["properties"]


def test_the_review_does_not_depend_on_the_engine_being_re_run(client: TestClient) -> None:
    """The same casebook read twice gives the same relations, whatever the engine returns."""

    casebook_id = make_casebook(client)
    archive(client, casebook_id, "她说喜欢我", occurred="2026-07-12")
    first = analyse(client, casebook={"casebook_id": casebook_id})["casebook_review"]
    second = analyse(client, casebook={"casebook_id": casebook_id})["casebook_review"]
    first.pop("casebook_id")
    second.pop("casebook_id")
    assert first == second


def test_the_engine_is_the_only_thing_that_reads_the_input(client: TestClient) -> None:
    """``/api/analyze`` with a selection still analyses in-process, once."""

    analyzer = NedAnalyzer()
    expected = analyzer.analyze_text(CURRENT)
    casebook_id = make_casebook(client)
    joint = analyse(client, casebook={"casebook_id": casebook_id})
    assert joint["verdict"]["code"] == expected.verdict.code
    assert joint["signal_type"] == expected.signal_type
    assert joint["recognition"] == expected.recognition
