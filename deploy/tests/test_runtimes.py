import io
import json

import pytest
from botocore.response import StreamingBody
from botocore.stub import ANY

from deploy import commands, functions, names, policy, resources, runtimes, settings
from deploy.tests.conftest import ACCOUNT

AGENT_ARN = f"arn:aws:bedrock-agentcore:us-east-1:{ACCOUNT}:runtime/agent-a1"
COPILOT_ARN = f"arn:aws:bedrock-agentcore:us-east-1:{ACCOUNT}:runtime/copilot-b2"
AGENT = {"agentRuntimeArn": AGENT_ARN, "agentRuntimeName": names.AGENT_RUNTIME}
COPILOT = {"agentRuntimeArn": COPILOT_ARN, "agentRuntimeName": names.COPILOT_RUNTIME}


def test_the_runtimes_settings_are_the_apps_the_gateways_and_the_memorys(
    aws, monkeypatch
):
    written: list[dict[str, str]] = []
    monkeypatch.setattr(
        resources, "find_gateway", lambda _: {"gatewayUrl": "https://gw/mcp"}
    )
    monkeypatch.setattr(resources, "find_memory", lambda _: {"id": "memory-1"})
    monkeypatch.setattr(resources, "function_url", lambda _, name: f"https://{name}")
    monkeypatch.setattr(settings, "write_local", written.append)
    runtimes.write_settings(aws)
    assert written == [
        {
            "PAYROLLCHECK_API": "https://payrollcheck-app",
            "PAYROLLCHECK_GATEWAY_URL": "https://gw/mcp",
            "PAYROLLCHECK_COPILOT_MEMORY_ID": "memory-1",
        }
    ]


def test_the_runtimes_need_the_gateway_and_the_memory(aws, monkeypatch):
    monkeypatch.setattr(resources, "find_gateway", lambda _: None)
    monkeypatch.setattr(resources, "find_memory", lambda _: {"id": "memory-1"})
    with pytest.raises(RuntimeError, match="steps 4 and 6"):
        runtimes.write_settings(aws)


def test_the_deploy_installs_the_cdk_projects_packages_first(monkeypatch):
    ran: list[list[str]] = []
    monkeypatch.setattr(commands, "run", ran.append)
    runtimes.deploy()
    assert ran == [["npm", "ci", "--prefix", "agentcore/cdk"], ["agentcore", "deploy"]]


def test_both_runtimes_are_found_by_the_apps_settings(aws, monkeypatch):
    found = {names.AGENT_RUNTIME: AGENT, names.COPILOT_RUNTIME: COPILOT}
    monkeypatch.setattr(resources, "find_runtime", lambda _, name: found.get(name))
    assert runtimes.deployed(aws) == {
        "PAYROLLCHECK_AGENT_RUNTIME": AGENT,
        "PAYROLLCHECK_COPILOT_RUNTIME": COPILOT,
    }
    del found[names.COPILOT_RUNTIME]
    with pytest.raises(RuntimeError, match=names.COPILOT_RUNTIME):
        runtimes.deployed(aws)


def test_the_app_may_invoke_both_runtimes_and_nothing_else(aws, stub):
    stub("iam").add_response(
        "put_role_policy",
        {},
        {
            "RoleName": names.APP_ROLE,
            "PolicyName": "payrollcheck-app-runtime",
            "PolicyDocument": json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "bedrock-agentcore:InvokeAgentRuntime",
                            "Resource": [
                                AGENT_ARN,
                                f"{AGENT_ARN}/runtime-endpoint/*",
                                COPILOT_ARN,
                                f"{COPILOT_ARN}/runtime-endpoint/*",
                            ],
                        }
                    ],
                }
            ),
        },
    )
    runtimes.allow_the_app_to_invoke(aws, [AGENT_ARN, COPILOT_ARN])


def answer(body: dict) -> dict:
    raw = json.dumps(body).encode()
    return {
        "response": StreamingBody(io.BytesIO(raw), len(raw)),
        "contentType": "application/json",
        "statusCode": 200,
        "runtimeSessionId": "payrollcheck-health-0123456789abcdef0123456789",
    }


def test_a_health_check_is_a_new_session_that_answers_healthy(aws, stub, capsys):
    runtime = stub("bedrock-agentcore")
    runtime.add_response(
        "invoke_agent_runtime",
        answer({"healthy": True}),
        {
            "agentRuntimeArn": AGENT_ARN,
            "runtimeSessionId": ANY,
            "payload": json.dumps({"operation": "health"}),
        },
    )
    runtimes.health_check(aws, AGENT)
    assert capsys.readouterr().out.startswith(
        f"Runtime {names.AGENT_RUNTIME}: {{'healthy': True}} in "
    )
    runtime.add_response("invoke_agent_runtime", answer({"refused": "no"}))
    with pytest.raises(RuntimeError, match="isn't healthy"):
        runtimes.health_check(aws, COPILOT)


def test_each_health_check_has_a_session_of_its_own(aws, stub):
    sessions: list[str] = []
    runtime = stub("bedrock-agentcore")
    client = aws.client("bedrock-agentcore")
    client.meta.events.register(
        "before-parameter-build.bedrock-agentcore.InvokeAgentRuntime",
        lambda params, **_: sessions.append(params["runtimeSessionId"]),
    )
    for _ in range(2):
        runtime.add_response("invoke_agent_runtime", answer({"healthy": True}))
        runtimes.health_check(aws, AGENT)
    assert len(set(sessions)) == 2
    assert all(len(session) >= 33 for session in sessions)


def test_the_step_points_the_app_at_both_and_puts_the_policy_naming_them(
    aws, monkeypatch
):
    done: list[object] = []
    monkeypatch.setattr(runtimes, "write_settings", lambda _: done.append("settings"))
    monkeypatch.setattr(runtimes, "deploy", lambda: done.append("deploy"))
    monkeypatch.setattr(
        runtimes,
        "deployed",
        lambda _: {
            "PAYROLLCHECK_AGENT_RUNTIME": AGENT,
            "PAYROLLCHECK_COPILOT_RUNTIME": COPILOT,
        },
    )
    monkeypatch.setattr(
        runtimes, "allow_the_app_to_invoke", lambda _, arns: done.append(arns)
    )
    monkeypatch.setattr(
        functions, "point_the_app_at", lambda _, settings: done.append(settings)
    )
    monkeypatch.setattr(
        policy,
        "run",
        lambda _, *, with_runtimes: done.append(("policy", with_runtimes)),
    )
    monkeypatch.setattr(
        runtimes,
        "health_check",
        lambda _, runtime: done.append(runtime["agentRuntimeName"]),
    )
    runtimes.run(aws)
    assert done == [
        "settings",
        "deploy",
        [AGENT_ARN, COPILOT_ARN],
        {
            "PAYROLLCHECK_AGENT_RUNTIME": AGENT_ARN,
            "PAYROLLCHECK_COPILOT_RUNTIME": COPILOT_ARN,
        },
        ("policy", True),
        names.AGENT_RUNTIME,
        names.COPILOT_RUNTIME,
    ]
