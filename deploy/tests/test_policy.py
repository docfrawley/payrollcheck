import asyncio
import json
import re

import pytest
from botocore.stub import ANY

from backend.agent_api import OPERATIONS
from context.server import build_server
from deploy import names, policy
from deploy.tests.conftest import ACCOUNT, OPERATOR

GATEWAY_ARN = (
    f"arn:aws:bedrock-agentcore:us-east-1:{ACCOUNT}:gateway/payrollcheck-gateway-a1b2"
)
AGENT = f"arn:aws:sts::{ACCOUNT}:assumed-role/AgentCore-payrollcheck-agent-role"
COPILOT = f"arn:aws:sts::{ACCOUNT}:assumed-role/AgentCore-payrollcheck-copilot-role"
EVERYONE = policy.Callers(operator=OPERATOR, agent=AGENT, copilot=COPILOT)
ENGINE_ID = "payrollcheck_policy_engine-x1"
ENGINE_ARN = f"arn:aws:bedrock-agentcore:us-east-1:{ACCOUNT}:policy-engine/{ENGINE_ID}"


def callers_in(statement: str) -> list[str]:
    """The callers a permit's condition names."""
    found = re.search(r"when \{\s*(\[.*\])\.contains\(principal\.id\)", statement)
    assert found
    return json.loads(found.group(1))


def test_every_tool_the_agent_needs_has_one_permit():
    permits = policy.allowlist(GATEWAY_ARN, EVERYONE)
    assert len(permits) == 12
    assert set(permits) == {
        *(f"payrollcheck_allow_app_{tool}" for tool in policy.APP_TOOLS),
        *(f"payrollcheck_allow_context_{tool}" for tool in policy.CONTEXT_TOOLS),
    }
    assert (
        'action == AgentCore::Action::"payrollcheck-app___get_case"'
        in (permits["payrollcheck_allow_app_get_case"])
    )
    assert (
        'action == AgentCore::Action::"payrollcheck-context___get_wage_rate"'
        in (permits["payrollcheck_allow_context_get_wage_rate"])
    )
    for statement in permits.values():
        assert statement.startswith("permit(")
        assert f'resource == AgentCore::Gateway::"{GATEWAY_ARN}"' in statement
        assert "principal is AgentCore::IamEntity" in statement


def test_nothing_is_forbidden_and_there_is_no_payment_cap():
    statements = " ".join(policy.allowlist(GATEWAY_ARN, EVERYONE).values()).lower()
    for word in ("forbid", "pay_claim", "payment", "amount", "decimal"):
        assert word not in statements


def test_only_the_agent_may_call_the_apps_tools():
    permits = policy.allowlist(GATEWAY_ARN, EVERYONE)
    for tool in policy.APP_TOOLS:
        assert callers_in(permits[f"payrollcheck_allow_app_{tool}"]) == [AGENT]
    for tool in policy.CONTEXT_TOOLS:
        assert callers_in(permits[f"payrollcheck_allow_context_{tool}"]) == [
            AGENT,
            COPILOT,
            OPERATOR,
        ]


def test_before_the_runtimes_only_the_operator_may_call_the_context_tools():
    permits = policy.allowlist(GATEWAY_ARN, policy.Callers(operator=OPERATOR))
    assert set(permits) == {
        f"payrollcheck_allow_context_{tool}" for tool in policy.CONTEXT_TOOLS
    }
    assert all(callers_in(p) == [OPERATOR] for p in permits.values())


def test_the_allowlist_is_every_tool_the_code_names():
    assert set(policy.APP_TOOLS) == OPERATIONS
    # A loop of its own, since asyncio.run would take the main thread's away from
    # the tests that run after it.
    loop = asyncio.new_event_loop()
    try:
        served = loop.run_until_complete(build_server().list_tools())
    finally:
        loop.close()
    assert set(policy.CONTEXT_TOOLS) == {tool.name for tool in served}


@pytest.mark.parametrize(
    ("arn", "caller"),
    [
        (
            f"arn:aws:iam::{ACCOUNT}:role/service-role/AgentRole",
            f"arn:aws:sts::{ACCOUNT}:assumed-role/AgentRole",
        ),
        (
            f"arn:aws:sts::{ACCOUNT}:assumed-role/AdminRole/someone@example.com",
            f"arn:aws:sts::{ACCOUNT}:assumed-role/AdminRole",
        ),
        (OPERATOR, OPERATOR),
    ],
)
def test_the_principal_the_policy_sees(arn, caller):
    assert policy.caller_of(arn) == caller


def engine_listing(*engines):
    return {
        "policyEngines": [
            {
                "policyEngineId": ENGINE_ID,
                "name": name,
                "createdAt": "2026-11-18T00:00:00Z",
                "updatedAt": "2026-11-18T00:00:00Z",
                "policyEngineArn": ENGINE_ARN,
                "status": "ACTIVE",
                "statusReasons": [],
            }
            for name in engines
        ]
    }


ENGINE = {
    "policyEngineId": ENGINE_ID,
    "name": names.POLICY_ENGINE,
    "createdAt": "2026-11-18T00:00:00Z",
    "updatedAt": "2026-11-18T00:00:00Z",
    "policyEngineArn": ENGINE_ARN,
    "status": "ACTIVE",
    "statusReasons": [],
}


def test_the_engine_is_made_tagged_the_first_time(aws, stub, capsys):
    control = stub("bedrock-agentcore-control")
    control.add_response("list_policy_engines", engine_listing())
    control.add_response(
        "create_policy_engine",
        {
            "policyEngineId": ENGINE_ID,
            "name": names.POLICY_ENGINE,
            "createdAt": "2026-11-18T00:00:00Z",
            "updatedAt": "2026-11-18T00:00:00Z",
            "policyEngineArn": ENGINE_ARN,
            "status": "CREATING",
            "statusReasons": [],
        },
        {"name": names.POLICY_ENGINE, "description": ANY, "tags": names.TAGS},
    )
    control.add_response("get_policy_engine", ENGINE, {"policyEngineId": ENGINE_ID})
    control.add_response("get_policy_engine", ENGINE, {"policyEngineId": ENGINE_ID})
    control.add_response("list_policy_engines", engine_listing(names.POLICY_ENGINE))
    control.add_response("get_policy_engine", ENGINE)
    control.add_response("get_policy_engine", ENGINE)
    assert policy.make_engine(aws)["policyEngineArn"] == ENGINE_ARN
    assert policy.make_engine(aws)["policyEngineArn"] == ENGINE_ARN
    assert capsys.readouterr().out.splitlines() == [
        f"Policy engine {names.POLICY_ENGINE}: created",
        f"Policy engine {names.POLICY_ENGINE}: unchanged",
    ]


def test_the_gateways_role_may_ask_the_engine(aws, stub):
    stub("iam").add_response(
        "put_role_policy",
        {},
        {
            "RoleName": names.GATEWAY_ROLE,
            "PolicyName": f"{names.GATEWAY_ROLE}-policy-engine",
            "PolicyDocument": json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "bedrock-agentcore:GetPolicyEngine",
                            "Resource": ENGINE_ARN,
                        },
                        {
                            "Effect": "Allow",
                            "Action": [
                                "bedrock-agentcore:AuthorizeAction",
                                "bedrock-agentcore:PartiallyAuthorizeActions",
                            ],
                            "Resource": [ENGINE_ARN, GATEWAY_ARN],
                        },
                    ],
                }
            ),
        },
    )
    policy.allow_the_gateway_to_ask(aws, ENGINE_ARN, GATEWAY_ARN)


GATEWAY = {
    "gatewayArn": GATEWAY_ARN,
    "gatewayId": "payrollcheck-gateway-a1b2",
    "gatewayUrl": "https://gw.example/mcp",
    "createdAt": "2026-11-18T00:00:00Z",
    "updatedAt": "2026-11-18T00:00:00Z",
    "status": "READY",
    "name": names.GATEWAY,
    "roleArn": f"arn:aws:iam::{ACCOUNT}:role/{names.GATEWAY_ROLE}",
    "protocolType": "MCP",
    "authorizerType": "AWS_IAM",
}


def test_the_engine_is_enforced_once_its_permission_arrives(
    aws, stub, no_pauses, capsys
):
    control = stub("bedrock-agentcore-control")
    control.add_client_error(
        "update_gateway",
        "ValidationException",
        "The role isn't allowed bedrock-agentcore:GetPolicyEngine",
    )
    enforced = {"arn": ENGINE_ARN, "mode": "ENFORCE"}
    control.add_response(
        "update_gateway",
        GATEWAY | {"policyEngineConfiguration": enforced},
        {
            "gatewayIdentifier": GATEWAY["gatewayId"],
            "name": names.GATEWAY,
            "description": ANY,
            "roleArn": GATEWAY["roleArn"],
            "protocolType": "MCP",
            "authorizerType": "AWS_IAM",
            "exceptionLevel": "DEBUG",
            "policyEngineConfiguration": enforced,
        },
    )
    control.add_response(
        "get_gateway", GATEWAY | {"policyEngineConfiguration": enforced}
    )
    policy.attach(aws, GATEWAY, ENGINE_ARN)
    assert no_pauses == [5]
    policy.attach(aws, GATEWAY | {"policyEngineConfiguration": enforced}, ENGINE_ARN)
    assert capsys.readouterr().out.splitlines()[-1].endswith("Policy: unchanged")


def policy_listing(*policy_names):
    return {
        "policies": [
            {
                "policyId": f"policy-id-{name}",
                "name": name,
                "policyEngineId": ENGINE_ID,
                "definition": {"cedar": {"statement": permit_text("listed")}},
                "createdAt": "2026-11-18T00:00:00Z",
                "updatedAt": "2026-11-18T00:00:00Z",
                "policyArn": f"{ENGINE_ARN}/policy/{name}",
                "status": "ACTIVE",
                "statusReasons": [],
            }
            for name in policy_names
        ]
    }


def permit_text(word):
    """A stand-in permit's statement, as long as a real one must be."""
    return f"permit(principal, action, resource) when {{ {word} }};"


def a_policy(name, statement, status="ACTIVE", reasons=()):
    return {
        "policyId": f"policy-id-{name}",
        "name": name,
        "policyEngineId": ENGINE_ID,
        "definition": {"cedar": {"statement": statement}},
        "createdAt": "2026-11-18T00:00:00Z",
        "updatedAt": "2026-11-18T00:00:00Z",
        "policyArn": f"{ENGINE_ARN}/policy/{name}",
        "status": status,
        "statusReasons": list(reasons),
    }


def test_each_permit_is_made_updated_or_left_as_it_is(aws, stub, capsys):
    control = stub("bedrock-agentcore-control")
    one, two, three = permit_text("one"), permit_text("two"), permit_text("three")
    wanted = {"same": one, "different": two, "missing": three}
    control.add_response("list_policies", policy_listing("same", "different"))
    control.add_response("get_policy", a_policy("same", one))
    control.add_response("get_policy", a_policy("different", permit_text("old")))
    control.add_response(
        "update_policy",
        a_policy("different", two),
        {
            "policyEngineId": ENGINE_ID,
            "policyId": "policy-id-different",
            "definition": {"cedar": {"statement": two}},
        },
    )
    control.add_response("get_policy", a_policy("different", two, "UPDATING"))
    control.add_response("get_policy", a_policy("different", two))
    control.add_response(
        "create_policy",
        a_policy("missing", three),
        {
            "policyEngineId": ENGINE_ID,
            "name": "missing",
            "definition": {"cedar": {"statement": three}},
        },
    )
    control.add_response("get_policy", a_policy("missing", three))
    policy.put_policies(aws, ENGINE_ID, wanted)
    assert capsys.readouterr().out.splitlines() == [
        "Policy same: unchanged",
        "Policy different: ACTIVE",
        "Policy different: updated",
        "Policy missing: ACTIVE",
        "Policy missing: created",
    ]


def test_a_permit_the_engine_refused_says_why_and_stops_the_step(aws, stub, capsys):
    control = stub("bedrock-agentcore-control")
    control.add_response("list_policies", policy_listing())
    control.add_response("create_policy", a_policy("refused", permit_text("x")))
    control.add_response(
        "get_policy",
        a_policy(
            "refused",
            permit_text("x"),
            "CREATE_FAILED",
            ["principal.id isn't an attribute of AgentCore::IamEntity"],
        ),
    )
    with pytest.raises(RuntimeError, match="refused the permit refused"):
        policy.put_policies(aws, ENGINE_ID, {"refused": permit_text("x")})
    assert capsys.readouterr().out.splitlines() == [
        "Policy refused: CREATE_FAILED",
        "  principal.id isn't an attribute of AgentCore::IamEntity",
    ]


def test_a_refused_permit_with_the_same_statement_is_tried_again(aws, stub, capsys):
    control = stub("bedrock-agentcore-control")
    control.add_response("list_policies", policy_listing("redo"))
    control.add_response(
        "get_policy", a_policy("redo", permit_text("x"), "CREATE_FAILED")
    )
    control.add_response("update_policy", a_policy("redo", permit_text("x")))
    control.add_response("get_policy", a_policy("redo", permit_text("x")))
    policy.put_policies(aws, ENGINE_ID, {"redo": permit_text("x")})
    assert capsys.readouterr().out.splitlines()[-1] == "Policy redo: updated"


def test_a_permit_the_allowlist_no_longer_has_is_deleted(aws, stub, capsys):
    control = stub("bedrock-agentcore-control")
    control.add_response("list_policies", policy_listing("payrollcheck_allow_old"))
    control.add_response(
        "delete_policy",
        a_policy("payrollcheck_allow_old", permit_text("x"), "DELETING"),
        {"policyEngineId": ENGINE_ID, "policyId": "policy-id-payrollcheck_allow_old"},
    )
    policy.put_policies(aws, ENGINE_ID, {})
    assert capsys.readouterr().out == (
        "Policy payrollcheck_allow_old: deleted, as it's not on the allowlist\n"
    )


def test_the_real_allowlist_is_one_the_engine_takes(aws, stub):
    control = stub("bedrock-agentcore-control")
    wanted = policy.allowlist(GATEWAY_ARN, EVERYONE)
    control.add_response("list_policies", policy_listing())
    for name, statement in wanted.items():
        control.add_response(
            "create_policy",
            a_policy(name, statement),
            {
                "policyEngineId": ENGINE_ID,
                "name": name,
                "definition": {"cedar": {"statement": statement}},
            },
        )
        control.add_response("get_policy", a_policy(name, statement))
    policy.put_policies(aws, ENGINE_ID, wanted)


def runtime_listing(*runtime_names):
    return {
        "agentRuntimes": [
            {
                "agentRuntimeArn": f"arn:runtime/{name}",
                "agentRuntimeId": f"{name}-id",
                "agentRuntimeVersion": "1",
                "agentRuntimeName": name,
                "description": "A runtime",
                "lastUpdatedAt": "2026-11-18T00:00:00Z",
                "status": "READY",
            }
            for name in runtime_names
        ]
    }


def a_runtime(name, role):
    return {
        "agentRuntimeArn": f"arn:runtime/{name}",
        "agentRuntimeName": name,
        "agentRuntimeId": f"{name}-id",
        "agentRuntimeVersion": "1",
        "createdAt": "2026-11-18T00:00:00Z",
        "lastUpdatedAt": "2026-11-18T00:00:00Z",
        "roleArn": f"arn:aws:iam::{ACCOUNT}:role/{role}",
        "networkConfiguration": {"networkMode": "PUBLIC"},
        "status": "READY",
        "lifecycleConfiguration": {},
    }


def with_runtimes(control, agent_role, copilot_role):
    """The two runtimes there, each with its role."""
    both = runtime_listing(names.AGENT_RUNTIME, names.COPILOT_RUNTIME)
    control.add_response("list_agent_runtimes", both)
    control.add_response(
        "get_agent_runtime",
        a_runtime(names.AGENT_RUNTIME, agent_role),
        {"agentRuntimeId": f"{names.AGENT_RUNTIME}-id"},
    )
    control.add_response("list_agent_runtimes", both)
    control.add_response(
        "get_agent_runtime",
        a_runtime(names.COPILOT_RUNTIME, copilot_role),
        {"agentRuntimeId": f"{names.COPILOT_RUNTIME}-id"},
    )


def test_before_the_runtimes_the_operator_alone_may_call(aws, stub):
    control = stub("bedrock-agentcore-control")
    control.add_response("list_agent_runtimes", runtime_listing())
    control.add_response("list_agent_runtimes", runtime_listing())
    assert policy.callers(aws, with_runtimes=False) == policy.Callers(operator=OPERATOR)


def test_once_theyre_there_each_runtimes_role_may_call(aws, stub):
    with_runtimes(
        stub("bedrock-agentcore-control"),
        "AgentCore-payrollcheck-agent-role",
        "AgentCore-payrollcheck-copilot-role",
    )
    assert policy.callers(aws, with_runtimes=True) == EVERYONE


def test_the_runtimes_step_needs_both_runtimes(aws, stub):
    stub("bedrock-agentcore-control").add_response(
        "list_agent_runtimes", runtime_listing()
    )
    with pytest.raises(RuntimeError, match="agentcore deploy"):
        policy.callers(aws, with_runtimes=True)


def test_runtimes_sharing_a_role_cant_be_told_apart(aws, stub):
    with_runtimes(stub("bedrock-agentcore-control"), "OneRole", "OneRole")
    with pytest.raises(RuntimeError, match="share a role"):
        policy.callers(aws, with_runtimes=True)


def test_the_step_needs_the_gateway(aws, monkeypatch):
    monkeypatch.setattr(policy.resources, "find_gateway", lambda _: None)
    with pytest.raises(RuntimeError, match="step 4"):
        policy.run(aws)


def test_the_step_enforces_the_allowlist_for_the_callers_there_now(aws, monkeypatch):
    done: list[object] = []
    monkeypatch.setattr(policy.resources, "find_gateway", lambda _: GATEWAY)
    monkeypatch.setattr(policy, "make_engine", lambda _: ENGINE)
    monkeypatch.setattr(
        policy, "allow_the_gateway_to_ask", lambda _, e, g: done.append(("ask", e, g))
    )
    monkeypatch.setattr(policy, "attach", lambda _, g, e: done.append(("attach", e)))

    def callers(_, *, with_runtimes):
        done.append(("runtimes needed", with_runtimes))
        return policy.Callers(operator=OPERATOR)

    monkeypatch.setattr(policy, "callers", callers)
    monkeypatch.setattr(
        policy, "put_policies", lambda _, e, wanted: done.append((e, sorted(wanted)))
    )
    policy.run(aws)
    assert done == [
        ("ask", ENGINE_ARN, GATEWAY_ARN),
        ("attach", ENGINE_ARN),
        ("runtimes needed", False),
        (
            ENGINE_ID,
            sorted(f"payrollcheck_allow_context_{t}" for t in policy.CONTEXT_TOOLS),
        ),
    ]
