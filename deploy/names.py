"""Every name the runbook gives what it makes, and the tag it puts on each, so the
runbook can find what it made and the teardown can tell it from anything else."""

from collections.abc import Mapping

PROJECT = "payrollcheck"
TAG_KEY = "project"
TAGS = {TAG_KEY: PROJECT}

APP_FUNCTION = "payrollcheck-app"
APP_ROLE = "payrollcheck-app-role"
CONTEXT_FUNCTION = "payrollcheck-context"
CONTEXT_ROLE = "payrollcheck-context-role"
KEY_PROVIDER = "payrollcheck-app-key"
GATEWAY_ROLE = "payrollcheck-gateway-role"
GATEWAY = "payrollcheck-gateway"
POLICY_ENGINE = "payrollcheck_policy_engine"
MEMORY = "payrollcheck_copilot_memory"
# What agentcore deploy names the project's stack and its two runtimes, from the
# project's name in agentcore/agentcore.json and its default target.
STACK = "AgentCore-payrollcheck-default"
AGENT_RUNTIME = "payrollcheck_default_agent"
COPILOT_RUNTIME = "payrollcheck_default_copilot"


def log_group(function: str) -> str:
    """The log group Lambda writes a function's logs to."""
    return f"/aws/lambda/{function}"


def tag_list(tags: Mapping[str, str] = TAGS) -> list[dict[str, str]]:
    """The tags as the services that take a list of keys and values want them."""
    return [{"Key": key, "Value": value} for key, value in tags.items()]


def is_ours(name: str, tags: Mapping[str, str]) -> bool:
    """Whether the runbook made a resource: named and tagged for PayrollCheck."""
    named = name.startswith(PROJECT) or name in {
        STACK,
        log_group(APP_FUNCTION),
        log_group(CONTEXT_FUNCTION),
    }
    return named and tags.get(TAG_KEY) == PROJECT
