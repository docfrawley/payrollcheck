"""The payroll agent's tools, the app's operations it calls on its route, the context
layer's lookups both agents have, and the search of its memory, and the context and
state they read."""

import operator
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict, cast

from langchain.tools import BaseTool, ToolException, ToolRuntime, tool
from langchain_core.messages import AnyMessage, ToolMessage
from langgraph.graph.message import add_messages
from langgraph.store.base import BaseStore
from langgraph.types import Command

from agent import api, app_terms, memory
from agent.agentcore_memory import UNREACHABLE
from agent.context_tools import CONTEXT_TOOLS, Query
from agent.json_text import as_json
from agent.routes import Route, Target


@dataclass
class PayrollContext:
    """The case a payroll agent is working on, its policy and subcontractor, the run it
    works in, if any, the route its tools take, and who its decisions are made by."""

    case_id: str
    run_id: str | None
    policy_id: str
    subcontractor_id: str
    route: Route
    decided_by: str


def keep_last(_: Any, new: Any) -> Any:
    """Keep the newest value, even when two tool calls set it in the same step. With
    it, LangGraph starts the key empty, as {} or "", so the key is always there."""
    return new


class PayrollState(TypedDict):
    """What the payroll graph keeps for one case, saved after every step: the check
    for hidden instructions' result, its reason and instructions_found, empty until
    the check has run, and the decision and the case's status as the backend
    recorded them, empty until then."""

    messages: Annotated[list[AnyMessage], add_messages]
    model_calls: Annotated[int, operator.add]
    screening: Annotated[dict[str, Any], keep_last]
    decision: Annotated[dict[str, Any], keep_last]
    status: Annotated[str, keep_last]


# What the payroll agent never reads of a case: the decisions reviewers sent back,
# whose notes reach its model only as a reviewer's message.
UNREAD = "sent_back_decisions"


def case_as_read(case: dict[str, Any]) -> str:
    """A case in full, as the payroll agent reads it, which is also what the check for
    hidden instructions reads."""
    return as_json({field: value for field, value in case.items() if field != UNREAD})


def on_app(runtime: ToolRuntime[PayrollContext], operation: str, **inputs: Any) -> Any:
    """Call one of the app's operations on the payroll agent's route."""
    return runtime.context.route.call(Target.APP, operation, inputs)


# A step a tool gives as its artifact, which the harness records on the case: its
# kind, its content and the context files it came from.
Step = tuple[api.StepKind, str, api.Sources]


@tool
def get_case(runtime: ToolRuntime[PayrollContext]) -> str:
    """Get your case in full: the story, the items claimed and the documents."""
    return case_as_read(on_app(runtime, "get_case", case_id=runtime.context.case_id))


@tool
def get_policy(runtime: ToolRuntime[PayrollContext]) -> str:
    """Get your case's policy: the plan, add-ons, purchase date, trip and travelers."""
    policy_id = runtime.context.policy_id
    return as_json(on_app(runtime, "get_policy", policy_id=policy_id))


@tool
def get_case_history(runtime: ToolRuntime[PayrollContext]) -> str:
    """Get your subcontractor's earlier cases, with the outcome and the amount paid."""
    subcontractor_id = runtime.context.subcontractor_id
    return as_json(
        on_app(runtime, "get_case_history", subcontractor_id=subcontractor_id)
    )


@tool(response_format="content_and_artifact")
def search_memory(
    query: Query, runtime: ToolRuntime[PayrollContext]
) -> tuple[str, Step]:
    """Search what we remember about this case's subcontractor from earlier cases."""
    context = runtime.context
    try:
        found = memory.recall(
            cast(BaseStore, runtime.store),
            context.subcontractor_id,
            context.case_id,
            query,
        )
    except UNREACHABLE as error:
        raise ToolException(f"The memory can't be reached. {error}") from error
    return as_json(found), ("memory_search", what_was_found(query, found), [])


def what_was_found(query: str, found: list[str]) -> str:
    """Say what a search of the memory looked for and what it found."""
    if not found:
        return f'"{query}": nothing found'
    return "\n".join([f'"{query}"', *(f"- {text}" for text in found)])


@tool
def calculate_payout(
    benefit: Annotated[api.Benefit, "The benefit the case is paid under"],
    lines: Annotated[
        list[api.Line],
        "The covered items and expenses, one for each line of the case, with any "
        "excluded ones left out",
    ],
    paid_by_others: Annotated[
        float, "What a carrier, hotel or anyone else has paid or refunded, or 0"
    ],
    runtime: ToolRuntime[PayrollContext],
) -> str:
    """Work out the payout on your case with UnderCover's payout rules."""
    payout = on_app(
        runtime,
        "calculate_payout",
        case_id=runtime.context.case_id,
        benefit=benefit,
        lines=[line.model_dump() for line in lines],
        paid_by_others=paid_by_others,
    )
    return as_json(payout)


@tool
def record_decision(
    decision: app_terms.DecisionKind,
    payout: Annotated[float, "In US dollars, and 0 for a decline or a referral"],
    section: Annotated[str, "The sections of the wording and the manual relied on"],
    reason: Annotated[str, "Two or three plain sentences for a colleague"],
    runtime: ToolRuntime[PayrollContext],
) -> Command:
    """Record the decision on your case, once, which ends your work on it."""
    case = on_app(
        runtime,
        "record_decision",
        case_id=runtime.context.case_id,
        decision=decision,
        payout=payout,
        section=section,
        reason=reason,
        decided_by=runtime.context.decided_by,
    )
    message = ToolMessage(case_as_read(case), tool_call_id=runtime.tool_call_id)
    update = {
        "messages": [message],
        "decision": case["decision"],
        "status": case["status"],
    }
    return Command(update=update)


APP_TOOLS = [
    get_case,
    get_policy,
    get_case_history,
    calculate_payout,
    record_decision,
]
PAYROLL_TOOLS = APP_TOOLS + CONTEXT_TOOLS


def payroll_tools(remembers: bool) -> list[BaseTool]:
    """The payroll agent's tools, with a search of its memory when it has one."""
    return PAYROLL_TOOLS + [search_memory] if remembers else PAYROLL_TOOLS


# The target each tool calls, by which a route names a call to it.
TARGETS = {tool.name: Target.APP for tool in APP_TOOLS} | {
    tool.name: Target.CONTEXT for tool in CONTEXT_TOOLS
}
