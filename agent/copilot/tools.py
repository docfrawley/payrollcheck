"""The Copilot's tools, which reach the app through its API with the reviewer's
sign-in and the context layer on the route in their context, the context they
read, and the kind of card each one makes. Each is thin: it calls its one route,
with null for an input the model left out and a period by name, and returns what
the app says. It reads, drafts a notice and starts the agent's work; no tool
signs off, sends back or overrides a case: those happen on the case page, by the
reviewer."""

from dataclasses import dataclass, field
from typing import Annotated, Any

from langchain.tools import BaseTool, ToolRuntime, tool
from pydantic import Field, StringConstraints

from agent.app_terms import EvaluationSet
from agent.context_tools import CONTEXT_TOOLS
from agent.copilot import app_api, waiting
from agent.copilot.app_api import CardKind
from agent.copilot.filters import (
    ALL_EXPOSURE,
    EVERY_CASE,
    CaseFilters,
    ExposureFilters,
    PeriodFilters,
    body,
)
from agent.json_text import as_json
from agent.routes import Route

# The memory's lookup at the start of a turn, which the code makes, not the model.
SEARCH_MEMORY = "search_memory"
# A search needs a word to look for.
Words = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
# How many payroll agents a start the reviewer didn't size works at once, as the
# queue page first offers. The settings' number is the improver's, which only the
# compliance manager reads.
FIRST_CHOICE = 3
Agents = Annotated[
    int,
    Field(
        description="How many payroll agents work at once, from 1 to 25",
        ge=1,
        le=25,
    ),
]


@dataclass
class CopilotContext:
    """Who the Copilot works for on a turn and how it reaches them: the reviewer's
    sign-in, the reviewer as the app gave them, the conversation and the turn, the
    route its context layer tools take and the business date the app gave. LangGraph
    hands it to the nodes and the tools and never saves it."""

    sign_in: str = field(repr=False)
    reviewer: dict[str, Any]
    conversation_id: str
    turn_id: str
    route: Route
    business_date: str


def sign_in_of(runtime: ToolRuntime[CopilotContext]) -> str:
    return runtime.context.sign_in


@tool
def list_cases(
    runtime: ToolRuntime[CopilotContext], filters: CaseFilters = EVERY_CASE
) -> str:
    """Find the queue's cases by any of these, with each subcontractor's counted."""
    return as_json(app_api.find_cases(sign_in_of(runtime), body(filters)))


@tool
def get_case(case_id: str, runtime: ToolRuntime[CopilotContext]) -> str:
    """Get a case in full: its submissions, exceptions, findings and notice."""
    return as_json(app_api.read_case(sign_in_of(runtime), case_id))


@tool
def get_exceptions(case_id: str, runtime: ToolRuntime[CopilotContext]) -> str:
    """Get the exceptions open on a case, each with its citation and amount owed."""
    return as_json(app_api.get_exceptions(sign_in_of(runtime), case_id))


@tool
def exposure_summary(
    runtime: ToolRuntime[CopilotContext], filters: ExposureFilters = ALL_EXPOSURE
) -> str:
    """Total the underpayment flagged and still outstanding, by rule, with its cases."""
    return as_json(app_api.exposure_summary(sign_in_of(runtime), body(filters)))


@tool
def filings_status(filters: PeriodFilters, runtime: ToolRuntime[CopilotContext]) -> str:
    """List a period's expected payrolls that are late, missing or on time."""
    return as_json(app_api.filings_status(sign_in_of(runtime), body(filters)))


@tool
def classification_changes(
    filters: PeriodFilters, runtime: ToolRuntime[CopilotContext]
) -> str:
    """List the workers whose classification changed from the week before."""
    found = app_api.classification_changes(sign_in_of(runtime), body(filters))
    return as_json(found)


@tool
def find_subcontractors(name: Words, runtime: ToolRuntime[CopilotContext]) -> str:
    """Find subcontractors whose legal name holds every word given, with their ids."""
    return as_json(app_api.find_subcontractors(sign_in_of(runtime), name))


@tool
def find_projects(name: Words, runtime: ToolRuntime[CopilotContext]) -> str:
    """Find our projects whose name holds every word given, with their ids."""
    return as_json(app_api.find_projects(sign_in_of(runtime), name))


@tool
def draft_notice(case_id: str, runtime: ToolRuntime[CopilotContext]) -> str:
    """Draft a case's send-back notice and save it, for the reviewer to send."""
    return as_json(app_api.draft_notice(sign_in_of(runtime), case_id))


@tool
def check_success_criteria(runtime: ToolRuntime[CopilotContext]) -> str:
    """Check the success criteria we agreed, each figure and verdict from our app."""
    return as_json(app_api.check_success_criteria(sign_in_of(runtime)))


@tool
def get_latest_dispatch(runtime: ToolRuntime[CopilotContext]) -> str:
    """Get the latest dispatch with its cases, cost, time and summary, or nothing."""
    return as_json(app_api.get_latest_dispatch(sign_in_of(runtime)))


def started(run: dict[str, Any]) -> str:
    """What the model is told of a run it started: its id and number."""
    return as_json({"run_id": run["run_id"], "number": run["number"]})


@tool
def wait_for_run(run_id: str, runtime: ToolRuntime[CopilotContext]) -> str:
    """Wait for a dispatch or evaluation you started to end, and get how it went."""
    sign_in = sign_in_of(runtime)
    return as_json(waiting.how_it_went(sign_in, waiting.wait_for(sign_in, run_id)))


@tool
def start_dispatch(
    runtime: ToolRuntime[CopilotContext], agents: Agents = FIRST_CHOICE
) -> str:
    """Start a dispatch of the queue with the payroll agents at once given."""
    return started(app_api.start_dispatch(sign_in_of(runtime), agents))


@tool
def start_evaluation(
    evaluation_set: Annotated[
        EvaluationSet,
        "The development set, the held-out set, or the development set's tiny cases",
    ],
    runtime: ToolRuntime[CopilotContext],
    agents: Agents = FIRST_CHOICE,
) -> str:
    """Start an evaluation of one of our labelled sets, or the tiny set."""
    run = app_api.start_evaluation(sign_in_of(runtime), evaluation_set, agents)
    return started(run)


CASE_TOOLS: list[BaseTool] = [list_cases, get_case, get_exceptions]
SUBCONTRACTOR_TOOLS: list[BaseTool] = [find_subcontractors]
PROJECT_TOOLS: list[BaseTool] = [find_projects]
WORK_TOOLS: list[BaseTool] = [
    exposure_summary,
    filings_status,
    classification_changes,
    get_latest_dispatch,
    wait_for_run,
    check_success_criteria,
]
ACTION_TOOLS: list[BaseTool] = [draft_notice, start_dispatch, start_evaluation]
COPILOT_TOOLS = (
    CASE_TOOLS
    + SUBCONTRACTOR_TOOLS
    + PROJECT_TOOLS
    + CONTEXT_TOOLS
    + WORK_TOOLS
    + ACTION_TOOLS
)


def kind_of_each(names: list[str], kind: CardKind) -> dict[str, CardKind]:
    return {name: kind for name in names}


def names(tools: list[BaseTool]) -> list[str]:
    return [tool.name for tool in tools]


# The kind of card each tool makes, and the memory's lookup.
KINDS = (
    kind_of_each(names(CASE_TOOLS), "cases")
    | kind_of_each(names(SUBCONTRACTOR_TOOLS), "subcontractors")
    | kind_of_each(names(PROJECT_TOOLS), "projects")
    | kind_of_each(names(CONTEXT_TOOLS), "context")
    | kind_of_each(names(WORK_TOOLS), "work")
    | kind_of_each(names(ACTION_TOOLS), "action")
    | kind_of_each([SEARCH_MEMORY], "memory")
)
