"""Step 7, the two Runtimes: the payroll agent and the Copilot, deployed from the
AgentCore project in agentcore/ with one agentcore deploy, after writing the settings
it gives them into agentcore/.env.local. Then the app's function is pointed at both
and allowed to invoke them, the Policy is put again naming both runtimes' roles, and
each runtime answers a health check in a new session."""

import json
import time
import uuid
from typing import Any

from agent.agentcore_app import HEALTHY, Health
from agent.copilot.memory import MEMORY_ID
from agent.gateway import GATEWAY_URL
from backend import agent_service, copilot_service
from deploy import commands, functions, names, policy, resources, settings
from deploy.aws import POLICY_VERSION, Aws

# The app's address, as the runtimes read it.
APP_URL = "PAYROLLCHECK_API"
HEALTH = Health(operation="health").model_dump()


def write_settings(aws: Aws) -> None:
    """The settings agentcore deploy gives both runtimes: the app's address, the
    Gateway's and the Copilot's Memory's."""
    gateway = resources.find_gateway(aws)
    memory = resources.find_memory(aws)
    if gateway is None or memory is None:
        raise RuntimeError("Run steps 4 and 6 first: the Gateway and the Memory")
    settings.write_local(
        {
            APP_URL: resources.function_url(aws, names.APP_FUNCTION),
            GATEWAY_URL: gateway["gatewayUrl"],
            MEMORY_ID: memory["id"],
        }
    )


def deploy() -> None:
    """agentcore deploy, with the CDK project's packages installed first. Its first
    run in an account makes the CDK bootstrap and the deploy's default target."""
    commands.run(["npm", "ci", "--prefix", "agentcore/cdk"])
    commands.run(["agentcore", "deploy"])


def deployed(aws: Aws) -> dict[str, dict[str, Any]]:
    """Both runtimes, by the app's setting that names each, which deploy has made."""
    found = {}
    for setting, name in (
        (agent_service.RUNTIME, names.AGENT_RUNTIME),
        (copilot_service.RUNTIME, names.COPILOT_RUNTIME),
    ):
        runtime = resources.find_runtime(aws, name)
        if runtime is None:
            raise RuntimeError(f"agentcore deploy made no runtime {name}")
        found[setting] = runtime
    return found


def allow_the_app_to_invoke(aws: Aws, arns: list[str]) -> None:
    """The app's role may invoke both runtimes, and nothing else on Runtime."""
    document = {
        "Version": POLICY_VERSION,
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "bedrock-agentcore:InvokeAgentRuntime",
                "Resource": [
                    resource
                    for arn in arns
                    for resource in (arn, f"{arn}/runtime-endpoint/*")
                ],
            }
        ],
    }
    aws.client("iam").put_role_policy(
        RoleName=names.APP_ROLE,
        PolicyName=f"{names.PROJECT}-app-runtime",
        PolicyDocument=json.dumps(document),
    )


def health_check(aws: Aws, runtime: dict[str, Any]) -> None:
    """Send the health check to a runtime in a new session, as the app sends its
    work, and say how long it took to get ready and answer."""
    started = time.monotonic()
    response = aws.client("bedrock-agentcore").invoke_agent_runtime(
        agentRuntimeArn=runtime["agentRuntimeArn"],
        runtimeSessionId=f"{names.PROJECT}-health-{uuid.uuid4()}",
        payload=json.dumps(HEALTH),
    )
    answer = json.loads(response["response"].read())
    took = time.monotonic() - started
    print(f"Runtime {runtime['agentRuntimeName']}: {answer} in {took:.1f} seconds")
    if answer != HEALTHY:
        raise RuntimeError(f"Runtime {runtime['agentRuntimeName']} isn't healthy")


def run(aws: Aws) -> None:
    """Step 7: both runtimes deployed, the app pointed at them, the Policy naming
    their roles, and each one's health checked."""
    write_settings(aws)
    deploy()
    runtimes = deployed(aws)
    allow_the_app_to_invoke(aws, [r["agentRuntimeArn"] for r in runtimes.values()])
    functions.point_the_app_at(
        aws, {setting: r["agentRuntimeArn"] for setting, r in runtimes.items()}
    )
    policy.run(aws, with_runtimes=True)
    for runtime in runtimes.values():
        health_check(aws, runtime)
