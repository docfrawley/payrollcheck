"""The payroll agent's own API document, which the Gateway turns into tools."""

from api_rules import rule_breaks
from backend.agent_api import OPERATIONS
from backend.tests.dashboard_reads import read

PATH = "/api/agent/openapi.json"


def operations_in(document):
    return {
        operation["operationId"]: operation
        for methods in document["paths"].values()
        for operation in methods.values()
    }


def test_the_document_holds_the_payroll_agents_seven_operations(client):
    document = client.get(PATH).json()
    operations = operations_in(document)
    assert (
        set(operations)
        == OPERATIONS
        == {
            "get_case",
            "get_project",
            "list_subcontractors",
            "get_payroll_history",
            "record_check_findings",
            "record_screening_flag",
            "record_exception_report",
        }
    )
    app_operations = operations_in(client.get("/openapi.json").json())
    for name, operation in operations.items():
        assert operation["description"] == app_operations[name]["description"]
    assert rule_breaks(document) == []


def test_the_document_has_no_servers_and_nothing_about_the_key(client):
    document = client.get(PATH).json()
    assert "servers" not in document
    assert "securitySchemes" not in document["components"]
    for operation in operations_in(document).values():
        assert "security" not in operation
        assert not [p for p in operation.get("parameters", []) if p["in"] == "header"]


def test_the_document_needs_the_key_or_a_sign_in(dashboard):
    assert read(dashboard, PATH).status_code == 200
    assert dashboard.get(PATH).status_code == 401


def test_the_app_no_longer_serves_the_travel_operations(client):
    operations = operations_in(client.get("/openapi.json").json())
    travel = {"get_policy", "get_case_history", "pay_case", "hold_payment"}
    assert travel & set(operations) == set()


def test_the_report_body_requires_who_raises_it(client):
    document = client.get(PATH).json()
    operation = operations_in(document)["record_exception_report"]
    body = operation["requestBody"]["content"]["application/json"]["schema"]
    model = document["components"]["schemas"][body["$ref"].split("/")[-1]]
    assert set(model["required"]) == {
        "raised",
        "dismissed",
        "added",
        "notice",
        "raised_by",
    }
