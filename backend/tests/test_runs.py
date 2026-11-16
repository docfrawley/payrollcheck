import pytest

from backend import runs
from backend.tests.case_requests import (
    NOTICE,
    fail,
    finding,
    flag,
    record_call,
    record_findings,
    record_time,
    report,
    start,
)
from backend.tests.dashboard_reads import read
from backend.tests.run_requests import (
    create_dispatch,
    dispatch_of,
    fail_run,
    finish,
    latest_dispatch,
    record_cases,
)


def test_no_dispatch_yet(client):
    response = read(client, "/api/dispatches/latest")
    assert response.status_code == 200
    assert response.json() is None


def test_create_a_dispatch(client):
    dispatch = create_dispatch(client, 7).json()
    assert (dispatch["kind"], dispatch["status"], dispatch["agents"]) == (
        "dispatch",
        "running",
        7,
    )
    assert (dispatch["model"], dispatch["reasoning_effort"]) == (
        "openai/gpt-6-luna",
        "none",
    )
    assert dispatch["evaluation_set"] is None
    assert dispatch["number"] == 1
    assert dispatch["started_at"]
    assert (dispatch["finished_at"], dispatch["seconds"], dispatch["summary"]) == (
        None,
        None,
        None,
    )
    assert (dispatch["cases"], dispatch["model_cost"]) == ([], 0)
    assert latest_dispatch(client) == dispatch


@pytest.mark.parametrize("agents", [0, 26])
def test_a_dispatch_has_1_to_25_payroll_agents(client, agents):
    assert create_dispatch(client, agents).status_code == 422
    assert latest_dispatch(client) is None


def test_record_the_cases_of_a_dispatch_in_order(client):
    run_id = create_dispatch(client).json()["run_id"]
    record_cases(client, run_id, "PC-1208", "PC-1201")
    dispatch = record_cases(client, run_id, "PC-1211", "PC-1201", "PC-1208").json()
    assert [c["case_id"] for c in dispatch["cases"]] == [
        "PC-1211",
        "PC-1201",
        "PC-1208",
    ]
    assert latest_dispatch(client)["cases"] == dispatch["cases"]


def test_recording_cases_needs_a_running_dispatch_and_known_cases(client):
    unknown = record_cases(client, "run-9", "PC-1201")
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Run run-9 not found"
    run_id = create_dispatch(client).json()["run_id"]
    missing = record_cases(client, run_id, "PC-1201", "PC-9999")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Case PC-9999 not found"
    finish(client, run_id)
    finished = record_cases(client, run_id, "PC-1201")
    assert finished.status_code == 409
    assert finished.json()["detail"] == f"Run {run_id} is not running"


def test_each_case_shows_where_it_stands_with_its_cost_and_time(client):
    run_id = dispatch_of(client, "PC-1201", "PC-1203")
    start(client, "PC-1201")
    record_call(client, "PC-1201", run_id, cost=0.004)
    record_call(client, "PC-1201", run_id, cost=0.006)
    record_call(client, "PC-1201", None, cost=0.5)
    record_time(client, "PC-1201", run_id, seconds=20)
    record_time(client, "PC-1201", run_id, seconds=21.5)
    report(client, "PC-1201")

    dispatch = latest_dispatch(client)
    first, second = dispatch["cases"]
    assert (first["case_id"], first["subcontractor_name"], first["status"]) == (
        "PC-1201",
        "Garden State Electric LLC",
        "awaiting_review",
    )
    assert (first["seconds"], first["model_cost"]) == (41.5, pytest.approx(0.01))
    assert first["started_at"]
    assert (second["status"], second["started_at"]) == ("received", None)
    assert (second["seconds"], second["model_cost"]) == (0, 0)
    assert dispatch["model_cost"] == pytest.approx(0.01)


def raise_one(client, case_id):
    """Report one finding on a started case, raised."""
    [candidate] = record_findings(client, case_id, findings=[finding()]).json()
    report(client, case_id, raised=[candidate["candidate_id"]], notice=NOTICE)


def test_finishing_a_dispatch_sums_up_its_cases(client):
    started = ["PC-1201", "PC-1202", "PC-1203", "PC-1204", "PC-1205"]
    run_id = dispatch_of(client, *started, "PC-1206")
    for case_id in started:
        start(client, case_id)
    raise_one(client, "PC-1201")
    report(client, "PC-1202")
    flag(client, "PC-1203")
    fail(client, "PC-1204")
    start(client, "PC-1204")
    fail(client, "PC-1204")

    dispatch = finish(client, run_id).json()
    assert dispatch["status"] == "finished"
    assert dispatch["finished_at"]
    assert dispatch["seconds"] >= 0
    assert dispatch["summary"] == {
        "with_exceptions": ["PC-1201"],
        "clean": ["PC-1202"],
        "flagged": ["PC-1203"],
        "agent_failed": ["PC-1204"],
        "unfinished": ["PC-1205", "PC-1206"],
    }
    assert latest_dispatch(client) == dispatch
    again = finish(client, run_id)
    assert again.status_code == 409
    assert again.json()["detail"] == f"Run {run_id} is not running"


def test_finish_needs_a_known_run(client):
    unknown = finish(client, "run-9")
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Run run-9 not found"


def test_a_run_whose_work_failed_is_stopped_with_why(client):
    finished = create_dispatch(client).json()["run_id"]
    finish(client, finished)
    running = create_dispatch(client).json()["run_id"]
    failed = fail_run(client, running)
    assert failed.status_code == 200
    assert (failed.json()["status"], failed.json()["stopped_because"]) == (
        "stopped",
        "RuntimeError: The dispatcher broke",
    )
    assert (failed.json()["finished_at"], failed.json()["seconds"]) == (None, None)
    assert latest_dispatch(client)["stopped_because"] == (
        "RuntimeError: The dispatcher broke"
    )
    for run_id, status in ((running, "stopped"), (finished, "finished")):
        again = fail_run(client, run_id, "RuntimeError: Again")
        assert (again.status_code, again.json()["status"]) == (200, status)
    assert client.get(f"/api/runs/{running}").json()["stopped_because"] == (
        "RuntimeError: The dispatcher broke"
    )
    assert fail_run(client, "run-9").status_code == 404


def test_finishing_a_stopped_run_answers_with_it_still_stopped(client):
    run_id = create_dispatch(client).json()["run_id"]
    fail_run(client, run_id)
    finished = finish(client, run_id)
    assert finished.status_code == 200
    assert finished.json()["status"] == "stopped"
    assert finished.json()["summary"] is None


def test_the_agent_reads_a_run_and_tells_the_app_it_is_working(client, dashboard):
    run_id = create_dispatch(client).json()["run_id"]
    run = client.get(f"/api/runs/{run_id}").json()
    assert (run["run_id"], run["status"], run["kind"]) == (
        run_id,
        "running",
        "dispatch",
    )
    assert client.post(f"/api/runs/{run_id}/heartbeat").status_code == 200
    assert client.get("/api/runs/run-9").status_code == 404
    assert client.post("/api/runs/run-9/heartbeat").status_code == 404
    assert dashboard.get(f"/api/runs/{run_id}").status_code == 401


def test_runs_started_in_the_same_second_keep_their_order(client, monkeypatch):
    monkeypatch.setattr(runs, "now", lambda: "2026-10-02T12:00:00+00:00")
    first = create_dispatch(client).json()
    finish(client, first["run_id"])
    second = create_dispatch(client).json()
    assert second["number"] == first["number"] + 1
    assert latest_dispatch(client)["run_id"] == second["run_id"]
