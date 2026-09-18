"""M4C: the reread endpoint - read-only, additive, and unable to touch the archive or the case.

The contract of the batch is measured on a real database: the business rows must be byte-identical
before and after, and the analyse path must be exactly what it was.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ned.app.main import create_app
from ned.app.store import CASEBOOK_ENV, CASEBOOK_PATH_ENV, CasebookStore

TEXT = "她记得我生日，但她说我们只是朋友"

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


def digest(path: Path) -> str:
    """A canonical digest of the business tables: "unchanged" means exactly that."""

    if not path.is_file():
        return "(no file)"
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        running = hashlib.sha256()
        for table in ("casebooks", "case_files", "entries"):
            rows = connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            running.update(f"{table}:{len(rows)}".encode())
            for row in rows:
                running.update(json.dumps([str(value) for value in row]).encode())
        return running.hexdigest()
    finally:
        connection.close()


def archive(client: TestClient, text: str = TEXT) -> tuple[str, str]:
    casebook = client.post("/api/casebook", json={"label": "小 X"}).json()
    casebook_id = casebook["casebook_id"]
    filed = client.post(
        f"/api/casebook/{casebook_id}/archive",
        json={
            "text": text,
            "action_id": uuid.uuid4().hex,
            "occurred": {
                "occurred_at": "2026-08-03",
                "occurred_precision": "day",
                "occurred_source": "user",
            },
        },
    ).json()
    return casebook_id, filed["case_file_id"]


# ------------------------------------------------------------------ the endpoint ---
def test_a_reread_returns_both_readings_and_the_alignment(client: TestClient) -> None:
    casebook_id, case_file_id = archive(client)
    response = client.post(f"/api/casebook/{casebook_id}/files/{case_file_id}/reread")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["casebook_id"] == casebook_id
    assert payload["case_file_id"] == case_file_id
    assert payload["input_text"] == TEXT
    assert payload["as_recorded"]["recognition"] == "material_registered"
    assert len(payload["as_recorded"]["entries"]) == 2
    assert payload["as_reread"]["engine_version"]
    assert len(payload["as_reread"]["materials"]) == 2
    assert [row["difference"] for row in payload["alignment"]] == ["same", "same"]
    assert payload["counts"] == {
        "same": 2,
        "changed": 0,
        "missing": 0,
        "ambiguous": 0,
        "new": 0,
        "rule_id_only": 0,
    }
    assert payload["identical"] is True
    assert payload["rules_differ_from_archive"] is False


def test_the_request_cannot_supply_the_history(client: TestClient) -> None:
    """Whatever a client posts is ignored: the server reads the archived input itself."""

    casebook_id, case_file_id = archive(client)
    payload = client.post(
        f"/api/casebook/{casebook_id}/files/{case_file_id}/reread",
        json={"text": "她此刻正爱着我", "input_text": "她此刻正爱着我"},
    ).json()
    assert payload["input_text"] == TEXT
    assert "她此刻正爱着我" not in json.dumps(payload, ensure_ascii=False)


def test_the_reread_is_read_only_even_if_the_writable_opener_would_fail(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The path opens the store read-only: a broken writable opener cannot affect it."""

    casebook_id, case_file_id = archive(client)

    def refuse(*args: object, **kwargs: object) -> CasebookStore:
        raise AssertionError("the reread path opened the casebook writable")

    monkeypatch.setattr(CasebookStore, "open", classmethod(lambda cls, *a, **k: refuse()))
    response = client.post(f"/api/casebook/{casebook_id}/files/{case_file_id}/reread")
    assert response.status_code == 200, response.text


def test_the_archive_does_not_move(client: TestClient, casebook_path: Path) -> None:
    casebook_id, case_file_id = archive(client)
    before = digest(casebook_path)
    status_before = client.get("/api/casebook/status").json()

    for _ in range(3):
        assert (
            client.post(f"/api/casebook/{casebook_id}/files/{case_file_id}/reread").status_code
            == 200
        )

    assert digest(casebook_path) == before
    status_after = client.get("/api/casebook/status").json()
    assert (status_after["casebooks"], status_after["case_files"], status_after["entries"]) == (
        status_before["casebooks"],
        status_before["case_files"],
        status_before["entries"],
    )


def test_unknown_ids_are_404(client: TestClient) -> None:
    casebook_id, _case_file_id = archive(client)
    assert client.post(f"/api/casebook/{casebook_id}/files/cf_nope/reread").status_code == 404
    assert client.post("/api/casebook/cb_nope/files/cf_nope/reread").status_code == 404


def test_a_switched_off_casebook_refuses_a_reread(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(CASEBOOK_ENV, raising=False)
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(workdir / "data" / "casebook.sqlite3"))
    with TestClient(create_app()) as off_client:
        response = off_client.post("/api/casebook/cb_x/files/cf_y/reread")
    assert response.status_code == 403
    assert "NED_CASEBOOK" in response.json()["detail"]


# ------------------------------------------------------------- the current case ---
def test_the_analyse_path_gains_nothing_from_a_reread(client: TestClient) -> None:
    casebook_id, case_file_id = archive(client)
    plain_before = client.post("/api/analyze", json={"text": "她今天又主动找我"}).json()
    joint_before = client.post(
        "/api/analyze",
        json={"text": "她今天又主动找我", "casebook": {"casebook_id": casebook_id}},
    ).json()

    client.post(f"/api/casebook/{casebook_id}/files/{case_file_id}/reread")

    plain_after = client.post("/api/analyze", json={"text": "她今天又主动找我"}).json()
    joint_after = client.post(
        "/api/analyze",
        json={"text": "她今天又主动找我", "casebook": {"casebook_id": casebook_id}},
    ).json()

    for name in PROTECTED:
        assert plain_before.get(name) == plain_after.get(name), name
        assert joint_before.get(name) == joint_after.get(name), name
    assert "reread" not in json.dumps(plain_after)
    assert joint_after["casebook_review"]["counts"]["superseded"] == 0


def test_a_reread_never_reaches_the_casebook_review(client: TestClient) -> None:
    """The reread is its own endpoint: the review payload carries no reread data at all."""

    casebook_id, case_file_id = archive(client)
    client.post(f"/api/casebook/{casebook_id}/files/{case_file_id}/reread")
    review = client.post(
        "/api/analyze",
        json={"text": "她今天又主动找我", "casebook": {"casebook_id": casebook_id}},
    ).json()["casebook_review"]
    assert "reread" not in json.dumps(review)
    assert set(review) == {
        "casebook_id",
        "casebook_label",
        "case_files_read",
        "entries_read",
        "items_compared",
        "current_direction",
        "items",
        "counts",
        "governing",
        "governing_reason",
        "order_known",
        "summary_code",
        "summary_args",
        "relation_assessed",
        "scored",
    }


def test_the_openapi_contract_stays_additive(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert client.get("/api/version").json()["api_version"] == "1"
    path = "/api/casebook/{casebook_id}/files/{case_file_id}/reread"
    assert path in schema["paths"]
    assert set(schema["paths"][path]) == {"post"}
    # and the analyse contract is untouched: the review is still an optional response property
    ref = schema["paths"]["/api/analyze"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"]
    model = schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    assert "casebook_review" in model["properties"]
    assert "casebook_review" not in model.get("required", [])


def test_a_reread_of_a_case_with_no_entries_is_still_honest(client: TestClient) -> None:
    casebook_id, case_file_id = archive(client, "她今天又主动找我")
    payload = client.post(f"/api/casebook/{casebook_id}/files/{case_file_id}/reread").json()
    assert payload["as_recorded"]["entries"] == []
    assert payload["counts"]["new"] == 0
    assert payload["identical"] is True
