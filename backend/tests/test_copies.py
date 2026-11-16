"""An evaluation's copies: each a Received case of its own holding the submissions
its original had before review, its history from its own labelled set, nothing the
agent's key reads holding anything from the labels, and no reviewer's answer."""

import json

from sqlalchemy import select

from backend.database import engine, labels
from backend.tests.case_requests import awaiting_review, send_back, sign_off
from backend.tests.run_requests import (
    create_evaluation,
    fail_run,
    start_evaluation,
)


def copies(client, evaluation_set):
    """An evaluation's copies, stopped at once so another can start."""
    run = create_evaluation(client, evaluation_set).json()
    fail_run(client, run["run_id"])
    return run["cases"]


def test_the_tiny_set_is_ten_development_copies_numbered_by_the_evaluation(client):
    first = copies(client, "tiny")
    assert len(first) == 10
    assert all(c["case_id"].endswith("-E1") for c in first)
    assert {c["status"] for c in first} == {"received"}
    second = create_evaluation(client, "tiny").json()
    assert second["number"] == 2
    assert second["cases"][0]["case_id"].endswith("-E2")


def test_the_whole_sets(client):
    assert len(copies(client, "development")) == 207
    assert len(copies(client, "held_out")) == 98


def test_a_copy_holds_what_its_original_had_before_review(client):
    run = create_evaluation(client, "development").json()
    found = {c["case_id"].rsplit("-E", 1)[0]: c["case_id"] for c in run["cases"]}
    corrected = client.get(f"/api/cases/{found['PC-0311']}").json()
    assert [s["submission_no"] for s in corrected["submissions"]] == [1]
    assert corrected["copy_of"] == "PC-0311"
    wave = client.get(f"/api/cases/{found['PC-1206']}").json()
    assert [s["submission_no"] for s in wave["submissions"]] == [1, 2]
    history = client.get("/api/cases/PC-0311").json()
    accepted = next(
        c["case_id"]
        for c in client.get("/api/cases").json()
        if c["status"] == "accepted"
        and len(client.get(f"/api/cases/{c['case_id']}").json()["submissions"]) == 2
    )
    copy = client.get(f"/api/cases/{found[accepted]}").json()
    assert [s["submission_no"] for s in copy["submissions"]] == [1]
    assert copy["exceptions"] == []
    assert history["exceptions"]


def test_a_copies_history_comes_from_its_own_set(client):
    run = create_evaluation(client, "held_out").json()
    later = next(c for c in run["cases"] if c["week_ending"] == "2026-10-11")
    history = client.get(f"/api/cases/{later['case_id']}/history").json()
    assert [p["week_ending"] for p in history["payrolls"]] == ["2026-10-04"]
    assert history["payrolls"][0]["case_id"].startswith("PC-5")
    project = client.get(f"/api/projects/{later['project_id']}").json()
    assert project["project_id"].startswith("PRJ-5")


def test_nothing_the_agents_key_reads_holds_the_labels(client):
    run = create_evaluation(client, "development").json()
    with engine().connect() as db:
        shortfalls = {
            str(x)
            for x in db.execute(select(labels.c.expected_shortfall_cents)).scalars()
            if x and x > 999
        }
    for copy in run["cases"][:40]:
        case_id = copy["case_id"]
        project_id = copy["project_id"]
        read = [
            client.get(f"/api/cases/{case_id}"),
            client.get(f"/api/cases/{case_id}/history"),
            client.get(f"/api/projects/{project_id}"),
            client.get(f"/api/projects/{project_id}/subcontractors"),
            client.get(f"/api/runs/{run['run_id']}"),
        ]
        text = json.dumps([r.json() for r in read])
        assert "expected_shortfall" not in text
        assert "labelled_set" not in text
        assert not {f'"shortfall_cents": {s}' for s in shortfalls} & {
            part for part in text.split(", ") if part.startswith('"shortfall_cents"')
        }


def test_a_copy_cant_be_signed_off_or_sent_back(client, dashboard):
    [copy, *_] = copies(client, "tiny")
    awaiting_review(client, copy["case_id"])
    for answer, what in ((sign_off, "signed off"), (send_back, "sent back")):
        refused = answer(dashboard, copy["case_id"])
        assert (refused.status_code, refused.json()["detail"]) == (
            409,
            f"Case {copy['case_id']} is a copy in an evaluation and can't be {what}",
        )


def test_the_queue_leaves_out_the_copies(client):
    create_evaluation(client, "tiny")
    assert not any("-E" in c["case_id"] for c in client.get("/api/cases").json())


def test_an_evaluation_needs_a_known_set_and_1_to_25_agents(client):
    assert start_evaluation(client, "evaluation").status_code == 422
    assert start_evaluation(client, agents=26).status_code == 422
