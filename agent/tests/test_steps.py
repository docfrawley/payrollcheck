"""Every step of the payroll agent's work on the case's page, in order: the
screening first, then the eight check tools' findings, then the model's calls,
each lookup with where it came from, each named as its route names it."""

from agent import direct, harness
from agent.gateway import Gateway
from agent.tests.stubs import agent_on, call, report_all, stub, work
from backend.tests.dashboard_reads import steps_of

RATE = {
    "craft": "electrician",
    "classification": "journeyman",
    "county": "Middlesex",
    "award_date": "2026-04-15",
    "work_date": "2026-11-16",
}
LOOKUPS = [
    (
        call("get_wage_rate", question=RATE),
        "Rate: electrician journeyman, Middlesex, worked 2026-11-16",
        ["rate_determinations.yaml"],
    ),
    (
        call("check_registration", registration_no="177511", date="2026-11-16"),
        "Registration 177511 on 2026-11-16",
        ["contractor_registry.yaml"],
    ),
    (
        call("check_apprentice", worker_id="W-064", date="2026-11-16"),
        "Apprentice W-064 on 2026-11-16",
        ["apprentice_registrations.yaml"],
    ),
    (call("get_filing_rules"), "The filing rules", ["filing_rules.yaml"]),
    (
        call("lookup_payroll_term", term="No Work Week"),
        'Term "No Work Week"',
        ["payroll_glossary.yaml"],
    ),
]
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


def steps_of_kind(client, case_id, kind):
    return [s for s in steps_of(client, case_id) if s["kind"] == kind]


def test_the_screening_comes_first_then_the_checks_in_order_then_the_model(client):
    harness.work_case("PC-1203", None, agent_on(stub(*work())))
    steps = steps_of(client, "PC-1203")
    assert steps[0]["kind"] == "screening"
    checks = steps[1:9]
    assert [s["kind"] for s in checks] == ["check"] * 8
    assert [s["content"].split(":", 1)[0] for s in checks] == CHECKS
    assert checks[0]["content"] == "check_form: Nothing found"
    assert checks[2]["content"].startswith(
        "check_rates: 1 found\n- rate.base_short W-006"
    )
    assert [s["kind"] for s in steps[9:]] == [
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
    ]


def test_each_context_tool_records_what_it_looked_up_and_where_from(client):
    model = stub(*(reply for reply, _, _ in LOOKUPS), report_all())
    harness.work_case("PC-1205", None, agent_on(model))
    lookups = steps_of_kind(client, "PC-1205", "lookup")
    assert [s["content"] for s in lookups] == [what for _, what, _ in LOOKUPS]
    assert [[f["file"] for f in s["sources"]] for s in lookups] == [
        files for _, _, files in LOOKUPS
    ]


def test_each_call_is_named_as_its_route_names_it(client, gateway):
    replies = [call("lookup_payroll_term", term="No Work Week"), *work()]
    harness.work_case(
        "PC-1205", None, agent_on(stub(*replies), route=Gateway(gateway.url))
    )
    replies = [call("lookup_payroll_term", term="No Work Week"), *work()]
    harness.work_case(
        "PC-1206", None, agent_on(stub(*replies), route=direct.from_environment())
    )
    on_the_gateway = [
        s["content"] for s in steps_of_kind(client, "PC-1205", "tool_call")
    ]
    directly = [s["content"] for s in steps_of_kind(client, "PC-1206", "tool_call")]
    assert on_the_gateway == [
        'payrollcheck-context___lookup_payroll_term(term="No Work Week")',
        "payrollcheck-app___get_case()",
        "payrollcheck-app___record_exception_report(raised=[], dismissed=[], "
        'added=[], notice="")',
    ]
    assert directly == [
        'lookup_payroll_term(term="No Work Week")',
        "get_case()",
        'record_exception_report(raised=[], dismissed=[], added=[], notice="")',
    ]
    results = steps_of_kind(client, "PC-1205", "tool_result")
    assert results[0]["content"].startswith(
        "payrollcheck-context___lookup_payroll_term: {"
    )
    # The check node read the case through the Gateway before the model's calls.
    called = gateway.names
    assert called[:4] == [
        "payrollcheck-app___get_case",
        "payrollcheck-app___get_payroll_history",
        "payrollcheck-app___get_project",
        "payrollcheck-app___list_subcontractors",
    ]
    assert called.count("payrollcheck-app___record_check_findings") == 8
    assert all(c.signed for c in gateway.calls)
