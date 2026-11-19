from agent.checks.findings import RULES
from agent.context_tools import RateQuestion
from agent.direct import CONTEXT_LAYER
from agent.json_text import as_json
from agent.mcp_tools import McpTools
from agent.tools import APP_TOOLS, CONTEXT_TOOLS, PAYROLL_TOOLS, AddedException


def operations(client):
    """Return the operation ids of the backend's API."""
    paths = client.get("/openapi.json").json()["paths"].values()
    return {operation["operationId"] for path in paths for operation in path.values()}


def test_the_app_tools_are_named_after_backend_operations(client):
    names = [t.name for t in APP_TOOLS]
    assert names == [
        "get_case",
        "get_project",
        "list_subcontractors",
        "get_payroll_history",
        "record_exception_report",
    ]
    assert set(names) <= operations(client)


def test_the_payroll_agents_tools_are_the_designs():
    assert [t.name for t in PAYROLL_TOOLS] == [
        "get_case",
        "get_project",
        "list_subcontractors",
        "get_payroll_history",
        "record_exception_report",
        "get_wage_rate",
        "check_registration",
        "check_apprentice",
        "get_filing_rules",
        "lookup_payroll_term",
    ]


def inputs_of(tool):
    """A tool's inputs as the model sees them, the rate question's fields as the
    rate lookup's own."""
    if tool.name == "get_wage_rate":
        return RateQuestion.model_json_schema()["properties"]
    return tool.args


def test_the_context_tools_are_the_context_layers_with_its_inputs(context_at):
    served = McpTools(CONTEXT_LAYER, context_at).tools
    assert {t.name for t in CONTEXT_TOOLS} == set(served)
    for tool in CONTEXT_TOOLS:
        inputs = served[tool.name].args
        ours = inputs_of(tool)
        assert set(ours) == set(inputs), tool.name
        for name, schema in ours.items():
            for rule in ("type", "enum", "minLength", "format"):
                assert schema.get(rule) == inputs[name].get(rule), (tool.name, name)


def test_a_payroll_agent_can_only_act_on_its_own_case_and_subcontractor():
    ids = {"case_id", "project_id", "subcontractor_id"}
    assert all(ids & set(t.args) == set() for t in PAYROLL_TOOLS)


def test_the_agent_writes_json_with_characters_as_themselves():
    found = {"citation": "N.J.S.A. 34:11-56.29 §(b)", "note": "the sub’s note"}
    assert as_json(found) == (
        '{"citation": "N.J.S.A. 34:11-56.29 §(b)", "note": "the sub’s note"}'
    )


def test_the_report_offers_only_the_rules_the_agent_may_add():
    rule = AddedException.model_fields["rule"].description or ""
    offered = rule.removeprefix("One of ").split(", ")
    assert offered == [r for r in RULES if r not in ("timeliness.late", "sequence.gap")]
