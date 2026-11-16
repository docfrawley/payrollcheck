"""The payroll agent's two routes to its tools: through the Gateway, signed, or
directly to the app and the context layer."""

import asyncio
import json
from typing import cast

import pytest
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from agent import api, checkpoints, direct, harness
from agent.check_inputs import fetch_inputs
from agent.direct import CONTEXT_URL
from agent.gateway import GATEWAY_URL, Gateway
from agent.json_text import as_json
from agent.mcp_tools import McpTools
from agent.routes import Target
from agent.tests.gateway_stand_in import DENIED
from agent.tests.records import case_of
from agent.tests.stubs import agent_on, call, flags, invented_report, stub, work
from backend.agent_api import OPERATIONS
from backend.tests.case_requests import start
from backend.tests.dashboard_reads import steps_of

APP = "payrollcheck-app___"
CONTEXT = "payrollcheck-context___"


def on_the_gateway(gateway, model, **kwargs):
    return agent_on(model, route=Gateway(gateway.url), **kwargs)


@pytest.fixture(params=["direct", "gateway"])
def route_name(request):
    return request.param


@pytest.fixture
def route(request, route_name):
    """Each route in turn: directly to the app, or through the stand-in Gateway."""
    if route_name == "direct":
        return direct.from_environment()
    return Gateway(request.getfixturevalue("gateway").url)


def test_the_models_tools_are_the_same_on_both_routes(gateway):
    on_each = []
    for route in (direct.from_environment(), Gateway(gateway.url)):
        model = stub()
        agent_on(model, route=route)
        [tools] = model.bound_tools
        on_each.append([(tool.name, tool.args) for tool in tools])
    assert on_each[0] == on_each[1]
    for _, args in on_each[0]:
        assert {"case_id", "project_id", "subcontractor_id"} & set(args) == set()


def test_the_gateway_route_reads_checks_and_reports_through_the_gateway(
    client, gateway
):
    model = stub(call("get_project"), *work())
    line = harness.work_case("PC-1203", None, on_the_gateway(gateway, model))
    assert line == "PC-1203  1 exception, $72.00 short, awaiting review"
    app_calls = [name for name in gateway.names if name.startswith(APP)]
    assert app_calls[:4] == [
        f"{APP}get_case",
        f"{APP}get_payroll_history",
        f"{APP}get_project",
        f"{APP}list_subcontractors",
    ]
    assert app_calls[4:12] == [f"{APP}record_check_findings"] * 8
    assert app_calls[12:] == [
        f"{APP}get_project",
        f"{APP}get_case",
        f"{APP}record_exception_report",
    ]
    reported = gateway.calls[-1].inputs
    assert (reported["case_id"], reported["raised_by"]) == (
        "PC-1203",
        "PayrollCheck Agent, version 1",
    )
    assert any(name.startswith(f"{CONTEXT}get_wage_rate") for name in gateway.names)
    assert all(c.signed for c in gateway.calls)
    assert case_of(client, "PC-1203")["status"] == "awaiting_review"


def test_the_screenings_flag_goes_through_the_gateway(client, gateway):
    line = harness.work_case(
        "PC-1205", None, on_the_gateway(gateway, stub(), screener=flags())
    )
    assert line == "PC-1205  flagged by the screening"
    assert gateway.names == [f"{APP}record_screening_flag"]


def test_the_check_inputs_are_the_same_on_both_routes(client, gateway):
    start(client, "PC-1210")
    on_each = [
        fetch_inputs(route, "PC-1210")
        for route in (direct.from_environment(), Gateway(gateway.url))
    ]
    assert on_each[0] == on_each[1]


def test_get_case_gives_the_same_text_on_both_routes(client, gateway):
    case = {"case_id": "PC-1203"}
    on_each = [
        as_json(route.call(Target.APP, "get_case", case))
        for route in (direct.from_environment(), Gateway(gateway.url))
    ]
    assert on_each[0] == on_each[1] == as_json(api.get_case("PC-1203"))


def test_a_report_the_app_refuses_is_a_refusal_on_each_route(client, route):
    model = stub(invented_report, *work()[1:])
    agent = agent_on(model, route=route)
    line = harness.work_case("PC-1203", None, agent)
    assert line == "PC-1203  1 exception, $72.00 short, awaiting review"
    refusal = model.prompts[1][-1]
    assert isinstance(refusal, ToolMessage)
    assert refusal.status == "error"
    assert "must be one a check tool found" in refusal.text
    name = route.name(Target.APP, "record_exception_report")
    refusals = [s for s in steps_of(client, "PC-1203") if s["kind"] == "refusal"]
    assert [s["content"] for s in refusals] == [f"{name}: {refusal.text}"]


def test_a_checks_read_the_gateway_refuses_fails_the_attempt(client, gateway):
    gateway.refused.add(f"{APP}get_payroll_history")
    model = stub(*work())
    line = harness.work_case("PC-1205", None, on_the_gateway(gateway, model))
    assert line == (f"PC-1205  failed: GatewayRefused: {DENIED}, back in the queue")
    assert model.prompts == []


def test_a_lookup_the_gateway_refuses_reaches_the_model_as_a_refusal(client, gateway):
    gateway.refused.add(f"{CONTEXT}lookup_payroll_term")
    model = stub(call("lookup_payroll_term", term="Fringe"), *work())
    line = harness.work_case("PC-1205", None, on_the_gateway(gateway, model))
    assert line == "PC-1205  clean, awaiting review"
    refusal = model.prompts[1][-1]
    assert refusal.text == f"Refused by the Gateway: {DENIED}"
    [step] = [s for s in steps_of(client, "PC-1205") if s["kind"] == "refusal"]
    assert step["content"] == (
        f"{CONTEXT}lookup_payroll_term: Refused by the Gateway: {DENIED}"
    )


def test_the_route_is_read_when_the_payroll_agents_are_built(gateway, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(harness, "PostgresSaver", lambda pool: InMemorySaver())
    version = api.get_current_version()
    monkeypatch.setenv(GATEWAY_URL, gateway.url)
    no_pool = cast(checkpoints.Pool, None)
    assert isinstance(harness.payroll_graphs(version, no_pool)().route, Gateway)
    monkeypatch.delenv(GATEWAY_URL)
    assert isinstance(harness.payroll_graphs(version, no_pool)().route, direct.Direct)


def test_an_mcp_call_leaves_the_main_threads_event_loop(gateway):
    loop = asyncio.get_event_loop()
    stand_in = McpTools("The stand-in Gateway", gateway.url)
    stand_in.call(f"{APP}get_case", {"case_id": "PC-1201"})
    assert asyncio.get_event_loop() is loop
    assert not loop.is_closed()


def test_the_stand_ins_app_tools_are_the_agents_api_documents_operations(
    client, gateway
):
    document = client.get("/api/agent/openapi.json").json()
    tools = {op.tool.name: op.tool for op in gateway.operations.values()}
    assert set(tools) == {f"{APP}{operation}" for operation in OPERATIONS}
    for path, methods in document["paths"].items():
        for operation in methods.values():
            tool = tools[f"{APP}{operation['operationId']}"]
            named = {p["name"] for p in operation.get("parameters", [])}
            assert named <= set(tool.inputSchema["properties"]), path
    report = tools[f"{APP}record_exception_report"].inputSchema
    assert set(report["required"]) == {
        "case_id",
        "raised",
        "dismissed",
        "added",
        "notice",
        "raised_by",
    }


RATE = {
    "craft": "electrician",
    "classification": "journeyman",
    "county": "Middlesex",
    "award_date": "2026-04-15",
    "work_date": "2026-11-16",
}
CONTEXT_CALLS = [
    call("get_wage_rate", question=RATE),
    call("check_registration", registration_no="177511", date="2026-11-16"),
    call("check_apprentice", worker_id="W-064", date="2026-11-16"),
    call("get_filing_rules"),
    call("lookup_payroll_term", term="No Work Week"),
    call("check_registration", registration_no="000000", date="2026-11-16"),
]


def test_the_context_layers_tools_answer_on_each_route(
    client, request, route_name, route
):
    model = stub(*CONTEXT_CALLS, *work())
    line = harness.work_case("PC-1205", None, agent_on(model, route=route))
    assert line == "PC-1205  clean, awaiting review"
    *answers, refused = [
        m for m in model.prompts[len(CONTEXT_CALLS)] if isinstance(m, ToolMessage)
    ]
    files = [json.loads(a.text)["sources"][0]["file"] for a in answers]
    assert files == [
        "rate_determinations.yaml",
        "contractor_registry.yaml",
        "apprentice_registrations.yaml",
        "filing_rules.yaml",
        "payroll_glossary.yaml",
    ]
    assert refused.status == "error"
    assert refused.text.startswith("Refused: ")
    assert refused.text.endswith("No registration 000000 in the registry")
    if route_name == "gateway":
        gateway = request.getfixturevalue("gateway")
        context_calls = [n for n in gateway.names if n.startswith(CONTEXT)][
            -len(CONTEXT_CALLS) :
        ]
        assert context_calls == [
            f"{CONTEXT}{c.tool_calls[0]['name']}" for c in CONTEXT_CALLS
        ]


# A port nothing on the laptop listens on.
NOBODY = "http://127.0.0.1:9/mcp"


def test_a_context_layer_that_isnt_answering_says_so_in_a_line(monkeypatch):
    monkeypatch.setenv(CONTEXT_URL, NOBODY)
    with pytest.raises(ConnectionError) as down:
        direct.from_environment()
    assert str(down.value) == f"The context layer isn't answering at {NOBODY}"
