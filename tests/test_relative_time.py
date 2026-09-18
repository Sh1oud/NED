"""M4D: relative-time hints - recognised, never resolved; and the copy the casebook made untrue.

Three product rules are pinned here:

* the detector is a pure function of the text: it names the wording, and it produces no date;
* the archive records the reader's own date, else the hint, else nothing - with ``occurred_at``
  staying NULL whenever no date was given;
* no present-tense claim in the product still says that nothing is ever stored.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.relative_time import has_relative_time, relative_time_cues
from ned.app.main import create_app
from ned.app.review import (
    MaterialFacts,
    Relation,
    ReviewRecord,
    build_casebook_review,
    current_case_facts,
)
from ned.app.store import CASEBOOK_ENV, CASEBOOK_PATH_ENV

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "ned" / "app" / "static" / "app.js").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "ned" / "app" / "templates" / "index.html").read_text(encoding="utf-8")
ANALYZER_SOURCE = (ROOT / "ned" / "app" / "core" / "analyzer.py").read_text(encoding="utf-8")
DETECTOR_SOURCE = (ROOT / "ned" / "app" / "core" / "relative_time.py").read_text(encoding="utf-8")
CAPTURE = (ROOT / "docs" / "cli-extreme.txt").read_text(encoding="utf-8")


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


def archive(client: TestClient, casebook_id: str, text: str, **extra: object) -> dict:
    body: dict[str, object] = {"text": text, "action_id": uuid.uuid4().hex}
    body.update(extra)
    response = client.post(f"/api/casebook/{casebook_id}/archive", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def make_casebook(client: TestClient) -> str:
    return client.post("/api/casebook", json={"label": "小 X"}).json()["casebook_id"]


# ------------------------------------------------------------------- the detector ---
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("她昨天说她喜欢我", ("昨天",)),
        ("前天她把我微信删了", ("前天",)),
        ("上周她记得我生日", ("上周",)),
        ("去年我们在一起了", ("去年",)),
        ("最近她总是主动找我", ("最近",)),
        ("上个月她把我删了", ("上个月",)),
        ("她刚才说我们只是朋友", ("刚才",)),
        ("前几天她说想见我", ("前几天",)),
        ("she said yesterday that she liked me", ("yesterday",)),
        ("Last week she removed me", ("last week",)),
    ],
)
def test_the_wording_is_recognised(text: str, expected: tuple[str, ...]) -> None:
    assert relative_time_cues(text) == expected
    assert has_relative_time(text) is True


def test_the_longest_wording_wins_and_order_is_kept() -> None:
    assert relative_time_cues("大前天她找我，昨天她又找我") == ("大前天", "昨天")
    assert relative_time_cues("她昨天找我，昨天又找我") == ("昨天",)


@pytest.mark.parametrize(
    "text",
    [
        "她记得我生日",
        "她说我们只是朋友",
        "我们分手了",
        "她妈妈反对我们在一起",
        "2026-08-03 她说喜欢我",
        "她说她喜欢我",
    ],
)
def test_a_text_without_relative_wording_has_no_cue(text: str) -> None:
    assert relative_time_cues(text) == ()
    assert has_relative_time(text) is False


def test_the_detector_has_no_clock_and_produces_no_date() -> None:
    """A hint about wording, not a conversion: no date type, no clock, no arithmetic."""

    # no import of any clock or date library, and no clock call anywhere in the module
    imports = [
        line for line in DETECTOR_SOURCE.splitlines() if line.startswith(("import ", "from "))
    ]
    assert imports == ["from __future__ import annotations"], imports
    for forbidden in (".now(", "utcnow", "strftime", "fromtimestamp", "timedelta("):
        assert forbidden not in DETECTOR_SOURCE, forbidden
    for cue in relative_time_cues("昨天她找我"):
        assert isinstance(cue, str)
        assert not any(character.isdigit() for character in cue)


# ------------------------------------------------------------------ the archive ---
def test_a_relative_clue_without_a_date_is_recorded_as_a_hint(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    outcome = archive(client, casebook_id, "她昨天说她喜欢我")

    assert outcome["occurred_source"] == "input_relative"
    assert outcome["occurred_at"] is None
    assert outcome["relative_time_cues"] == ["昨天"]
    case_file = client.get(f"/api/casebook/{casebook_id}").json()["case_files"][0]
    assert case_file["occurred_source"] == "input_relative"
    assert case_file["occurred_at"] is None
    assert case_file["occurred_precision"] == "unknown"


def test_the_reader_can_supply_the_date_and_it_is_kept_exactly(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    outcome = archive(
        client,
        casebook_id,
        "她昨天说她喜欢我",
        occurred={
            "occurred_at": "2026-09-17",
            "occurred_precision": "day",
            "occurred_source": "user",
        },
    )
    assert outcome["occurred_source"] == "user"
    assert outcome["occurred_at"] == "2026-09-17"
    assert outcome["occurred_precision"] == "day"
    # the hint is still reported: it describes the text, not the stored date
    assert outcome["relative_time_cues"] == ["昨天"]
    case_file = client.get(f"/api/casebook/{casebook_id}").json()["case_files"][0]
    assert case_file["occurred_at"] == "2026-09-17"
    assert case_file["occurred_source"] == "user"


def test_a_date_is_never_padded_into_a_finer_one(client: TestClient) -> None:
    """No midnight, no UTC marker, no finer precision than the reader gave."""

    casebook_id = make_casebook(client)
    for occurred_at, precision in (
        ("2026-09-17T00:00:00", "day"),
        ("2026-09-17T00Z", "day"),
        ("2026-09-17T00:00:00+08:00", "second"),
        ("2026-09", "week"),
        ("2026-09-17", "day "),
    ):
        response = client.post(
            f"/api/casebook/{casebook_id}/archive",
            json={
                "text": "她昨天说她喜欢我",
                "action_id": uuid.uuid4().hex,
                "occurred": {
                    "occurred_at": occurred_at,
                    "occurred_precision": precision,
                    "occurred_source": "user",
                },
            },
        )
        assert response.status_code == 422, (occurred_at, precision, response.text[:120])


def test_no_cue_and_no_date_stays_unknown(client: TestClient) -> None:
    casebook_id = make_casebook(client)
    outcome = archive(client, casebook_id, "她记得我生日")
    assert outcome["occurred_source"] == "unknown"
    assert outcome["occurred_at"] is None
    assert outcome["relative_time_cues"] == []


# --------------------------------------------------------------------- the hint ---
def test_the_hint_endpoint_answers_without_touching_anything(client: TestClient) -> None:
    answer = client.post("/api/casebook/relative-time", json={"text": "她昨天说她喜欢我"}).json()
    assert answer == {"cues": ["昨天"], "has_relative_time": True, "note_code": "relative_time_cue"}
    quiet = client.post("/api/casebook/relative-time", json={"text": "她记得我生日"}).json()
    assert quiet["has_relative_time"] is False
    assert quiet["cues"] == []


def test_the_hint_endpoint_creates_no_database(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even with the casebook off it answers, and it still writes nothing anywhere."""

    monkeypatch.delenv(CASEBOOK_ENV, raising=False)
    target = workdir / "data" / "casebook.sqlite3"
    monkeypatch.setenv(CASEBOOK_PATH_ENV, str(target))
    with TestClient(create_app()) as off_client:
        answer = off_client.post("/api/casebook/relative-time", json={"text": "她昨天说她喜欢我"})
        assert answer.status_code == 200
    assert not target.exists()
    assert not target.parent.exists()


def test_the_hint_endpoint_is_additive_on_the_casebook_router(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/casebook/relative-time" in schema["paths"]
    assert client.get("/api/version").json()["api_version"] == "1"


# ------------------------------------------------- the longitudinal consequence ---
def _entry(
    entry_id: str, text: str, occurred: str | None, precision: str, source: str
) -> ReviewRecord:
    """One recorded entry, as the longitudinal review reads it."""

    analyzer = NedAnalyzer()
    material = analyzer.analyze_text(text).materials[0]
    return ReviewRecord(
        item_kind="entry",
        item_id=entry_id,
        case_file_id="cf_" + entry_id,
        entry_kind="event",
        material_kind=material.material_kind,
        reported_content=material.reported_content,
        occurred_at=occurred,
        occurred_precision=precision,
        occurred_source=source,
        recorded_verdict_code=analyzer.analyze_text(text).verdict.code,
        recorded_signal_type=str(analyzer.analyze_text(text).signal_type),
        material=MaterialFacts(
            material_kind=material.material_kind,
            origin_rule_id=material.origin_rule_id,
            polarity=str(material.polarity),
            proposition_owner=material.proposition_owner,
            target=material.target,
        ),
    )


def _review(entry_occurred: str | None, precision: str, source: str):
    entry = _entry("en_1", "她记得我生日", entry_occurred, precision, source)
    boundary = _entry("en_2", "她说我们只是朋友", "2026-08-10", "day", "user")
    current = current_case_facts(materials=[], signal_type="initiation", verdict_code="ped.ren_hao")
    return build_casebook_review(
        casebook_id="cb_x",
        casebook_label="小 X",
        current=current,
        records=[entry, boundary],
        case_files_read=2,
        entries_read=2,
    )


def test_an_undated_relative_entry_is_never_ordered() -> None:
    review = _review(None, "unknown", "input_relative")
    row = next(item for item in review.items if item.item_id == "en_1")
    assert row.relation is Relation.NOT_COMPARABLE
    assert review.counts.superseded == 0
    assert review.governing is None


def test_the_same_entry_with_a_supplied_date_can_be_superseded() -> None:
    """Once the reader dates it, the comparator decides - and here it proves the boundary later."""

    review = _review("2026-07-12", "day", "user")
    row = next(item for item in review.items if item.item_id == "en_1")
    assert row.relation is Relation.SUPERSEDED
    assert row.superseded_by == "en_2"


def test_a_supplied_date_later_than_the_boundary_keeps_the_boundary_from_governing() -> None:
    review = _review("2026-09-01", "day", "user")
    assert review.counts.superseded == 0
    assert review.governing is None
    assert review.governing_reason == "later_record_after_boundary"


# ------------------------------------------------------------------ the copy ---
def test_the_payload_no_longer_claims_there_is_no_database() -> None:
    analyzer = NedAnalyzer()
    notes = " ".join(analyzer.analyze_text("她说她喜欢我").mode_notes)
    assert "NED has no database" not in notes
    assert "casebook" in notes
    assert "analysing stores nothing" in notes


def test_no_present_tense_claim_says_nothing_is_stored() -> None:
    """The files that make present-tense claims about this product."""

    for relative in ("README.md", "RELEASE_CHECKLIST.md", "CONTRIBUTING.md"):
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert "no database" not in content, relative
        assert "no files written from your input, no accounts" not in content, relative
    assert "no database, no accounts" not in ANALYZER_SOURCE
    assert "NED has no database" not in CAPTURE


def test_the_documents_now_describe_the_opt_in_casebook() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "casebook" in readme
    assert "NED_CASEBOOK=on" in readme
    assert "writes nothing to disk" in readme


def test_the_cli_capture_matches_the_current_engine_note() -> None:
    assert "analysing stores nothing and sends nothing anywhere" in CAPTURE
    assert "explicit_affection" in CAPTURE


# --------------------------------------------------------------------- the web ---
def test_the_client_asks_for_the_hint_once_and_never_fills_the_date() -> None:
    assert SCRIPT.count('"/api/casebook/relative-time"') == 1
    module = SCRIPT[
        SCRIPT.index(
            "/* -------------------------------------------------------------- casebook */"
        ) :
    ]
    module = module[
        : module.index(
            "/* ------------------------------------------------------------- hall copy */"
        )
    ]
    assert "function showRelativeHint" in module
    # the only writer of the date control is the reader - and the chooser empties it on open, so a
    # date confirmed for one case cannot be inherited by the next
    assert "casebook-occurred').value =" not in SCRIPT
    assert 'casebook-occurred").value =' not in SCRIPT
    assert 'setValue("casebook-occurred"' not in SCRIPT
    module = SCRIPT[
        SCRIPT.index(
            "/* -------------------------------------------------------------- casebook */"
        ) :
    ]
    module = module[
        : module.index(
            "/* ------------------------------------------------------------- hall copy */"
        )
    ]
    # read once when filing, cleared once when the chooser opens
    assert module.count('$("casebook-occurred")') == 2
    assert 'dateField.value = ""' in module
    assert 'newNameField.value = ""' in module


def test_the_hint_is_rendered_from_the_catalogue() -> None:
    from ned.app.ui import personality as p

    assert 'id="casebook-relative-hint"' in TEMPLATE
    assert 'casebookCopy("casebook_relative_hint")' in SCRIPT
    for key in (
        "casebook_relative_hint",
        "casebook_relative_filed",
        "casebook_dated_filed",
        "casebook_occurred_by_user",
    ):
        assert key in p.FRONT_DESK_COPY, key
        values = p.FRONT_DESK_COPY[key]
        assert values["zh"] != values["en"]
        assert values["zh"].strip() and values["en"].strip()


def test_the_hint_copy_says_ned_will_not_convert_the_date() -> None:
    from ned.app.ui import personality as p

    hint = p.FRONT_DESK_COPY["casebook_relative_hint"]
    assert "不会自行换算日期" in hint["zh"]
    assert "does not convert it into a date" in hint["en"]
    filed = p.FRONT_DESK_COPY["casebook_relative_filed"]
    assert "没有换算日期" in filed["zh"]


def test_the_panel_shows_that_the_reader_supplied_the_date() -> None:
    assert "casebook_occurred_by_user" in SCRIPT
    assert 'txt(caseFile.occurred_source) === "user"' in SCRIPT


def test_the_default_analyse_payload_gains_nothing(client: TestClient) -> None:
    payload = client.post("/api/analyze", json={"text": "她昨天说她喜欢我"}).json()
    assert "relative_time" not in json.dumps(payload)
    assert "cues" not in payload
