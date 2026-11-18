"""Step 5, the Policy: the policy engine, enforced on the Gateway, as an explicit
allowlist. Each tool the payroll agent's work needs has one permit, naming who may
call it, and everything else is denied by default. Ed's payment cap isn't ported.

The agent's runtime role may call every tool on both targets. The Copilot's runtime
role and the operator who runs the runbook may call the context layer's tools only,
so a call they make to one of the app's is refused by the Policy itself."""

import json
from dataclasses import dataclass
from functools import partial
from typing import Any

from agent import app_operations, context_tools
from agent.gateway import SEPARATOR
from agent.routes import Target
from deploy import gateway, names, resources, waits
from deploy.aws import POLICY_VERSION, Aws

APP_TOOLS = (
    app_operations.GET_CASE,
    app_operations.GET_PROJECT,
    app_operations.LIST_SUBCONTRACTORS,
    app_operations.GET_PAYROLL_HISTORY,
    app_operations.RECORD_CHECK_FINDINGS,
    app_operations.RECORD_SCREENING_FLAG,
    app_operations.RECORD_EXCEPTION_REPORT,
)
CONTEXT_TOOLS = (
    context_tools.GET_WAGE_RATE,
    context_tools.CHECK_REGISTRATION,
    context_tools.CHECK_APPRENTICE,
    context_tools.GET_FILING_RULES,
    context_tools.LOOKUP_PAYROLL_TERM,
)
ENFORCE = "ENFORCE"
ACTIVE = "ACTIVE"


@dataclass(frozen=True)
class Callers:
    """Who may call the Gateway's tools, each as the Policy sees them: the agent's
    and the Copilot's runtime roles, once agentcore deploy has made them, and the
    operator."""

    operator: str
    agent: str | None = None
    copilot: str | None = None

    def of(self, target: Target) -> list[str]:
        """Who may call a target's tools."""
        if target == Target.APP:
            everyone = [self.agent]
        else:
            everyone = [self.agent, self.copilot, self.operator]
        return [caller for caller in everyone if caller]


def caller_of(arn: str) -> str:
    """The principal the Policy sees for an IAM ARN: a role, or a session of one,
    as the role assumed, without a session; any other identity as it is."""
    prefix, _, resource = arn.partition(":role/")
    if resource:
        account = prefix.split(":")[4]
        return f"arn:aws:sts::{account}:assumed-role/{resource.rsplit('/', 1)[-1]}"
    prefix, _, session = arn.partition(":assumed-role/")
    if session:
        return f"{prefix}:assumed-role/{session.split('/')[0]}"
    return arn


def policy_name(target: Target, tool: str) -> str:
    """The name of a tool's permit, such as payrollcheck_allow_app_get_case."""
    short = target.removeprefix(f"{names.PROJECT}-")
    return f"{names.PROJECT}_allow_{short}_{tool}"


def permit(target: Target, tool: str, gateway_arn: str, callers: list[str]) -> str:
    """The Cedar permit for one tool, as the Gateway names it, for its callers."""
    return f"""permit(
  principal is AgentCore::IamEntity,
  action == AgentCore::Action::"{target}{SEPARATOR}{tool}",
  resource == AgentCore::Gateway::"{gateway_arn}"
)
when {{
  {json.dumps(callers)}.contains(principal.id)
}};"""


def allowlist(gateway_arn: str, callers: Callers) -> dict[str, str]:
    """Each tool's permit, by its name, for the tools anyone may call yet."""
    tools = {Target.APP: APP_TOOLS, Target.CONTEXT: CONTEXT_TOOLS}
    return {
        policy_name(target, tool): permit(target, tool, gateway_arn, callers.of(target))
        for target, target_tools in tools.items()
        if callers.of(target)
        for tool in target_tools
    }


def make_engine(aws: Aws) -> dict[str, Any]:
    """The policy engine, made the first time, once it's active."""
    control = resources.control(aws)
    engine = resources.find_policy_engine(aws)
    if engine:
        engine_id = engine["policyEngineId"]
        print(f"Policy engine {names.POLICY_ENGINE}: unchanged")
    else:
        engine_id = control.create_policy_engine(
            name=names.POLICY_ENGINE,
            description="The allowlist for the PayrollCheck Gateway",
            tags=names.TAGS,
        )["policyEngineId"]
        print(f"Policy engine {names.POLICY_ENGINE}: created")
    control.get_waiter("policy_engine_active").wait(policyEngineId=engine_id)
    return control.get_policy_engine(policyEngineId=engine_id)


def allow_the_gateway_to_ask(aws: Aws, engine_arn: str, gateway_arn: str) -> None:
    """The Gateway's role may ask the engine about every call."""
    document = {
        "Version": POLICY_VERSION,
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "bedrock-agentcore:GetPolicyEngine",
                "Resource": engine_arn,
            },
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:AuthorizeAction",
                    "bedrock-agentcore:PartiallyAuthorizeActions",
                ],
                "Resource": [engine_arn, gateway_arn],
            },
        ],
    }
    aws.client("iam").put_role_policy(
        RoleName=names.GATEWAY_ROLE,
        PolicyName=f"{names.GATEWAY_ROLE}-policy-engine",
        PolicyDocument=json.dumps(document),
    )


def attach(aws: Aws, found: dict[str, Any], engine_arn: str) -> None:
    """Enforce the engine on the Gateway, trying again while the role's new
    permission travels, unless it's enforced already."""
    attached = {"arn": engine_arn, "mode": ENFORCE}
    if found.get("policyEngineConfiguration") == attached:
        print(f"Gateway {names.GATEWAY}'s Policy: unchanged")
        return
    control = resources.control(aws)
    waits.retry(
        lambda: control.update_gateway(
            gatewayIdentifier=found["gatewayId"],
            **gateway.gateway_settings(found["roleArn"]),
            policyEngineConfiguration=attached,
        ),
        lambda error: (
            isinstance(error, control.exceptions.ValidationException)
            and waits.says("GetPolicyEngine")(error)
        ),
        tries=20,
        every=5,
        message="Waiting for the role's new permission to reach AgentCore",
    )
    waits.wait_for(
        lambda: control.get_gateway(gatewayIdentifier=found["gatewayId"]),
        f"Gateway {names.GATEWAY}",
    )
    print(f"Gateway {names.GATEWAY}'s Policy: enforced")


def settled(aws: Aws, engine_id: str, policy_id: str, name: str, done: str) -> None:
    """Wait for a permit the engine is checking, printing its reasons, and stop the
    step when the engine refused it."""
    control = resources.control(aws)
    policy = waits.wait_for(
        partial(control.get_policy, policyEngineId=engine_id, policyId=policy_id),
        f"Policy {name}",
    )
    if policy["status"] != ACTIVE:
        raise RuntimeError(f"The engine refused the permit {name}")
    print(f"Policy {name}: {done}")


def put_policies(aws: Aws, engine_id: str, wanted: dict[str, str]) -> None:
    """Each permit: created when it's missing, updated when its statement differs
    or the engine refused it, and left alone when it's the same and active. A permit
    of ours the allowlist no longer has is deleted, so the engine holds only it."""
    control = resources.control(aws)
    there = {p["name"]: p for p in resources.find_policies(aws, engine_id)}
    for name, statement in wanted.items():
        definition = {"cedar": {"statement": statement}}
        if name not in there:
            policy_id = control.create_policy(
                policyEngineId=engine_id, name=name, definition=definition
            )["policyId"]
            settled(aws, engine_id, policy_id, name, "created")
            continue
        policy_id = there[name]["policyId"]
        current = control.get_policy(policyEngineId=engine_id, policyId=policy_id)
        if current["status"] == ACTIVE and current["definition"] == definition:
            print(f"Policy {name}: unchanged")
            continue
        control.update_policy(
            policyEngineId=engine_id, policyId=policy_id, definition=definition
        )
        settled(aws, engine_id, policy_id, name, "updated")
    for name in there.keys() - wanted.keys():
        control.delete_policy(
            policyEngineId=engine_id, policyId=there[name]["policyId"]
        )
        print(f"Policy {name}: deleted, as it's not on the allowlist")


def callers(aws: Aws, *, with_runtimes: bool) -> Callers:
    """Who may call the Gateway's tools now: the operator, and each runtime's role
    once it's there, which the Runtimes step needs both of, each its own."""
    roles = {}
    for name in (names.AGENT_RUNTIME, names.COPILOT_RUNTIME):
        runtime = resources.find_runtime(aws, name)
        if runtime is None and with_runtimes:
            raise RuntimeError(f"There's no runtime {name}: run agentcore deploy")
        roles[name] = caller_of(runtime["roleArn"]) if runtime else None
    agent, copilot = roles[names.AGENT_RUNTIME], roles[names.COPILOT_RUNTIME]
    if agent and agent == copilot:
        raise RuntimeError(
            "The agent and the Copilot share a role: the Policy can't tell them apart"
        )
    return Callers(operator=caller_of(aws.operator), agent=agent, copilot=copilot)


def run(aws: Aws, *, with_runtimes: bool = False) -> None:
    """Step 5: the engine, enforced on the Gateway, with the allowlist for whoever
    may call the Gateway's tools now. The Runtimes step runs it again with both
    runtimes there."""
    found = resources.find_gateway(aws)
    if found is None:
        raise RuntimeError("There's no Gateway yet: run step 4 first")
    engine = make_engine(aws)
    allow_the_gateway_to_ask(aws, engine["policyEngineArn"], found["gatewayArn"])
    attach(aws, found, engine["policyEngineArn"])
    wanted = allowlist(found["gatewayArn"], callers(aws, with_runtimes=with_runtimes))
    put_policies(aws, engine["policyEngineId"], wanted)
