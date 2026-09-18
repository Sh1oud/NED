"""M2: the casebook API - CRUD, the server-built snapshot, idempotency, isolation, deletes.

The tests here are written against the product rules, not the implementation: analysing never
writes, a client cannot file a verdict it made up, a double-click is one case file and a new
action on the same sentence is a second one, and every read or delete is scoped to one casebook.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ned.app.main import create_app
from ned.app.store import CASEBOOK_ENV, CASEBOOK_PATH_ENV

TEXT = "她记得我生日"


@pytest.fixture
def casebook_path(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A switched-on casebook in a scratch directory, with its own file per test."""

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


def action() -> str:
    """A fresh user action id, the way the browser mints one per click."""

    return uuid.uuid4().hex


def make_casebook(client: TestClient, label: str = "小 A") -> str:
    response = client.post("/api/casebook", json={"label": label})
    assert response.status_code == 201, response.text
    return response.json()["casebook_id"]


def archive(client: TestClient, casebook_id: str, text: str = TEXT, **extra: object) -> dict:
    body = {"text": text, "mode": "normal", "action_id": action()}
    body.update(extra)
    response = client.post(f"/api/casebook/{casebook_id}/archive", json=body)
    return {"status": response.status_code, **(response.json() if response.content else {})}


# ------------------------------------------------------------------- the switch ---
def test_switched_off_status_creates_nothing(off_client: TestClient, workdir: Path) -> None:
    response = off_client.get("/api/casebook/status")
    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "path": None,
        "casebooks": 0,
        "case_files": 0,
        "entries": 0,
        "note": "",
    }
    assert not (workdir / "data").exists()


def test_switched_off_refuses_every_casebook_write(off_client: TestClient) -> None:
    assert off_client.post("/api/casebook", json={"label": "小 A"}).status_code == 403
    assert off_client.get("/api/casebook").status_code == 403
    assert off_client.get("/api/casebook/cb_x").status_code == 403
    assert off_client.delete("/api/casebook/cb_x").status_code == 403
    assert (
        off_client.post(
            "/api/casebook/cb_x/archive", json={"text": TEXT, "action_id": action()}
        ).status_code
        == 403
    )
    assert off_client.delete("/api/casebook/cb_x/entries/en_x").status_code == 403


def test_switched_on_status_never_creates_the_file(client: TestClient, casebook_path: Path) -> None:
    response = client.get("/api/casebook/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["path"] == str(casebook_path)
    assert payload["casebooks"] == 0
    assert not casebook_path.exists(), "a status probe must not bring the file into existence"


def test_switched_on_status_counts_what_is_on_file(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    archive(client, casebook_id, text="她记得我生日")
    status = client.get("/api/casebook/status").json()
    assert status["casebooks"] == 1
    assert status["case_files"] == 1
    assert status["entries"] == 1


# ------------------------------------------------------------------ casebooks ---
def test_create_list_and_rename(client: TestClient) -> None:
    first = make_casebook(client, "小 A")
    second = make_casebook(client, "小 B")

    listed = client.get("/api/casebook").json()
    assert [item["label"] for item in listed] == ["小 A", "小 B"]

    renamed = client.patch(f"/api/casebook/{first}", json={"label": "小 A（同事）"})
    assert renamed.status_code == 200
    assert renamed.json()["label"] == "小 A（同事）"
    assert second != first


def test_renaming_an_unknown_casebook_is_404(client: TestClient) -> None:
    assert client.patch("/api/casebook/cb_missing", json={"label": "x"}).status_code == 404
    assert client.get("/api/casebook/cb_missing").status_code == 404


def test_a_casebook_needs_a_label(client: TestClient) -> None:
    assert client.post("/api/casebook", json={"label": ""}).status_code == 422


# ----------------------------------------------------- the server builds the snapshot ---
def test_archiving_uses_this_process_analysis(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    outcome = archive(client, casebook_id, text="她记得我生日")
    assert outcome["status"] == 200, outcome
    assert outcome["created"] is True
    assert outcome["entry_count"] == 1

    reference = client.post("/api/analyze", json={"text": "她记得我生日"}).json()
    detail = client.get(f"/api/casebook/{casebook_id}").json()
    case_file = detail["case_files"][0]
    assert case_file["verdict_code"] == reference["verdict"]["code"]
    assert case_file["verdict_text"] == reference["verdict"]["text"]
    assert case_file["recognition"] == reference["recognition"]
    assert case_file["signal_type"] == reference["signal_type"]
    assert case_file["engine_name"] == reference["engine"]["name"]
    assert case_file["engine_version"] == reference["engine"]["version"]
    assert case_file["rules_fingerprint"].startswith("rp_")
    assert case_file["input_text"] == "她记得我生日"
    entry = case_file["entries"][0]
    assert entry["material_kind"] == reference["materials"][0]["material_kind"]
    assert entry["reported_content"] == reference["materials"][0]["reported_content"]
    assert entry["origin_rule_id"] == reference["materials"][0]["origin_rule_id"]
    assert entry["entry_kind"] == "event"
    assert case_file["saved_at"] >= case_file["generated_at"]


def test_a_client_cannot_file_a_verdict_it_made_up(client: TestClient) -> None:
    """``extra="forbid"`` is the anti-forgery mechanism: there is nowhere to put a fake verdict."""

    casebook_id = make_casebook(client)
    forged = {
        "text": TEXT,
        "action_id": action(),
        "verdict_code": "ned.no_signal",
        "verdict_text": "NED 无事可做。",
        "recognition": "nothing_recognized",
        "materials": [{"material_kind": "invented", "reported_content": "invented"}],
        "generated_at": "1999-01-01T00:00:00+00:00",
        "saved_at": "1999-01-01T00:00:00+00:00",
    }
    response = client.post(f"/api/casebook/{casebook_id}/archive", json=forged)
    assert response.status_code == 422
    assert client.get(f"/api/casebook/{casebook_id}").json()["case_files"] == []
    assert client.get("/api/casebook/status").json()["entries"] == 0


def test_archiving_something_ned_recognises_nothing_in_is_still_recorded(
    client: TestClient,
) -> None:
    """A filed case file may carry zero materials; the input is still on file verbatim."""

    casebook_id = make_casebook(client)
    outcome = archive(client, casebook_id, text="今天食堂的饭难吃")
    assert outcome["status"] == 200
    case_file = client.get(f"/api/casebook/{casebook_id}").json()["case_files"][0]
    assert case_file["entries"] == []
    assert case_file["input_text"] == "今天食堂的饭难吃"


def test_archiving_into_an_unknown_casebook_is_404(client: TestClient) -> None:
    response = client.post(
        "/api/casebook/cb_missing/archive", json={"text": TEXT, "action_id": action()}
    )
    assert response.status_code == 404


def test_archiving_requires_an_action_id(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    response = client.post(f"/api/casebook/{casebook_id}/archive", json={"text": TEXT})
    assert response.status_code == 422


# ------------------------------------------------------------------ idempotency ---
def test_a_double_click_files_one_case_file(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    same_action = action()
    first = archive(client, casebook_id, action_id=same_action)
    second = archive(client, casebook_id, action_id=same_action)

    assert first["created"] is True
    assert second["created"] is False
    assert second["case_file_id"] == first["case_file_id"]
    detail = client.get(f"/api/casebook/{casebook_id}").json()
    assert len(detail["case_files"]) == 1
    assert len(detail["case_files"][0]["entries"]) == 1


def test_the_same_sentence_filed_by_a_new_action_is_a_new_case_file(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    first = archive(client, casebook_id, text="她说她喜欢我")
    second = archive(client, casebook_id, text="她说她喜欢我")

    assert first["created"] is True
    assert second["created"] is True
    assert first["case_file_id"] != second["case_file_id"]
    detail = client.get(f"/api/casebook/{casebook_id}").json()
    assert len(detail["case_files"]) == 2
    assert {item["input_text"] for item in detail["case_files"]} == {"她说她喜欢我"}


def test_analysing_never_writes_to_the_casebook(client: TestClient, casebook_path: Path) -> None:
    """The strongest form of "only 归入卷宗 writes": analyse a lot of inputs, file none."""

    make_casebook(client)
    for text in ("她说她喜欢我", "她记得我生日", "她骂我是不是有病"):
        assert client.post("/api/analyze", json={"text": text}).status_code == 200
    detail = client.get("/api/casebook").json()
    assert detail[0]["case_files"] == 0
    assert client.get("/api/casebook/status").json()["entries"] == 0


# -------------------------------------------------------------------- isolation ---
def test_two_casebooks_do_not_see_each_other(client: TestClient) -> None:
    x = make_casebook(client, "小 X")
    y = make_casebook(client, "小 Y")
    archive(client, x, text="她记得我生日")
    filed_y = archive(client, y, text="她说她不喜欢我")

    detail_x = client.get(f"/api/casebook/{x}").json()
    detail_y = client.get(f"/api/casebook/{y}").json()
    assert [item["input_text"] for item in detail_x["case_files"]] == ["她记得我生日"]
    assert [item["input_text"] for item in detail_y["case_files"]] == ["她说她不喜欢我"]

    entry_x = detail_x["case_files"][0]["entries"][0]["entry_id"]
    entry_y = detail_y["case_files"][0]["entries"][0]["entry_id"]
    assert entry_x != entry_y

    # a delete addressed at X must not reach Y's rows
    assert client.delete(f"/api/casebook/{x}/entries/{entry_y}").status_code == 404
    assert client.delete(f"/api/casebook/{x}/files/{filed_y['case_file_id']}").status_code == 404
    # neither casebook lost anything, and X still holds exactly its own case file
    assert len(client.get(f"/api/casebook/{y}").json()["case_files"]) == 1
    assert len(client.get(f"/api/casebook/{x}").json()["case_files"]) == 1


def test_the_casebook_id_is_in_every_path(client: TestClient) -> None:
    """There is no casebook route without a casebook id (except status/list/create)."""

    paths = client.get("/openapi.json").json()["paths"]
    casebook_paths = {
        path: sorted(method for method in verbs if method != "parameters")
        for path, verbs in paths.items()
        if path.startswith("/api/casebook")
    }
    assert "/api/casebook" in casebook_paths
    for path in casebook_paths:
        if path in ("/api/casebook", "/api/casebook/status"):
            continue
        assert path.startswith("/api/casebook/{casebook_id}"), path


# ---------------------------------------------------------------------- deletes ---
def test_deleting_an_entry_leaves_the_case_file(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    archive(client, casebook_id)
    entry = client.get(f"/api/casebook/{casebook_id}").json()["case_files"][0]["entries"][0]

    deleted = client.delete(f"/api/casebook/{casebook_id}/entries/{entry['entry_id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {
        "deleted": True,
        "kind": "entry",
        "identifier": entry["entry_id"],
        "detail": "entry and the material it quoted were removed from the casebook",
    }
    remaining = client.get(f"/api/casebook/{casebook_id}").json()
    assert remaining["case_files"][0]["entries"] == []
    assert client.get("/api/casebook/status").json()["entries"] == 0


def test_deleting_a_case_file_takes_its_entries(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    outcome = archive(client, casebook_id)
    deleted = client.delete(f"/api/casebook/{casebook_id}/files/{outcome['case_file_id']}")
    assert deleted.status_code == 200
    assert deleted.json()["kind"] == "case_file"
    assert client.get(f"/api/casebook/{casebook_id}").json()["case_files"] == []
    status = client.get("/api/casebook/status").json()
    assert (status["casebooks"], status["case_files"], status["entries"]) == (1, 0, 0)


def test_deleting_a_casebook_takes_everything(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    archive(client, casebook_id)
    deleted = client.delete(f"/api/casebook/{casebook_id}")
    assert deleted.status_code == 200
    assert deleted.json()["kind"] == "casebook"
    assert client.get(f"/api/casebook/{casebook_id}").status_code == 404
    status = client.get("/api/casebook/status").json()
    assert (status["casebooks"], status["case_files"], status["entries"]) == (0, 0, 0)


def test_deleting_an_unknown_row_says_so_without_inventing_one(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    response = client.delete(f"/api/casebook/{casebook_id}/entries/en_missing")
    assert response.status_code == 404
    assert client.delete("/api/casebook/cb_missing").json()["deleted"] is False


# ------------------------------------------------------------------ event time ---
def test_the_readers_event_time_is_validated_and_stored(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    outcome = archive(
        client,
        casebook_id,
        occurred={
            "occurred_at": "2026-03-01",
            "occurred_precision": "day",
            "occurred_source": "user",
        },
    )
    assert outcome["status"] == 200
    case_file = client.get(f"/api/casebook/{casebook_id}").json()["case_files"][0]
    assert case_file["occurred_at"] == "2026-03-01"
    assert case_file["occurred_precision"] == "day"
    assert case_file["occurred_source"] == "user"
    # the entry inherited the same event time as a value
    assert case_file["entries"][0]["occurred_at"] == "2026-03-01"
    assert case_file["entries"][0]["occurred_source"] == "user"


def test_an_undated_case_does_not_become_today(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    archive(client, casebook_id)
    case_file = client.get(f"/api/casebook/{casebook_id}").json()["case_files"][0]
    assert case_file["occurred_at"] is None
    assert case_file["occurred_precision"] == "unknown"
    assert case_file["occurred_source"] == "unknown"
    assert case_file["saved_at"]


def test_an_invented_or_padded_event_time_is_refused(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    for occurred in (
        {
            "occurred_at": "2026-03-01T00:00:00Z",
            "occurred_precision": "day",
            "occurred_source": "user",
        },
        {
            "occurred_at": "2026-03-01",
            "occurred_precision": "unknown",
            "occurred_source": "unknown",
        },
        {"occurred_at": None, "occurred_precision": "unknown", "occurred_source": "user"},
        {
            "occurred_at": "2026-03-01T14:00:00+08:00",
            "occurred_precision": "second",
            "occurred_source": "user",
        },
    ):
        response = client.post(
            f"/api/casebook/{casebook_id}/archive",
            json={"text": TEXT, "action_id": action(), "occurred": occurred},
        )
        assert response.status_code == 422, occurred


def test_a_relative_time_clue_is_recorded_as_such(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    outcome = archive(
        client,
        casebook_id,
        occurred={
            "occurred_at": None,
            "occurred_precision": "unknown",
            "occurred_source": "input_relative",
        },
    )
    assert outcome["status"] == 200
    case_file = client.get(f"/api/casebook/{casebook_id}").json()["case_files"][0]
    assert case_file["occurred_source"] == "input_relative"
    assert case_file["occurred_at"] is None


# ----------------------------------------------------------- additive contract ---
def test_the_analyse_contract_is_unchanged(client: TestClient) -> None:
    """New endpoints are additive: /api/analyze keeps its shape and API_VERSION stays 1."""

    version = client.get("/api/version").json()
    assert version["api_version"] == "1"
    required = {"input", "mode", "language", "recognition", "verdict", "evidence", "engine"}
    payload = client.post("/api/analyze", json={"text": TEXT}).json()
    assert required <= set(payload)
    assert "casebook" not in payload


# ------------------------------------------------------------------ concurrency ---
def test_overlapping_requests_do_not_break_the_store(client: TestClient) -> None:
    """One store per request, on the request's own thread.

    A sqlite connection may only be used from the thread that created it, and FastAPI does not
    promise a dependency and its endpoint share a worker. Opening the store inside the endpoint
    body is what makes this pass; opening it in a dependency made every overlapping request answer
    500 with a ProgrammingError.
    """

    from concurrent.futures import ThreadPoolExecutor

    def one_round(index: int) -> list[int]:
        statuses: list[int] = []
        created = client.post("/api/casebook", json={"label": f"并发-{index}"})
        statuses.append(created.status_code)
        casebook_id = created.json()["casebook_id"]
        for round_index in range(2):
            statuses.append(client.get("/api/casebook/status").status_code)
            statuses.append(client.get("/api/casebook").status_code)
            statuses.append(client.get(f"/api/casebook/{casebook_id}").status_code)
            archived = client.post(
                f"/api/casebook/{casebook_id}/archive",
                json={
                    "text": "她记得我生日",
                    "action_id": f"concurrent-{index}-{round_index}",
                },
            )
            statuses.append(archived.status_code)
        statuses.append(client.delete(f"/api/casebook/{casebook_id}").status_code)
        return statuses

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(one_round, range(8)))

    statuses = [status for row in results for status in row]
    assert statuses, "the pool produced no results"
    assert max(statuses) < 500, sorted(set(statuses))
    assert all(status in (200, 201) for status in statuses), sorted(set(statuses))
    status = client.get("/api/casebook/status").json()
    assert status["casebooks"] == 0
    assert status["entries"] == 0
