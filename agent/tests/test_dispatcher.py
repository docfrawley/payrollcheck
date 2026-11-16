"""The dispatcher: payroll agents working a dispatch at once, with retries."""

import operator
import time
from datetime import timedelta
from typing import Annotated, Any, TypedDict, cast

import pytest
from langchain_core.exceptions import ModelRateLimitError, ModelTimeoutError
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send

from agent import api, dispatcher, harness
from agent.tests.dispatching import dispatch
from agent.tests.failures import fail_once
from agent.tests.queue_setup import leave_received
from agent.tests.records import case_of, work_times_of
from agent.tests.stubs import agent_on, call, report_all, stub, swarm, work
from backend.tests.case_requests import sign_off
from backend.tests.dashboard_reads import steps_of
from backend.tests.rows import run_heard
from backend.tests.run_requests import latest_dispatch


def tries_on(model, case_id):
    """Count the model calls a case's agents made."""
    return sum(prompt[1].content == f"Case {case_id}" for prompt in model.prompts)


def test_the_graph(monkeypatch, no_waits):
    monkeypatch.setattr(dispatcher, "RETRY", no_waits)
    graph = dispatcher.dispatcher()
    drawn = graph.get_graph()
    assert set(drawn.nodes) == {
        "__start__",
        "list_cases",
        "work_case",
        "finish_run",
        "__end__",
    }
    edges = {(e.source, e.target, e.conditional) for e in drawn.edges}
    assert edges == {
        ("__start__", "list_cases", False),
        ("list_cases", "work_case", True),
        ("list_cases", "finish_run", True),
        ("work_case", "finish_run", False),
        ("finish_run", "__end__", False),
    }
    [retry] = graph.nodes["work_case"].retry_policy or []
    assert (retry.max_attempts, retry.initial_interval) == (3, 10)
    assert retry.retry_on == harness.TRANSIENT


def test_the_tests_retry_without_waiting():
    retry = dispatcher.RETRY
    assert (retry.initial_interval, retry.jitter) == (0, False)
    assert (retry.max_attempts, retry.retry_on) == (3, harness.TRANSIENT)


def test_never_more_than_n_payroll_agents_at_once(client):
    ids = ["PC-1205", "PC-1206", "PC-1207", "PC-1212", "PC-1217", "PC-1218"]
    leave_received(*ids)
    scripts = {case_id: work() for case_id in ids}
    model = swarm(scripts, pause=0.05, fill=3)
    reports = dispatch(model, agents=3)

    assert model.most_at_once == 3
    assert sorted(reports) == [f"{case_id}  clean, awaiting review" for case_id in ids]
    cases = [case_of(client, case_id) for case_id in ids]
    assert {c["status"] for c in cases} == {"awaiting_review"}
    assert len({c["thread_id"] for c in cases}) == len(ids)
    finished = latest_dispatch(client)
    assert (finished["status"], finished["agents"]) == ("finished", 3)


def test_a_dispatch_works_the_received_and_in_progress_cases_oldest_first(client):
    leave_received("PC-1205", "PC-1206", "PC-1207", "PC-1219", "PC-1220", "PC-1221")
    harness.work_case("PC-1206", None, agent_on(stub(*work())))
    client.post("/api/cases/PC-1220/start", json={"thread_id": "t-1220"})

    worked = ["PC-1205", "PC-1207", "PC-1219", "PC-1220", "PC-1221"]
    dispatch(swarm({case_id: work() for case_id in worked}))

    assert [c["case_id"] for c in latest_dispatch(client)["cases"]] == worked
    assert case_of(client, "PC-1220")["thread_id"] == "t-1220"
    assert case_of(client, "PC-1206")["attempts"] == 1
    assert case_of(client, "PC-1224")["status"] == "awaiting_review"


def test_a_rate_limit_waits_and_carries_the_case_on(client):
    leave_received("PC-1205")
    limited = ModelRateLimitError("429 Too Many Requests")
    model = swarm({"PC-1205": [call("get_case"), limited, report_all()]})
    assert dispatch(model) == ["PC-1205  clean, awaiting review"]

    case = case_of(client, "PC-1205")
    assert (case["status"], case["attempts"]) == ("awaiting_review", 1)
    steps = steps_of(client, "PC-1205")
    assert {s["thread_id"] for s in steps} == {case["thread_id"]}
    assert "error" not in {s["kind"] for s in steps}
    run_id = latest_dispatch(client)["run_id"]
    assert [w["run_id"] for w in work_times_of("PC-1205")] == [run_id, run_id]


@pytest.mark.parametrize(
    "error",
    [ModelRateLimitError("429 Too Many Requests"), ModelTimeoutError("Timed out")],
)
def test_a_case_still_failing_after_its_tries_is_left_in_progress(client, error):
    leave_received("PC-1205", "PC-1206")
    model = swarm({"PC-1205": [error] * 3, "PC-1206": work()})
    began = time.monotonic()
    reports = dispatch(model)
    assert time.monotonic() - began < 5

    left = f"PC-1205  left for the next dispatch: {type(error).__name__}: {error}"
    assert sorted(reports) == [left, "PC-1206  clean, awaiting review"]
    assert tries_on(model, "PC-1205") == 3
    case = case_of(client, "PC-1205")
    assert (case["status"], case["attempts"]) == ("in_progress", 1)
    assert "error" not in {s["kind"] for s in steps_of(client, "PC-1205")}
    assert case_of(client, "PC-1206")["status"] == "awaiting_review"
    assert latest_dispatch(client)["status"] == "finished"


def test_a_case_that_fails_is_tried_once_more_in_the_same_dispatch(client):
    leave_received("PC-1205", "PC-1207")
    outage = RuntimeError("503: The model is unavailable")
    model = swarm({"PC-1205": [outage, *work()], "PC-1207": [outage, outage]})
    reports = dispatch(model)

    assert sorted(reports) == [
        "PC-1205  clean, awaiting review",
        "PC-1207  failed: RuntimeError: 503: The model is unavailable,"
        " left for a reviewer",
    ]
    again = case_of(client, "PC-1205")
    assert (again["status"], again["attempts"]) == ("awaiting_review", 2)
    steps = steps_of(client, "PC-1205")
    # Each attempt starts with the screening.
    kinds = [s["kind"] for s in steps]
    assert kinds[:9] == ["screening"] + ["check"] * 8
    assert kinds[9:11] == ["error", "screening"]
    assert steps[-1]["thread_id"] == again["thread_id"] != steps[0]["thread_id"]
    left = case_of(client, "PC-1207")
    assert (left["status"], left["agent_failed"], left["attempts"]) == (
        "awaiting_review",
        True,
        2,
    )
    assert tries_on(model, "PC-1207") == 2


def test_a_case_started_elsewhere_is_reported_and_the_rest_worked(client, monkeypatch):
    leave_received("PC-1205", "PC-1206")
    start_case = api.start_case

    def started_elsewhere(case_id, thread_id):
        if case_id == "PC-1206":
            start_case(case_id, "another-process")
        return start_case(case_id, thread_id)

    monkeypatch.setattr(api, "start_case", started_elsewhere)
    reports = dispatch(swarm({"PC-1205": work()}))

    assert sorted(reports) == [
        "PC-1205  clean, awaiting review",
        "PC-1206  left for the next dispatch: Refused: 409: Case PC-1206 is not"
        " Received",
    ]
    assert case_of(client, "PC-1206")["thread_id"] == "another-process"
    assert latest_dispatch(client)["status"] == "finished"


class Work(TypedDict):
    items: list[str]
    done: Annotated[list[str], operator.add]


class Item(TypedDict):
    item: str


def test_langgraph_raises_an_error_its_handler_took_beside_another_worker():
    """LangGraph 1.2.12 still raises from invoke an error a node's error_handler
    took, when the node runs beside another, so the dispatcher doesn't use one.
    When this test fails, a release has fixed it."""
    handled = []

    def fan(state: Work) -> list[Send]:
        return [Send("work", Item(item=item)) for item in state["items"]]

    def work(state: Item) -> dict[str, list[str]]:
        if state["item"] == "bad":
            raise ValueError("bad")
        return {"done": [state["item"]]}

    def handle(state: Item, error: NodeError) -> Command:
        handled.append(state["item"])
        return Command(update={"done": ["handled"]})

    builder = StateGraph(Work)
    # The NodeError parameter is as LangGraph's docs give it; its types don't allow it.
    builder.add_node("work", work, error_handler=cast(Any, handle))
    builder.add_conditional_edges(START, fan, ["work"])
    builder.add_edge("work", END)
    graph = builder.compile()

    assert graph.invoke({"items": ["bad"], "done": []})["done"] == ["handled"]
    handled.clear()
    with pytest.raises(ValueError, match="bad"):
        graph.invoke({"items": ["bad", "good"], "done": []})
    assert handled == ["bad"]


def test_a_dispatch_stopped_partway_is_finished_by_the_next(client):
    leave_received("PC-1205", "PC-1224", "PC-1206")
    saver = InMemorySaver()
    harness.work_case("PC-1224", None, agent_on(stub(*work()), saver))
    model = swarm(
        {
            "PC-1205": [call("get_case"), KeyboardInterrupt(), report_all()],
            "PC-1206": [call("get_case"), KeyboardInterrupt(), report_all()],
        },
        pause=0.05,
    )
    with pytest.raises(KeyboardInterrupt):
        dispatch(model, saver, agents=2)
    stopped = {i: case_of(client, i) for i in ("PC-1205", "PC-1206")}
    assert {c["status"] for c in stopped.values()} == {"in_progress"}
    sign_off(client, "PC-1224")
    assert case_of(client, "PC-1224")["status"] == "accepted"
    # The agent stopped answering, so the next start marks the dispatch stopped.
    first = latest_dispatch(client)["run_id"]
    run_heard(first, timedelta(minutes=6))

    # The sign-off accepted PC-1224, so the next dispatch leaves it alone.
    reports = dispatch(model, saver, agents=2)
    assert client.get(f"/api/runs/{first}").json()["stopped_because"] == (
        "The agent stopped answering"
    )
    assert sorted(reports) == [
        "PC-1205  clean, awaiting review",
        "PC-1206  clean, awaiting review",
    ]
    for case_id, before in stopped.items():
        case = case_of(client, case_id)
        assert (case["status"], case["attempts"]) == ("awaiting_review", 1)
        assert case["thread_id"] == before["thread_id"]
    assert case_of(client, "PC-1224")["reviewed_by"] == "HND-01"


def test_a_report_the_app_never_got_is_made_again_by_the_next_dispatch(
    client, monkeypatch
):
    leave_received("PC-1205")
    lost = RuntimeError("The connection was lost")
    fail_once(monkeypatch, api, "record_exception_report", lost)
    first = harness.work_case("PC-1205", None, agent_on(stub(*work())))
    assert first == (
        "PC-1205  failed: RuntimeError: The connection was lost, back in the queue"
    )
    assert dispatch(stub(*work())) == ["PC-1205  clean, awaiting review"]
    assert case_of(client, "PC-1205")["attempts"] == 2


def test_a_dispatch_with_nothing_to_work_finishes(client):
    leave_received()
    assert dispatch(stub()) == []
    finished = latest_dispatch(client)
    assert (finished["status"], finished["cases"]) == ("finished", [])
    assert finished["summary"]["unfinished"] == []
