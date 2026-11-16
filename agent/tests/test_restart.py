"""The agent stopped partway, by a crash, a restart or Ctrl-C, and carrying on. The
tests stop it with KeyboardInterrupt, which the harness doesn't catch, so the case is
left as a crash leaves it."""

import itertools

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from agent import api, harness
from agent.tests.failures import fail_once
from agent.tests.records import case_of
from agent.tests.stubs import (
    StubModel,
    agent_on,
    call,
    report_all,
    stub,
    work,
)
from backend.tests.dashboard_reads import steps_of


def stop_while_working(case_id, saver, *replies):
    """Work a case until the agent is stopped after the replies given."""
    with pytest.raises(KeyboardInterrupt):
        harness.work_case(
            case_id, None, agent_on(stub(*replies, KeyboardInterrupt()), saver)
        )


def calls_to(monkeypatch, name):
    """Count the calls to one of the backend's operations."""
    calls = []
    function = getattr(api, name)

    def count(**inputs):
        calls.append(tuple(inputs.values()))
        return function(**inputs)

    monkeypatch.setattr(api, name, count)
    return calls


class StopBeforeCheckpoint(InMemorySaver):
    """Saves a step's writes, then stops before saving the checkpoint that follows,
    once a step has recorded the report: the gap a crash can land in."""

    stopping = False

    def put_writes(self, config, writes, task_id, task_path=""):
        super().put_writes(config, writes, task_id, task_path)
        self.stopping = self.stopping or any(c == "status" for c, _ in writes)

    def put(self, config, checkpoint, metadata, new_versions):
        if self.stopping:
            self.stopping = False
            raise KeyboardInterrupt
        return super().put(config, checkpoint, metadata, new_versions)


def test_a_case_stopped_partway_carries_on_from_its_last_step(client):
    saver = InMemorySaver()
    stop_while_working("PC-1203", saver, call("get_case"), call("get_project"))
    stopped = case_of(client, "PC-1203")
    assert (stopped["status"], stopped["attempts"]) == ("in_progress", 1)
    before = steps_of(client, "PC-1203")

    model = stub(report_all())
    line = harness.carry_on("PC-1203", None, agent_on(model, saver))
    assert line == "PC-1203  1 exception, $72.00 short, awaiting review"
    case = case_of(client, "PC-1203")
    assert (case["thread_id"], case["attempts"]) == (stopped["thread_id"], 1)
    first = model.prompts[0]
    assert len([m for m in first if isinstance(m, HumanMessage)]) == 2
    earlier = [m.name for m in first if isinstance(m, ToolMessage)]
    assert earlier == ["get_case", "get_project"]
    steps = steps_of(client, "PC-1203")
    assert steps[: len(before)] == before
    # The report, called and answered, and no check run again.
    assert len(steps) == len(before) + 2
    assert {s["thread_id"] for s in steps} == {case["thread_id"]}
    assert "error" not in {s["kind"] for s in steps}


def test_stopped_just_after_the_report_is_recorded_it_stands(client, monkeypatch):
    saver = InMemorySaver()
    fail_once(
        monkeypatch, api, "record_exception_report", KeyboardInterrupt(), carry_out=True
    )
    with pytest.raises(KeyboardInterrupt):
        harness.work_case("PC-1203", None, agent_on(stub(*work()), saver))
    reported = case_of(client, "PC-1203")
    assert reported["status"] == "awaiting_review"

    line = harness.carry_on("PC-1203", None, agent_on(stub(), saver))
    assert line == "PC-1203  1 exception, $72.00 short, awaiting review"
    case = case_of(client, "PC-1203")
    assert case["exceptions"] == reported["exceptions"]


def test_stopped_after_a_step_was_written_but_before_its_checkpoint(client):
    saver = StopBeforeCheckpoint()
    with pytest.raises(KeyboardInterrupt):
        harness.work_case("PC-1203", None, agent_on(stub(*work()), saver))
    assert case_of(client, "PC-1203")["status"] == "awaiting_review"

    model = stub()
    agent = agent_on(model, saver)
    line = harness.carry_on("PC-1203", None, agent)
    assert line == "PC-1203  1 exception, $72.00 short, awaiting review"
    assert model.prompts == []
    case = case_of(client, "PC-1203")
    assert case["attempts"] == 1
    thread = harness.thread_of(case)
    assert agent.graph.get_state(thread).values["status"] == "awaiting_review"


def test_finished_without_a_report_but_stopped_before_it_was_failed(
    client, monkeypatch
):
    saver = InMemorySaver()
    fail_once(monkeypatch, harness, "settle", KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        harness.work_case(
            "PC-1207", None, agent_on(stub(call("get_case"), "Hmm."), saver)
        )
    assert case_of(client, "PC-1207")["status"] == "in_progress"

    model = stub()
    report = harness.carry_on("PC-1207", None, agent_on(model, saver))
    assert report == (
        "PC-1207  failed: The agent finished without recording an exception report,"
        " back in the queue"
    )
    assert model.prompts == []


def test_a_case_stopped_before_its_first_step_was_saved(client):
    client.post("/api/cases/PC-1205/start", json={"thread_id": "nothing-saved"})
    model = stub(*work())
    report = harness.carry_on("PC-1205", None, agent_on(model))
    assert report == "PC-1205  clean, awaiting review"
    case = case_of(client, "PC-1205")
    assert (case["thread_id"], case["attempts"]) == ("nothing-saved", 1)
    assert model.prompts[0][1].content == "Case PC-1205"


def test_the_model_call_limit_holds_across_a_restart(client):
    saver = InMemorySaver()
    before = 20
    stop_while_working("PC-1207", saver, *(call("get_case") for _ in range(before)))
    endless = StubModel(messages=(call("get_case") for _ in itertools.count()))
    report = harness.carry_on("PC-1207", None, agent_on(endless, saver))
    assert report.startswith("PC-1207  failed: TooManyModelCalls: ")
    assert len(endless.prompts) == harness.CASE_MODEL_CALLS - before


def test_a_case_that_fails_while_carried_on_starts_afresh_next_time(client):
    saver = InMemorySaver()
    stop_while_working("PC-1207", saver, call("get_case"))
    stopped = case_of(client, "PC-1207")
    outage = stub(RuntimeError("503: The model is unavailable"))
    report = harness.carry_on("PC-1207", None, agent_on(outage, saver))
    assert report == (
        "PC-1207  failed: RuntimeError: 503: The model is unavailable,"
        " back in the queue"
    )
    assert len(outage.prompts) == 1

    harness.work_case("PC-1207", None, agent_on(stub(*work()), saver))
    case = case_of(client, "PC-1207")
    assert case["attempts"] == 2
    assert case["thread_id"] != stopped["thread_id"]
