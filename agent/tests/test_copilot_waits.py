"""Waiting for the agent's work in code: the wait for a dispatch the Copilot started,
what needs a reviewer after it, and a run still going or stopped."""

import json
import threading
import time

import pytest

from agent import connection
from agent.copilot import app_api, waiting
from agent.copilot.filters import EVERY_CASE, body
from agent.copilot.needs_a_reviewer import needs_a_reviewer
from agent.tests.copilot_driver import Copilot, started_run
from agent.tests.stubs import call, stub
from backend.tests.case_requests import (
    awaiting_review,
    fail,
    finding,
    flag,
    report,
    start,
)
from backend.tests.run_requests import fail_run, finish, record_cases, run_path
from backend.tests.sign_in import DANA, MARCUS, token

SUMMARY = "PC-1201 has an exception to review and PC-1202 is clean."


@pytest.fixture(autouse=True)
def quick_waits(monkeypatch):
    """Read the run every hundredth of a second, for up to five seconds."""
    monkeypatch.setattr(waiting, "POLL", 0.01)
    monkeypatch.setattr(waiting, "WAIT", 5)


def wait_for_the_run(prompt):
    """The model's call to wait for the run its last tool started."""
    return call("wait_for_run", run_id=json.loads(prompt[-1].text)["run_id"])


class Reads:
    """The test backend, keeping each request the Copilot sends."""

    def __init__(self, backend):
        self.backend = backend
        self.sent: list[tuple[str, str, dict[str, str]]] = []

    def request(self, method, path, headers, **request):
        self.sent.append((method, path, headers))
        return self.backend.request(method, path, headers=headers, **request)


def test_the_wait_for_a_dispatch(client, copilot: Copilot, agent_calls, monkeypatch):
    reads = Reads(connection.backend)
    monkeypatch.setattr(connection, "backend", reads)
    working = []

    def play_the_dispatch_out():
        run_id = started_run(agent_calls)
        record_cases(client, run_id, "PC-1201", "PC-1202")
        while not [s for _, s, _ in reads.sent if s == f"/runs/{run_id}"]:
            time.sleep(0.01)
        conversation = copilot.read(copilot.last_payload()["conversation_id"])
        working.append(conversation["turns"][-1]["steps"][-1])
        awaiting_review(client, "PC-1201", finding())
        awaiting_review(client, "PC-1202")
        finish(client, run_id)

    dispatch = threading.Thread(target=play_the_dispatch_out)
    dispatch.start()
    copilot.model = stub(call("start_dispatch", agents=10), wait_for_the_run, SUMMARY)
    [turn] = copilot.ask("Work the queue with 10 agents and tell me what needs me")[
        "turns"
    ]
    dispatch.join(10)
    [card] = working
    assert (card["tool"], card["status"]) == ("wait_for_run", "working")
    assert [(c["tool"], c["status"]) for c in turn["steps"]] == [
        ("start_dispatch", "done"),
        ("wait_for_run", "done"),
    ]
    assert (turn["answer"], turn["model_calls"]) == (SUMMARY, 3)
    went = json.loads(copilot.model.prompts[2][-1].text)
    assert went["status"] == "finished"
    assert went["summary"] == {
        "with_exceptions": ["PC-1201"],
        "clean": ["PC-1202"],
        "flagged": [],
        "agent_failed": [],
        "unfinished": [],
    }
    needs = went["needs_a_reviewer"]
    assert needs["with_open_exceptions"] == [
        {"case_id": "PC-1201", "open_exceptions": 1, "shortfall": "$0.32"}
    ]
    assert needs["to_sign_off"] == ["PC-1202"]
    assert (needs["screening_flagged"], needs["agent_failed"]) == ([], [])
    assert "PC-1201" not in needs["received"]
    assert "PC-1203" in needs["received"]
    run_reads = [h for _, path, h in reads.sent if path.startswith("/runs/")]
    assert len(run_reads) > 1
    sign_in = copilot.last_payload()["sign_in"]
    assert all(h == {"Authorization": f"Bearer {sign_in}"} for h in run_reads)


def what_needs(email=DANA):
    """What needs the reviewer, worked out as the wait works it out."""
    found = app_api.find_cases(token(email), body(EVERY_CASE))
    return needs_a_reviewer(found)


def test_what_needs_a_reviewer(client):
    """The cases awaiting review with open exceptions and with none, those the
    screening flagged and those the agent failed twice apart, and those Received;
    a case failed once is Received again, and one returned isn't listed."""
    awaiting_review(client, "PC-1201", finding(), finding(worker_id="W-002"))
    awaiting_review(client, "PC-1202")
    start(client, "PC-1203")
    flag(client, "PC-1203")
    for _ in range(2):
        start(client, "PC-1204")
        fail(client, "PC-1204")
    start(client, "PC-1205")
    fail(client, "PC-1205")
    needs = what_needs()
    assert needs["with_open_exceptions"] == [
        {"case_id": "PC-1201", "open_exceptions": 2, "shortfall": "$0.64"}
    ]
    assert needs["to_sign_off"] == ["PC-1202"]
    assert needs["screening_flagged"] == ["PC-1203"]
    assert needs["agent_failed"] == ["PC-1204"]
    assert "PC-1205" in needs["received"]
    assert "PC-0311" not in str(needs)


def test_only_the_received_wave_needs_a_reviewer_in_the_seeded_queue():
    needs = what_needs(MARCUS)
    assert needs["with_open_exceptions"] == needs["to_sign_off"] == []
    assert (needs["screening_flagged"], needs["agent_failed"]) == ([], [])
    assert len(needs["received"]) == 15
    assert all(case_id.startswith("PC-12") for case_id in needs["received"])


def test_a_run_still_going_and_a_run_that_stopped(
    client, copilot: Copilot, agent_calls, monkeypatch
):
    monkeypatch.setattr(waiting, "WAIT", 0.05)
    copilot.model = stub(call("start_dispatch", agents=10), wait_for_the_run, "Still.")
    conversation_id = copilot.ask("Work the queue")["conversation_id"]
    went = json.loads(copilot.model.prompts[2][-1].text)
    assert went["status"] == "running"
    assert went["note"].endswith("Follow it on the queue page.")
    run_id = started_run(agent_calls)
    fail_run(client, run_id, "RuntimeError: The dispatcher broke")
    copilot.model = stub(call("wait_for_run", run_id=run_id), "It stopped.")
    copilot.ask("How did it go?", conversation_id)
    went = json.loads(copilot.model.prompts[1][-1].text)
    assert (went["status"], went["stopped_because"]) == (
        "stopped",
        "RuntimeError: The dispatcher broke",
    )


def test_the_wait_for_an_evaluation_gives_its_measures(
    client, copilot: Copilot, agent_calls
):
    def play_the_evaluation_out():
        run_id = started_run(agent_calls)
        for copy in client.get(run_path(run_id)).json()["cases"]:
            start(client, copy["case_id"])
            report(client, copy["case_id"])
        finish(client, run_id)

    evaluation = threading.Thread(target=play_the_evaluation_out)
    evaluation.start()
    copilot.model = stub(
        call("start_evaluation", evaluation_set="tiny", agents=5),
        wait_for_the_run,
        "Done.",
    )
    copilot.ask("Evaluate the tiny set")
    evaluation.join(10)
    went = json.loads(copilot.model.prompts[2][-1].text)
    assert (went["kind"], went["status"]) == ("evaluation", "finished")
    measures = went["measures"]
    assert (measures["catch_rate"], measures["caught"]) == (0, 0)
    assert measures["labels"] > 0
    assert measures["false_exceptions"] == 0
