"""The context layer's server: its tools follow the API rules, and its Lambda
handler answers a Function URL's requests, one after another in one process."""

import json
from typing import Any

from api_rules import rule_breaks
from context.server import handler
from context.tests.function_url import Context, mcp_request

TOOLS = {
    "get_wage_rate",
    "check_registration",
    "check_apprentice",
    "get_filing_rules",
    "lookup_payroll_term",
}


def through_the_handler(method: str, params: dict[str, Any]) -> dict[str, Any]:
    """Send one MCP request through the Lambda handler, and return its result."""
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    answer = handler(mcp_request(json.dumps(body)), Context())
    assert answer["statusCode"] == 200
    return json.loads(answer["body"])["result"]


def as_operations(tools: list[dict[str, Any]]) -> dict[str, Any]:
    """The tools as API operations, each taking its inputs as its body, so the API
    rules can check them as they check the app's."""
    body = {"required": True, "content": {"application/json": {"schema": {}}}}
    paths, models = {}, {}
    for tool in tools:
        name = tool["name"]
        schema = {"$ref": f"#/components/schemas/{name}"}
        content = {"application/json": {"schema": schema}}
        operation = {"operationId": name, "description": tool["description"]}
        paths[f"/{name}"] = {
            "post": operation | {"requestBody": body | {"content": content}}
        }
        models[name] = tool["inputSchema"]
    return {"paths": paths, "components": {"schemas": models}}


def test_the_handler_lists_the_tools_then_calls_one():
    tools = through_the_handler("tools/list", {})["tools"]
    assert {tool["name"] for tool in tools} == TOOLS
    found = through_the_handler(
        "tools/call",
        {"name": "lookup_payroll_term", "arguments": {"term": "No Work Week"}},
    )
    assert not found["isError"]
    assert json.loads(found["content"][0]["text"])["term"] == "No Work Week"


def test_every_tool_is_read_only_and_follows_the_api_rules():
    tools = through_the_handler("tools/list", {})["tools"]
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools)
    assert rule_breaks(as_operations(tools)) == []


def test_an_unknown_registration_is_refused_with_its_reason():
    arguments = {"registration_no": "000000", "date": "2026-11-23"}
    refused = through_the_handler(
        "tools/call", {"name": "check_registration", "arguments": arguments}
    )
    assert refused["isError"]
    assert refused["content"][0]["text"].endswith(
        "No registration 000000 in the registry"
    )


def test_a_payroll_tool_answers_through_the_handler_and_refuses_clearly():
    arguments = {
        "craft": "electrician",
        "classification": "journeyman",
        "county": "Middlesex",
        "award_date": "2026-04-15",
        "work_date": "2026-11-23",
    }
    found = through_the_handler(
        "tools/call", {"name": "get_wage_rate", "arguments": arguments}
    )
    rate = json.loads(found["content"][0]["text"])
    assert rate["row"]["effective"] == "2026-10-01"
    assert rate["sources"][0]["file"] == "rate_determinations.yaml"
    refused = through_the_handler(
        "tools/call",
        {"name": "get_wage_rate", "arguments": arguments | {"county": "Atlantis"}},
    )
    assert refused["isError"]
    assert "No county Atlantis" in refused["content"][0]["text"]
