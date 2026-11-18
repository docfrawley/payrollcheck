"""The smoke check's parts that are code, run after the runbook on the deployed product:
the Copilot's answer to one of the six questions, checked against the expected answers,
with its Memory's events; the Policy probe, signed as the operator through the
Gateway, a context tool allowed and an app tool refused, with each target's logs read
over the probe; and the policy engine's decisions."""

from datetime import UTC, datetime, timedelta
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import StreamableHttpConnection
from mcp.shared.exceptions import McpError
from sqlalchemy import select

from agent import app_operations, context_tools
from agent.gateway import SEPARATOR, SigV4Auth
from agent.mcp_tools import SERVER, run_async
from agent.routes import Target
from backend.database import conversations, copilot_turns, engine, reviewers
from backend.models import TurnStatus
from backend.money import cents_in_dollars
from data.payroll_world.expected_answers import QUESTIONS, answer_to, read_expected
from data.payroll_world.worlds import MARCUS
from deploy import names, resources, waits
from deploy.aws import Aws
from deploy.settings import REPO

QUESTION = 2
ALLOWED = (Target.CONTEXT, context_tools.GET_FILING_RULES, {})
REFUSED = (Target.APP, app_operations.GET_CASE, {"case_id": "PC-1201"})
# What the Gateway says when its Policy refuses a call, which phase 5 confirms.
POLICY_DENIED = "not allowed due to policy enforcement"
# How long Lambda can take to deliver a function's logs.
LOG_DELAY = 60
START = "START RequestId"


def latest_turn(email: str) -> dict[str, Any]:
    """A reviewer's latest finished turn with the Copilot, from the app's records."""
    query = (
        select(copilot_turns, conversations.c.reviewer_id)
        .select_from(
            copilot_turns.join(conversations).join(
                reviewers, conversations.c.reviewer_id == reviewers.c.reviewer_id
            )
        )
        .where(reviewers.c.email == email, copilot_turns.c.status == TurnStatus.DONE)
        .order_by(copilot_turns.c.started_at.desc())
        .limit(1)
    )
    with engine().connect() as db:
        turn = db.execute(query).mappings().first()
    if turn is None:
        raise RuntimeError(f"{email} has no answer from the Copilot yet")
    return dict(turn)


def missing_from(answer: str, expected: dict[str, Any]) -> list[str]:
    """The case ids and the total an answer should name and doesn't."""
    wanted = [*expected["case_ids"], cents_in_dollars(expected["flagged_cents"])]
    return [each for each in wanted if each not in answer]


def copilot(aws: Aws) -> None:
    """Marcus's latest answer from the Copilot names question 2's case ids and total,
    and the Copilot's Memory holds the conversation's events."""
    turn = latest_turn(MARCUS)
    expected = answer_to(read_expected(REPO / "data"), QUESTION)
    print(f"Asked: {turn['message']}")
    if turn["message"].strip() != QUESTIONS[QUESTION - 1]:
        raise RuntimeError(f"Marcus's latest question isn't: {QUESTIONS[QUESTION - 1]}")
    print(f"Answered: {turn['answer']}")
    missing = missing_from(turn["answer"], expected)
    memory = resources.find_memory(aws)
    if memory is None:
        raise RuntimeError("There's no Copilot Memory: run step 6")
    events = aws.client("bedrock-agentcore").list_events(
        memoryId=memory["id"],
        actorId=turn["reviewer_id"],
        sessionId=turn["conversation_id"],
    )["events"]
    print(f"The Copilot's Memory holds {len(events)} events of the conversation")
    if missing:
        raise RuntimeError(f"The answer doesn't name {', '.join(missing)}")
    if not events:
        raise RuntimeError("The Copilot's Memory has none of the conversation")
    print(f"The answer names {', '.join(expected['case_ids'])} and the total")


def call_by_name(
    aws: Aws, url: str, name: str, inputs: dict[str, Any]
) -> tuple[bool, str]:
    """Call a Gateway tool by its name, signed with the operator's credentials, in a
    session of its own, whether or not the Gateway lists it to the operator.
    Returns whether it answered, and its answer or refusal."""
    connection = StreamableHttpConnection(
        transport="streamable_http", url=url, auth=SigV4Auth(aws.session)
    )
    client = MultiServerMCPClient({SERVER: connection})

    async def call() -> tuple[bool, str]:
        async with client.session(SERVER) as session:
            try:
                result = await session.call_tool(name, inputs)
            except McpError as refused:
                return False, str(refused)
        text = "".join(getattr(block, "text", "") for block in result.content)
        return not result.isError, text

    return run_async(call())


def invocations(aws: Aws, function: str, start: datetime, end: datetime) -> int:
    """How many times a function ran between two moments, from its log group."""
    pages = (
        aws.client("logs")
        .get_paginator("filter_log_events")
        .paginate(
            logGroupName=names.log_group(function),
            startTime=int(start.timestamp() * 1000),
            endTime=int(end.timestamp() * 1000),
            filterPattern=f'"{START}"',
        )
    )
    return sum(len(page["events"]) for page in pages)


def probe(aws: Aws) -> None:
    """The Policy at work: signed as the operator, a context tool answers and reaches
    the context layer, and an app tool is refused and never reaches the app."""
    gateway = resources.find_gateway(aws)
    if gateway is None:
        raise RuntimeError("There's no Gateway: run step 4")
    start = datetime.now(UTC)
    outcomes = {}
    for target, tool, inputs in (ALLOWED, REFUSED):
        name = f"{target}{SEPARATOR}{tool}"
        outcomes[name] = call_by_name(aws, gateway["gatewayUrl"], name, inputs)
        answered, text = outcomes[name]
        print(f"{name}: {'answered' if answered else 'refused'}: {text[:300]}")
    end = datetime.now(UTC)
    print(f"Waiting {LOG_DELAY} seconds for Lambda to deliver the functions' logs")
    waits.pause(LOG_DELAY)
    reached = {
        function: invocations(aws, function, start, end)
        for function in (names.CONTEXT_FUNCTION, names.APP_FUNCTION)
    }
    for function, count in reached.items():
        print(f"{function} ran {count} times during the probe")
    allowed, refused = outcomes.values()
    refused_by_policy = not refused[0] and POLICY_DENIED in refused[1].lower()
    if not allowed[0] or not refused_by_policy:
        raise RuntimeError("The Policy didn't answer the probe as the allowlist says")
    if reached[names.APP_FUNCTION] or not reached[names.CONTEXT_FUNCTION]:
        raise RuntimeError("The logs don't show the refused call kept from the app")
    print("The Policy refused the app's tool, and the call never reached the app")


def decisions(aws: Aws) -> None:
    """The policy engine's decisions over the last three hours, which CloudWatch
    counts a minute or two behind, as Ed's lab read them."""
    engine_found = resources.find_policy_engine(aws)
    if engine_found is None:
        raise RuntimeError("There's no policy engine: run step 5")
    now = datetime.now(UTC)
    totals: dict[str, int] = {}
    for metric in ("AllowDecisions", "DenyDecisions"):
        stats = aws.client("cloudwatch").get_metric_statistics(
            Namespace="AWS/Bedrock-AgentCore",
            MetricName=metric,
            Dimensions=[
                {"Name": "OperationName", "Value": "AuthorizeAction"},
                {"Name": "Mode", "Value": "ENFORCE"},
                {"Name": "PolicyEngine", "Value": engine_found["policyEngineId"]},
            ],
            StartTime=now - timedelta(hours=3),
            EndTime=now,
            Period=3600,
            Statistics=["Sum"],
        )
        totals[metric] = int(sum(point["Sum"] for point in stats["Datapoints"]))
        print(f"{metric}: {totals[metric]}")
    if not totals["DenyDecisions"]:
        raise RuntimeError(
            "The engine has counted no refusal yet: run the Policy probe, or wait a"
            " few minutes and read again"
        )


PARTS = {"copilot": copilot, "policy": probe, "decisions": decisions}


def run(aws: Aws, part: str) -> None:
    """One part of the smoke check: copilot, policy or decisions."""
    PARTS[part](aws)
