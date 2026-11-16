"""The cost of each model call and the time spent on each case, with their run."""

import httpx
import pytest

from agent import api, harness
from agent.tests.dispatching import dispatch, new_dispatch
from agent.tests.failures import fail_once
from agent.tests.queue_setup import leave_received
from agent.tests.records import case_of, model_calls_of, work_times_of
from agent.tests.stubs import USAGE, agent_on, call, stub, swarm, work
from backend.tests.case_requests import sign_off
from backend.tests.dashboard_reads import steps_of
from backend.tests.run_requests import latest_dispatch


def test_each_model_call_and_spell_of_work_is_recorded(client):
    harness.work_case("PC-1205", None, agent_on(stub(*work())))
    thread_id = case_of(client, "PC-1205")["thread_id"]
    calls = model_calls_of("PC-1205")
    assert [
        (c["input_tokens"], c["output_tokens"], c["cost"], c["run_id"]) for c in calls
    ] == [(USAGE["prompt_tokens"], USAGE["completion_tokens"], USAGE["cost"], None)] * 3
    assert {c["thread_id"] for c in calls} == {thread_id}
    [spell] = work_times_of("PC-1205")
    assert (spell["thread_id"], spell["run_id"]) == (thread_id, None)


def test_a_run_records_its_calls_and_spells_and_tags_its_traces(client, traces):
    leave_received("PC-1205", "PC-1206")
    dispatch(swarm({"PC-1205": work(), "PC-1206": work()}))

    run_id = latest_dispatch(client)["run_id"]
    for case_id in ("PC-1205", "PC-1206"):
        # The check's call, then the payroll agent's two.
        assert [c["run_id"] for c in model_calls_of(case_id)] == [run_id] * 3
        assert [w["run_id"] for w in work_times_of(case_id)] == [run_id]
    assert [t["langfuse_tags"] for t in traces] == [[run_id], [run_id]]


def test_a_case_worked_alone_has_no_tags(traces):
    harness.work_case("PC-1205", None, agent_on(stub(*work())))
    [trace] = traces
    assert "langfuse_tags" not in trace


def test_both_attempts_of_a_case_are_under_the_run(client):
    leave_received("PC-1207")
    outage = RuntimeError("503: The model is unavailable")
    dispatch(swarm({"PC-1207": [call("get_case"), outage, *work()]}))

    run_id = latest_dispatch(client)["run_id"]
    calls, spells = model_calls_of("PC-1207"), work_times_of("PC-1207")
    assert [c["run_id"] for c in calls] == [run_id] * 5
    assert [s["run_id"] for s in spells] == [run_id] * 2
    first, second = (s["thread_id"] for s in spells)
    assert first != second
    # Each attempt is checked first.
    assert [c["thread_id"] for c in calls] == [first, first, second, second, second]


def test_a_sign_off_adds_no_spell_of_work(client):
    run_id = new_dispatch()["run_id"]
    harness.work_case("PC-1224", run_id, agent_on(stub(*work())))
    sign_off(client, "PC-1224")

    assert case_of(client, "PC-1224")["status"] == "accepted"
    [spell] = work_times_of("PC-1224")
    assert spell["run_id"] == run_id


def test_a_failed_recording_still_settles_the_case(client, monkeypatch):
    lost = httpx.ConnectError("Connection refused")
    fail_once(monkeypatch, api, "record_work_time", lost)
    outage = RuntimeError("503: The model is unavailable")
    with pytest.raises(httpx.ConnectError):
        harness.work_case("PC-1207", None, agent_on(stub(outage)))
    case = case_of(client, "PC-1207")
    assert (case["status"], case["attempts"]) == ("received", 1)
    last = steps_of(client, "PC-1207")[-1]
    assert (last["kind"], last["content"]) == (
        "error",
        "RuntimeError: 503: The model is unavailable",
    )
