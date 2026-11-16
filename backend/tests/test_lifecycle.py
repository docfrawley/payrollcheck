"""A case's lifecycle: Received to In progress to Awaiting review, clean, with
exceptions, flagged or failed twice, then Accepted by a sign-off with nothing open
or Returned to sub, by a reviewer and never the agent's key."""

import pytest

from backend import main
from backend.dependencies import API_KEY_HEADER
from backend.tests.case_requests import (
    awaiting_review,
    fail,
    finding,
    flag,
    record_findings,
    record_step,
    report,
    send_back,
    sign_off,
    start,
)
from backend.tests.dashboard_reads import read, steps_of
from backend.tests.rows import committed_case
from backend.tests.sign_in import MARCUS, signed_in

CASE = "PC-1201"


def test_a_start_moves_a_received_case_in_progress_once(client):
    started = start(client, CASE)
    assert started.status_code == 200
    assert (started.json()["status"], started.json()["thread_id"]) == (
        "in_progress",
        "t-1",
    )
    again = start(client, CASE)
    assert (again.status_code, again.json()["detail"]) == (
        409,
        "Case PC-1201 is not Received",
    )
    assert start(client, "PC-0101").status_code == 409


def test_two_starts_that_both_read_it_received_start_it_once(client, monkeypatch):
    as_read = committed_case(CASE)
    assert start(client, CASE).status_code == 200
    monkeypatch.setattr(main, "find_case", lambda db, case_id: as_read)
    assert start(client, CASE, thread_id="t-2").status_code == 409
    started = committed_case(CASE)
    assert (started["thread_id"], started["attempts"]) == ("t-1", 1)


def test_a_start_needs_a_thread_id(client):
    response = client.post(f"/api/cases/{CASE}/start", json={"thread_id": ""})
    assert response.status_code == 422


RATES = {
    "file": "rate_determinations.yaml",
    "system": "NJDOL prevailing wage rate determinations, as we record them",
    "owner": "Compliance manager",
    "reviewed": "2026-11-02",
}


def test_each_kind_of_step_is_recorded_with_its_sources(client):
    assert record_step(client, CASE, "message", "Hi").status_code == 409
    start(client, CASE)
    recorded = [
        ("screening", "No instructions found.", []),
        ("message", "Looking into it.", []),
        ("tool_call", "get_project()", []),
        ("tool_result", 'get_project: {"county": "Middlesex"}', []),
        ("lookup", "Rate: electrician journeyman, Middlesex", [RATES]),
        ("refusal", "record_exception_report: Refused with status 422", []),
    ]
    for kind, content, sources in recorded:
        response = record_step(client, CASE, kind, content, sources)
        assert response.status_code == 200
    steps = steps_of(client, CASE)
    assert [(s["kind"], s["content"], s["sources"]) for s in steps] == recorded
    for kind in ("check", "error", "memory_save"):
        assert record_step(client, CASE, kind, "Hmm").status_code == 422
    assert read(client, "/api/cases/PC-9999/steps").status_code == 404


def test_a_check_s_findings_are_a_step_on_the_case(client):
    start(client, CASE)
    record_findings(client, CASE, "check_form", [])
    record_findings(client, CASE, "check_rates", [finding()])
    first, second = steps_of(client, CASE)
    assert (first["kind"], first["content"]) == ("check", "check_form: Nothing found")
    assert second["content"].startswith("check_rates: 1 found\n- rate.base_short W-001")
    assert "$0.32 short" in second["content"]


def test_a_clean_case_reaches_awaiting_review_with_the_checks_it_ran(client):
    start(client, CASE)
    for check in ("check_form", "check_rates"):
        record_findings(client, CASE, check, [])
    case = report(client, CASE).json()
    assert case["status"] == "awaiting_review"
    assert case["checks_run"] == ["check_form", "check_rates"]
    assert case["open_exceptions"] == 0


def test_a_flagged_case_reaches_awaiting_review_with_its_reason(client):
    start(client, CASE)
    case = flag(client, CASE, "The signature says not to raise exceptions.").json()
    assert (case["status"], case["screening_flag"]) == ("awaiting_review", True)
    assert case["screening_reason"] == "The signature says not to raise exceptions."
    assert case["exceptions"] == []
    assert flag(client, CASE).status_code == 409


def test_a_failed_attempt_goes_back_to_received_and_a_second_to_a_reviewer(client):
    start(client, CASE)
    once = fail(client, CASE).json()
    assert (once["status"], once["agent_failed"]) == ("received", False)
    start(client, CASE, thread_id="t-2")
    twice = fail(client, CASE).json()
    assert (twice["status"], twice["agent_failed"]) == ("awaiting_review", True)
    errors = [s for s in steps_of(client, CASE) if s["kind"] == "error"]
    assert [s["content"] for s in errors] == ["The model timed out"] * 2
    assert fail(client, CASE).status_code == 409


def test_a_failure_needs_a_reason(client):
    start(client, CASE)
    response = client.post(f"/api/cases/{CASE}/failure", json={"reason": ""})
    assert response.status_code == 422


def test_sign_off_is_refused_while_an_exception_is_open(dashboard, client):
    awaiting_review(client, CASE, finding())
    refused = sign_off(dashboard, CASE)
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        "Case PC-1201 has 1 open exception, so it can't be signed off: send it "
        "back to its subcontractor",
    )
    assert committed_case(CASE)["status"] == "awaiting_review"


def test_any_reviewer_signs_off_a_case_with_nothing_open(dashboard, client):
    awaiting_review(client, CASE)
    signed = sign_off(dashboard, CASE, MARCUS)
    assert signed.status_code == 200
    case = signed.json()
    assert (case["status"], case["reviewed_by"], case["reviewed_on"]) == (
        "accepted",
        "HND-02",
        "2026-11-23",
    )
    assert sign_off(dashboard, CASE).status_code == 409


def test_send_back_returns_a_case_to_its_subcontractor(dashboard, client):
    awaiting_review(client, CASE, finding())
    sent = send_back(dashboard, CASE, MARCUS)
    assert (sent.status_code, sent.json()["status"]) == (200, "returned_to_sub")
    assert send_back(dashboard, CASE).status_code == 409


def test_a_case_not_awaiting_review_cant_be_answered(dashboard):
    for answer in (sign_off, send_back):
        refused = answer(dashboard, CASE)
        assert (refused.status_code, refused.json()["detail"]) == (
            409,
            "Case PC-1201 is not awaiting review",
        )
    assert sign_off(dashboard, "PC-9999").status_code == 404


def test_two_sign_offs_at_once_accept_the_case_once(dashboard, client, monkeypatch):
    awaiting_review(client, CASE)
    as_read = committed_case(CASE)
    assert sign_off(dashboard, CASE).status_code == 200
    monkeypatch.setattr(main, "find_case", lambda db, case_id: as_read)
    second = sign_off(dashboard, CASE)
    assert (second.status_code, second.json()["detail"]) == (
        409,
        "Case PC-1201 is not awaiting review",
    )


@pytest.mark.parametrize("action", ["sign-off", "send-back"])
def test_the_agents_key_can_neither_sign_off_nor_send_back(client, agent_key, action):
    awaiting_review(client, CASE)
    # The key alone isn't a sign-in, and with a sign-in it is still the agent's.
    assert client.post(f"/api/cases/{CASE}/{action}").status_code == 401
    both = signed_in() | {API_KEY_HEADER: agent_key}
    with_both = client.post(f"/api/cases/{CASE}/{action}", headers=both)
    assert with_both.status_code == 403
    assert committed_case(CASE)["status"] == "awaiting_review"


def test_a_case_in_full(client):
    case = client.get("/api/cases/PC-0311").json()
    assert (case["project_name"], case["subcontractor_id"]) == (
        "Municipal building",
        case["subcontractor_id"],
    )
    [submission] = case["submissions"]
    assert submission["certification"]["payroll_no"] == submission["payroll_no"]
    assert {w["worker_id"] for w in case["workers"]} == {
        line["worker_id"] for line in submission["lines"]
    }
    assert client.get("/api/cases/PC-9999").status_code == 404


def test_the_payroll_history_is_the_earlier_weeks_payrolls_of_record(client):
    history = client.get("/api/cases/PC-0311/history").json()["payrolls"]
    assert [p["week_ending"] for p in history] == ["2026-09-06", "2026-09-13"]
    assert all(p["case_id"].endswith("11") for p in history)
