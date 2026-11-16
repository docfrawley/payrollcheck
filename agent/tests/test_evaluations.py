"""Evaluations: the agent works copies of a labelled set's cases, and the
backend scores them."""

from functools import partial

import pytest
from langchain_core.exceptions import ModelRateLimitError
from langgraph.checkpoint.memory import InMemorySaver

from agent import api, dispatcher, harness
from agent.tests.dispatching import dispatch, new_evaluation
from agent.tests.invoking import ACCEPTED, work_run
from agent.tests.queue_setup import leave_received
from agent.tests.records import case_of, model_calls_of, work_times_of
from agent.tests.stubs import agent_on, swarm, work
from backend.tests.dashboard_reads import evaluations
from backend.tests.run_requests import get_evaluation, latest_dispatch, queue


def test_an_evaluation_the_app_created_worked_by_the_agent(client, serve):
    before = queue(client)
    run = new_evaluation()
    copies = [copy["case_id"] for copy in run["cases"]]
    failed, *worked = copies
    outage = RuntimeError("503: The model is unavailable")
    model = swarm({copy: work() for copy in worked} | {failed: [outage, outage]})
    agent = serve(model, InMemorySaver())
    assert agent.invoke(work_run(run["run_id"])).json() == ACCEPTED

    [listed] = evaluations(client)
    assert (listed["status"], listed["agents"], listed["size"]) == ("finished", 5, 10)
    assert queue(client) == before
    assert case_of(client, failed)["agent_failed"] is True
    evaluation = get_evaluation(client, listed["run_id"])
    # The check tools find every label of a worked copy to the cent, end to end.
    for case in evaluation["cases"]:
        if case["case_id"] != failed:
            results = {label["result"] for label in case["labels"]}
            assert results <= {"caught"}, case["case_id"]
    measures = evaluation["measures"]
    cost = sum(c["cost"] for i in copies for c in model_calls_of(i))
    seconds = sum(w["seconds"] for i in copies for w in work_times_of(i))
    assert measures["model_cost_per_case"] == pytest.approx(cost / 10)
    assert measures["seconds_per_case"] == pytest.approx(seconds / 10)
    # Two model calls a worked copy, and the screening's one an attempt: the
    # failed copy's model calls raised before they were recorded.
    assert cost == pytest.approx(0.0042 * (2 * 9 + 9 + 2))


def test_a_dispatch_leaves_an_evaluations_copies_alone(client):
    leave_received("PC-1205")
    evaluation = new_evaluation()
    first, second = (copy["case_id"] for copy in evaluation["cases"][:2])
    client.post(f"/api/cases/{first}/start", json={"thread_id": "copy-thread"})
    client.post(f"/api/runs/{evaluation['run_id']}/finish")
    dispatch(swarm({"PC-1205": work()}))

    assert [c["case_id"] for c in latest_dispatch(client)["cases"]] == ["PC-1205"]
    copy = case_of(client, first)
    assert (copy["status"], copy["thread_id"]) == ("in_progress", "copy-thread")
    assert case_of(client, second)["status"] == "received"


def test_the_agent_cant_read_the_scoreboard():
    for name in (
        "list_evaluations",
        "get_evaluation",
        "start_dispatch",
        "start_evaluation",
        "get_configuration",
        "get_version_details",
    ):
        assert not hasattr(api, name)


def test_a_copy_still_failing_after_its_tries_is_left_in_progress(client):
    run = new_evaluation()
    limited = ModelRateLimitError("429 Too Many Requests")
    scripts = {copy["case_id"]: work() for copy in run["cases"]}
    stuck = run["cases"][0]["case_id"]
    model = swarm(scripts | {stuck: [limited] * 3})
    work_copy = partial(
        harness.work_in_run, new_agent=partial(agent_on, model, InMemorySaver())
    )
    reports = dispatcher.work_run(run, work_copy)

    assert (
        f"{stuck}  left in progress: ModelRateLimitError: 429 Too Many Requests"
        in reports
    )
    assert case_of(client, stuck)["status"] == "in_progress"
