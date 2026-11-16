"""The seed: stage 2's committed output loaded as it is, the history with its
exceptions from the labels, the week-12 wave Received, the labelled sets out of the
queue, the business date, and nothing held out in any list."""

from collections import Counter

from sqlalchemy import func, select

from backend import seed
from backend.database import (
    SCREENING,
    engine,
    exceptions,
    labelled_cases,
    labels,
    submissions,
    versions,
)
from backend.tests.dashboard_reads import read
from backend.tests.rows import count

WEEK_12 = "2026-11-22"


def queue(client):
    return client.get("/api/cases").json()


def test_the_week_12_wave_is_22_received_cases(client):
    wave = [c for c in queue(client) if c["week_ending"] == WEEK_12]
    assert len(wave) == 22
    assert {c["status"] for c in wave} == {"received"}


def test_the_history_as_the_generator_recorded_it(client):
    history = [c for c in queue(client) if c["week_ending"] != WEEK_12]
    assert Counter(c["status"] for c in history) == {
        "accepted": 175,
        "returned_to_sub": 10,
    }
    with engine().connect() as db:
        corrected = db.execute(
            select(submissions.c.case_id)
            .group_by(submissions.c.case_id)
            .having(func.count() == 2)
        ).scalars()
        twice = set(corrected) - {"PC-1206"}
    accepted = {c["case_id"] for c in history if c["status"] == "accepted"}
    assert len(twice) == 20
    assert twice <= accepted


def test_a_corrected_cases_exceptions_are_superseded_and_a_returned_ones_open(
    client,
):
    with engine().connect() as db:
        rows = list(db.execute(select(exceptions)).mappings())
    by_status = Counter(
        (
            row["status"],
            len(client.get(f"/api/cases/{row['case_id']}").json()["submissions"]),
        )
        for row in rows
    )
    assert set(by_status) <= {("superseded", 2), ("open", 1)}
    assert all(row["submission_no"] == 1 for row in rows)
    names = {"Dana Whitfield", "Marcus Oyelaran", "Priya Raman"}
    assert {row["raised_by"] for row in rows} <= names


def test_pc_0311_is_returned_to_sub_with_its_three_open_exceptions(client):
    case = client.get("/api/cases/PC-0311").json()
    assert case["status"] == "returned_to_sub"
    assert case["open_exceptions"] == 3
    assert [e["status"] for e in case["exceptions"]] == ["open"] * 3
    assert {e["severity"] for e in case["exceptions"]} == {"high"}
    assert all(e["citation"] for e in case["exceptions"])


def test_pc_1206_is_received_with_two_submissions(client):
    case = client.get("/api/cases/PC-1206").json()
    assert case["status"] == "received"
    assert [s["submission_no"] for s in case["submissions"]] == [1, 2]
    assert case["latest_submission_no"] == 2


def test_the_two_missing_filings_have_no_case(client):
    for case_id in ("PC-1214", "PC-1223"):
        assert client.get(f"/api/cases/{case_id}").status_code == 404


def test_the_business_date_and_version_1s_parameters(client):
    settings = read(client, "/api/settings").json()
    assert settings["current"]["business_date"] == "2026-11-23"
    with engine().connect() as db:
        parameters = db.execute(select(versions.c.parameters)).scalar_one()
    assert parameters == {"rounding_tolerance_cents": 0}


def test_the_labelled_sets_and_their_labels(client):
    with engine().connect() as db:
        sets = Counter(db.execute(select(labelled_cases.c.labelled_set)).scalars())
        tiny = db.execute(
            select(func.count()).where(labelled_cases.c.tiny)
        ).scalar_one()
        found = list(db.execute(select(labels)).mappings())
    assert sets == {"development": 207, "held_out": 98}
    assert tiny == 10
    development = [x for x in found if x["labelled_set"] == "development"]
    assert sum(x["rule"] != SCREENING for x in development) == 45
    assert sum(x["rule"] == SCREENING for x in development) == 3
    assert count(labels) == len(found)


def test_no_held_out_record_is_in_any_list(client):
    projects = read(client, "/api/projects").json()
    assert [p["project_id"] for p in projects] == ["PRJ-01", "PRJ-02", "PRJ-03"]
    assert all(c["project_id"] in {"PRJ-01", "PRJ-02", "PRJ-03"} for c in queue(client))
    found = read(client, "/api/subcontractors?name=e").json()
    assert found
    assert all(s["subcontractor_id"].startswith("SUB-0") for s in found)
    assert read(client, "/api/subcontractors/SUB-51").status_code == 404


def test_the_seed_command_says_what_it_seeded(capsys):
    seed.main()
    said = capsys.readouterr().out
    assert said.startswith("Seeded 207 cases on 3 projects, 8 subcontractors, 64")
    assert "207 development and 98 held-out labelled cases" in said
