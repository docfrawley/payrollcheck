"""The payroll agent's tools: the app's reads and its exception report on its route,
and the context layer's lookups both agents have, with the context and state they
read. No tool takes a case, project or subcontractor id from the model: each fills
them in from the context."""

import operator
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AnyMessage, ToolMessage
from langgraph.graph.message import add_messages
from langgraph.types import Command
from pydantic import BaseModel, Field

from agent.app_operations import (
    GET_CASE,
    GET_PAYROLL_HISTORY,
    GET_PROJECT,
    LIST_SUBCONTRACTORS,
    RECORD_EXCEPTION_REPORT,
)
from agent.checks.findings import CHECK_DECIDES, RULES
from agent.context_tools import CONTEXT_TOOLS
from agent.json_text import as_json
from agent.routes import Route, Target


@dataclass
class PayrollContext:
    """The case a payroll agent is working on, its project and subcontractor, the run
    it works in, if any, the route its tools take, who its exceptions are raised by
    and the check tools' parameters from its version."""

    case_id: str
    run_id: str | None
    project_id: str
    subcontractor_id: str
    route: Route
    raised_by: str
    parameters: dict[str, Any]


def keep_last(_: Any, new: Any) -> Any:
    """Keep the newest value, even when two tool calls set it in the same step. With
    it, LangGraph starts the key empty, as {} or "", so the key is always there."""
    return new


class PayrollState(TypedDict):
    """What the payroll graph keeps for one case, saved after every step: the
    screening's result, its reason and instructions_found, empty until it has run,
    and the case's status once the report is recorded, empty until then."""

    messages: Annotated[list[AnyMessage], add_messages]
    model_calls: Annotated[int, operator.add]
    screening: Annotated[dict[str, Any], keep_last]
    status: Annotated[str, keep_last]


def on_app(runtime: ToolRuntime[PayrollContext], operation: str, **inputs: Any) -> Any:
    """Call one of the app's operations on the payroll agent's route."""
    return runtime.context.route.call(Target.APP, operation, inputs)


@tool
def get_case(runtime: ToolRuntime[PayrollContext]) -> str:
    """Get your case: its submissions, its workers and the checks' findings."""
    return as_json(on_app(runtime, GET_CASE, case_id=runtime.context.case_id))


@tool
def get_project(runtime: ToolRuntime[PayrollContext]) -> str:
    """Get your case's project: its county, public body, contract and award date."""
    project_id = runtime.context.project_id
    return as_json(on_app(runtime, GET_PROJECT, project_id=project_id))


@tool
def list_subcontractors(runtime: ToolRuntime[PayrollContext]) -> str:
    """List your project's subcontractors: legal names and engagement windows."""
    project_id = runtime.context.project_id
    return as_json(on_app(runtime, LIST_SUBCONTRACTORS, project_id=project_id))


@tool
def get_payroll_history(runtime: ToolRuntime[PayrollContext]) -> str:
    """Get your subcontractor's payrolls of record for earlier weeks on the project."""
    case_id = runtime.context.case_id
    return as_json(on_app(runtime, GET_PAYROLL_HISTORY, case_id=case_id))


class Dismissal(BaseModel):
    candidate_id: int
    reason: str = Field(description="Why the finding isn't a breach, for a reviewer")


class AddedException(BaseModel):
    """A breach no check found, which carries no money."""

    rule: str = Field(
        description=f"One of {', '.join(r for r in RULES if r not in CHECK_DECIDES)}"
    )
    worker_id: str | None = Field(description="None for a rule about the payroll")
    line_no: int | None
    expected: str
    actual: str
    shortfall_cents: int | None = Field(
        description="None: only a check tool's finding carries a shortfall"
    )
    citation: str = Field(description="The record or rule it rests on")


@tool
def record_exception_report(
    raised: Annotated[list[int], "The candidates you raise as exceptions, by id"],
    dismissed: Annotated[
        list[Dismissal],
        "The candidates you dismiss, each with its reason; never one under "
        f"{' or '.join(CHECK_DECIDES)}, which its check alone decides",
    ],
    added: Annotated[list[AddedException], "Breaches no check found, with no money"],
    notice: Annotated[
        str,
        "The draft send-back notice to the subcontractor's payroll clerk, covering "
        "every exception, or blank when there are none",
    ],
    runtime: ToolRuntime[PayrollContext],
) -> Command:
    """Record your exception report and draft notice, once, which ends your work."""
    case = on_app(
        runtime,
        RECORD_EXCEPTION_REPORT,
        case_id=runtime.context.case_id,
        raised=raised,
        dismissed=[d.model_dump() for d in dismissed],
        added=[a.model_dump() for a in added],
        notice=notice,
        raised_by=runtime.context.raised_by,
    )
    message = ToolMessage(as_json(case), tool_call_id=runtime.tool_call_id)
    return Command(update={"messages": [message], "status": case["status"]})


APP_TOOLS = [
    get_case,
    get_project,
    list_subcontractors,
    get_payroll_history,
    record_exception_report,
]
PAYROLL_TOOLS = APP_TOOLS + CONTEXT_TOOLS
# The target each tool calls, by which a route names a call to it.
TARGETS = {tool.name: Target.APP for tool in APP_TOOLS} | {
    tool.name: Target.CONTEXT for tool in CONTEXT_TOOLS
}
