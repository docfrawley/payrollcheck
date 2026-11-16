"""The payroll agent on a stub model: its graph, a case worked from Received to
Awaiting review through the screening, the check tools and the model's report, the
judgment calls it records, the guarantee's refusals going back to the model, and
how a case ends when something goes wrong."""

import itertools

import pytest
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver

from agent import api, harness
from agent.connection import Refused
from agent.tests.records import case_of
from agent.tests.stubs import (
    INSTRUCTIONS,
    NOTICE,
    StubModel,
    agent_on,
    call,
    candidates_in,
    invented_report,
    report,
    report_all,
    stub,
    work,
)
from backend.tests.dashboard_reads import steps_of

CHECKS = [
    "check_form",
    "check_contractor_registration",
    "check_rates",
    "check_overtime",
    "check_arithmetic",
    "check_apprentices",
    "check_timeliness",
    "check_classification",
]


def work_case(case_id, model, saver=None):
    return harness.work_case(case_id, None, agent_on(model, saver))


def test_the_graph():
    graph = agent_on(stub()).graph.get_graph()
    assert set(graph.nodes) == {
        "__start__",
        "screen",
        "flag",
        "check",
        "agent",
        "tools",
        "__end__",
    }
    edges = {(e.source, e.target, e.conditional) for e in graph.edges}
    assert edges == {
        ("__start__", "screen", False),
        ("screen", "flag", True),
        ("screen", "check", True),
        ("flag", "__end__", False),
        ("check", "agent", False),
        ("agent", "tools", True),
        ("agent", "__end__", True),
        ("tools", "agent", True),
        ("tools", "__end__", True),
    }


def test_a_clean_case_reaches_awaiting_review_with_the_eight_checks_it_ran(
    client, caplog
):
    caplog.set_level("INFO")
    model = stub(*work())
    assert work_case("PC-1205", model) == "PC-1205  clean, awaiting review"
    case = case_of(client, "PC-1205")
    assert (case["status"], case["exceptions"], case["notice"]) == (
        "awaiting_review",
        [],
        None,
    )
    assert case["checks_run"] == CHECKS
    first = model.prompts[0]
    assert first[0] == SystemMessage(INSTRUCTIONS)
    assert first[1].content == "Case PC-1205"
    assert first[2].text.endswith("They found nothing.")
    assert "PC-1205  clean, awaiting review" in caplog.messages


def test_a_case_with_findings_reports_them_with_their_shortfalls(client):
    model = stub(*work())
    assert work_case("PC-1210", model) == (
        "PC-1210  2 exceptions, $992.80 short, awaiting review"
    )
    case = case_of(client, "PC-1210")
    found = [
        (e["rule"], e["worker_id"], e["shortfall_cents"]) for e in case["exceptions"]
    ]
    assert found == [
        ("arithmetic.gross", "W-023", 10000),
        ("apprentice.unregistered", "W-064", 89280),
    ]
    assert all(e["candidate_id"] for e in case["exceptions"])
    assert all(
        e["raised_by"] == "PayrollCheck Agent, version 1" for e in case["exceptions"]
    )
    assert case["notice"]["draft"] == NOTICE
    told = candidates_in(model.prompts[0])
    assert [c["rule"] for c in told] == ["arithmetic.gross", "apprentice.unregistered"]


def test_the_classification_note_is_dismissed_with_its_reason(client):
    reason = "The line note says W-004 was acting foreman while T. Brennan was out."

    def dismiss(messages):
        [note] = candidates_in(messages)
        return report(
            dismissed=[{"candidate_id": note["candidate_id"], "reason": reason}]
        )

    work_case("PC-1202", stub(dismiss))
    case = case_of(client, "PC-1202")
    assert case["exceptions"] == []
    [candidate] = case["candidates"]
    assert (candidate["rule"], candidate["dismissed_because"]) == (
        "classification.changed",
        reason,
    )


def test_an_exception_no_check_found_with_no_money_is_the_agents_own(client):
    own = {
        "rule": "form.project_mismatch",
        "worker_id": None,
        "line_no": None,
        "expected": "Our project record's contract",
        "actual": "Another contract number in the notes",
        "shortfall_cents": None,
        "citation": "Our project and subcontractor records",
    }
    work_case("PC-1205", stub(report(added=[own], notice=NOTICE)))
    [exception] = case_of(client, "PC-1205")["exceptions"]
    assert (exception["rule"], exception["candidate_id"]) == (
        "form.project_mismatch",
        None,
    )


def test_an_invented_shortfall_is_refused_and_the_refusal_goes_back_to_the_model(
    client,
):
    model = stub(invented_report, report_all())
    assert work_case("PC-1203", model).startswith("PC-1203  1 exception, $72.00")
    refusals = [s for s in steps_of(client, "PC-1203") if s["kind"] == "refusal"]
    [refused] = refusals
    assert refused["content"].startswith(
        "record_exception_report: Refused with status 422"
    )
    assert "must be one a check tool found" in refused["content"]
    assert "must be one a check tool found" in model.prompts[1][-1].content
    [exception] = case_of(client, "PC-1203")["exceptions"]
    assert exception["shortfall_cents"] == 7200


def test_exceptions_with_a_blank_notice_are_refused(client):
    def no_notice(messages):
        return report(raised=[c["candidate_id"] for c in candidates_in(messages)])

    model = stub(no_notice, report_all())
    work_case("PC-1203", model)
    refused = [s for s in steps_of(client, "PC-1203") if s["kind"] == "refusal"]
    assert "needs a draft send-back notice" in refused[0]["content"]
    assert case_of(client, "PC-1203")["notice"]["draft"] == NOTICE


def test_a_lookup_is_recorded_with_its_sources(client):
    question = {
        "craft": "plumber",
        "classification": "journeyman",
        "county": "Middlesex",
        "award_date": "2026-04-15",
        "work_date": "2026-11-16",
    }
    model = stub(call("get_wage_rate", question=question), report_all())
    work_case("PC-1203", model)
    lookups = [s for s in steps_of(client, "PC-1203") if s["kind"] == "lookup"]
    [lookup] = lookups
    assert lookup["content"] == "Rate: plumber journeyman, Middlesex, worked 2026-11-16"
    assert lookup["sources"][0]["file"] == "rate_determinations.yaml"


def test_a_lookup_with_bad_arguments_goes_back_to_the_model(client):
    model = stub(call("check_apprentice", worker_id="W-064", date="soon"), *work())
    assert work_case("PC-1205", model) == "PC-1205  clean, awaiting review"
    assert "lookup" not in {s["kind"] for s in steps_of(client, "PC-1205")}


def test_a_case_is_traced_in_the_session_of_its_thread(client, traces):
    work_case("PC-1205", stub(*work()))
    thread_id = case_of(client, "PC-1205")["thread_id"]
    assert [(t["langfuse_session_id"], t["langfuse_trace_name"]) for t in traces] == [
        (f"PC-1205:{thread_id}", "Work case")
    ]


def test_working_a_case_saves_each_step_on_its_thread(client, monkeypatch):
    agent = agent_on(stub(*work()))
    runs = []
    invoke = agent.graph.invoke

    def spy(start, config, **kwargs):
        runs.append((config, kwargs))
        return invoke(start, config, **kwargs)

    monkeypatch.setattr(agent.graph, "invoke", spy)
    harness.work_case("PC-1205", None, agent)
    [(config, kwargs)] = runs
    assert kwargs["durability"] == "sync"
    thread_id = case_of(client, "PC-1205")["thread_id"]
    assert config["configurable"]["thread_id"] == thread_id


def test_a_provider_error_puts_the_case_back_then_to_a_reviewer(client):
    outage = RuntimeError("503: The model is unavailable")
    saver = InMemorySaver()
    line = work_case("PC-1205", stub(call("get_case"), outage), saver)
    assert line == (
        "PC-1205  failed: RuntimeError: 503: The model is unavailable,"
        " back in the queue"
    )
    case = case_of(client, "PC-1205")
    assert (case["status"], case["attempts"]) == ("received", 1)
    last = steps_of(client, "PC-1205")[-1]
    assert (last["kind"], last["content"]) == (
        "error",
        "RuntimeError: 503: The model is unavailable",
    )
    model = stub(outage)
    again = work_case("PC-1205", model, saver)
    assert again.endswith(", left for a reviewer")
    retried = case_of(client, "PC-1205")
    assert (retried["status"], retried["agent_failed"], retried["attempts"]) == (
        "awaiting_review",
        True,
        2,
    )
    assert retried["thread_id"] != case["thread_id"]


def test_a_tool_that_breaks_stops_the_agent_rather_than_telling_the_model(
    client, monkeypatch
):
    def broken(project_id):
        raise RuntimeError("The backend is unreachable")

    model = stub(call("get_project"), *work())
    agent = agent_on(model)
    monkeypatch.setattr(api, "get_project", broken)
    line = harness.work_case("PC-1205", None, agent)
    assert line == (
        "PC-1205  failed: RuntimeError: The backend is unreachable, back in the queue"
    )


def test_finishing_without_a_report_is_a_failure(client):
    model = stub(call("get_case"), AIMessage(content="It looks fine."))
    assert work_case("PC-1205", model) == (
        "PC-1205  failed: The agent finished without recording an exception report,"
        " back in the queue"
    )


def test_a_payroll_agent_going_round_in_circles_stops(client):
    model = StubModel(messages=(call("get_case") for _ in itertools.count()))
    line = work_case("PC-1205", model)
    assert line == (
        "PC-1205  failed: TooManyModelCalls: The payroll agent made 30 model calls"
        " without finishing, back in the queue"
    )
    assert len(model.prompts) == harness.CASE_MODEL_CALLS


def test_a_failure_after_the_report_keeps_it(client, monkeypatch, caplog):
    record_step = api.record_step

    def lost_after_the_report(case_id, kind, content, sources):
        if content.startswith("record_exception_report:"):
            raise RuntimeError("The connection was lost")
        return record_step(case_id, kind, content, sources)

    monkeypatch.setattr(api, "record_step", lost_after_the_report)
    line = work_case("PC-1203", stub(*work()))
    assert line == "PC-1203  1 exception, $72.00 short, awaiting review"
    assert "PC-1203  RuntimeError: The connection was lost" in caplog.messages
    case = case_of(client, "PC-1203")
    assert (case["status"], case["attempts"]) == ("awaiting_review", 1)
    assert "error" not in {s["kind"] for s in steps_of(client, "PC-1203")}


def test_a_case_that_isnt_received_is_not_started(client):
    work_case("PC-1205", stub(*work()))
    before = steps_of(client, "PC-1205")
    with pytest.raises(Refused, match="^409: Case PC-1205 is not Received$"):
        work_case("PC-1205", stub())
    assert steps_of(client, "PC-1205") == before
    assert case_of(client, "PC-1205")["attempts"] == 1


def test_each_case_starts_clean(client):
    model = stub(*work(), *work())
    agent = agent_on(model)
    harness.work_case("PC-1205", None, agent)
    harness.work_case("PC-1206", None, agent)
    firsts = [prompt for prompt in model.prompts if len(prompt) == 3]
    assert [prompt[1].content for prompt in firsts] == ["Case PC-1205", "Case PC-1206"]
    assert firsts[0][0] == firsts[1][0]
    worked = [case_of(client, i) for i in ("PC-1205", "PC-1206")]
    assert worked[0]["thread_id"] != worked[1]["thread_id"]
