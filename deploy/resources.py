"""Finding what the runbook made, by its name: the one place that lists each kind of
AgentCore resource, which the steps use to tell whether one is there already."""

from typing import Any

from deploy import names
from deploy.aws import Aws


def control(aws: Aws) -> Any:
    """The AgentCore control plane's client."""
    return aws.client("bedrock-agentcore-control")


def listed(aws: Aws, operation: str, key: str, **inputs: str) -> list[dict[str, Any]]:
    """Every item a paginated AgentCore listing gives."""
    pages = control(aws).get_paginator(operation).paginate(**inputs)
    return [item for page in pages for item in page[key]]


def find_gateway(aws: Aws) -> dict[str, Any] | None:
    """The Gateway, in full, if it's there."""
    for summary in listed(aws, "list_gateways", "items"):
        if summary["name"] == names.GATEWAY:
            return control(aws).get_gateway(gatewayIdentifier=summary["gatewayId"])
    return None


def find_targets(aws: Aws, gateway_id: str) -> list[dict[str, Any]]:
    """The Gateway's targets."""
    return listed(aws, "list_gateway_targets", "items", gatewayIdentifier=gateway_id)


def find_policy_engine(aws: Aws) -> dict[str, Any] | None:
    """The policy engine, if it's there."""
    engines = listed(aws, "list_policy_engines", "policyEngines")
    return next((e for e in engines if e["name"] == names.POLICY_ENGINE), None)


def find_policies(aws: Aws, engine_id: str) -> list[dict[str, Any]]:
    """The policies in the policy engine."""
    return listed(aws, "list_policies", "policies", policyEngineId=engine_id)


def find_runtime(aws: Aws, name: str) -> dict[str, Any] | None:
    """A runtime, in full, if agentcore deploy has made it."""
    for summary in listed(aws, "list_agent_runtimes", "agentRuntimes"):
        if summary["agentRuntimeName"] == name:
            return control(aws).get_agent_runtime(
                agentRuntimeId=summary["agentRuntimeId"]
            )
    return None


def find_memory(aws: Aws) -> dict[str, Any] | None:
    """The Copilot's Memory, unless it's being deleted."""
    memories = listed(aws, "list_memories", "memories")
    return next(
        (
            m
            for m in memories
            if m["id"].startswith(names.MEMORY) and m["status"] != "DELETING"
        ),
        None,
    )


def key_provider(aws: Aws) -> dict[str, Any]:
    """The Gateway's credential, which step 3 made."""
    return control(aws).get_api_key_credential_provider(name=names.KEY_PROVIDER)


def function_url(aws: Aws, function: str) -> str:
    """A function's URL, which step 2 made, without its closing slash."""
    config = aws.client("lambda").get_function_url_config(FunctionName=function)
    return config["FunctionUrl"].rstrip("/")


def function_arn(aws: Aws, function: str) -> str:
    """A function's ARN."""
    found = aws.client("lambda").get_function(FunctionName=function)
    return found["Configuration"]["FunctionArn"]
