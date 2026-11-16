"""The Copilot's tools, which reach the app through its API with the reviewer's
sign-in and the context layer on the route in their context, the context they
read, and the kind of card each one makes. No tool signs off or sends back a
case: those happen on the case page, by the reviewer."""

from dataclasses import dataclass, field
from typing import Annotated, Any

from langchain.tools import BaseTool, ToolRuntime, tool
from pydantic import Field, StringConstraints

from agent.app_terms import EvaluationSet
from agent.context_tools import CONTEXT_TOOLS
from agent.copilot import app_api, waiting
from agent.copilot.app_api import CardKind
from agent.copilot.needs_a_reviewer import needs_a_reviewer
from agent.json_text import as_json
from agent.routes import Route

# The memory's lookup at the start of a turn, which the code makes, not the model.
SEARCH_MEMORY = "search_memory"
# A search needs a word to look for.
Words = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Agents = Annotated[
    int | None,
    Field(
        description="How many payroll agents work at once, or null for the number in "
        "our settings"
    ),
]


@dataclass
class CopilotContext:
    """Who the Copilot works for on a turn and how it reaches them: the reviewer's
    sign-in, the reviewer as the app gave them, the conversation and the turn, and
    the route its context layer tools take. LangGraph hands it to the nodes and
    the tools and never saves it."""

    sign_in: str = field(repr=False)
    reviewer: dict[str, Any]
    conversation_id: str
    turn_id: str
    route: Route


def sign_in_of(runtime: ToolRuntime[CopilotContext]) -> str:
    return runtime.context.sign_in


@tool
def list_cases(runtime: ToolRuntime[CopilotContext]) -> str:
    """List the queue's cases with where each stands, its flags and open exceptions."""
    return as_json(app_api.list_cases(sign_in_of(runtime)))


@tool
def get_case(case_id: str, runtime: ToolRuntime[CopilotContext]) -> str:
    """Get a case in full: its submissions, exceptions, findings and notice."""
    return as_json(app_api.get_case(sign_in_of(runtime), case_id))


@tool
def list_steps(case_id: str, runtime: ToolRuntime[CopilotContext]) -> str:
    """List the payroll agent's steps on a case, in order, with what it looked up."""
    return as_json(app_api.list_steps(sign_in_of(runtime), case_id))


@tool
def find_subcontractors(name: Words, runtime: ToolRuntime[CopilotContext]) -> str:
    """Find subcontractors whose legal name holds every word given, with their ids."""
    return as_json(app_api.find_subcontractors(sign_in_of(runtime), name))


@tool
def get_subcontractor(
    subcontractor_id: str, runtime: ToolRuntime[CopilotContext]
) -> str:
    """Get a subcontractor with its record, its projects and its cases in our queue."""
    return as_json(app_api.get_subcontractor(sign_in_of(runtime), subcontractor_id))


@tool
def get_latest_dispatch(runtime: ToolRuntime[CopilotContext]) -> str:
    """Get the latest dispatch with its cases, cost, time and summary, or nothing."""
    return as_json(app_api.get_latest_dispatch(sign_in_of(runtime)))


@tool
def list_evaluations(runtime: ToolRuntime[CopilotContext]) -> str:
    """List the evaluations, newest first, with their measures."""
    return as_json(app_api.list_evaluations(sign_in_of(runtime)))


@tool
def get_settings(runtime: ToolRuntime[CopilotContext]) -> str:
    """Get our settings: the objectives, spending limit and payroll agents at once."""
    return as_json(app_api.get_settings(sign_in_of(runtime)))


def agents_or_settings(sign_in: str, agents: int | None) -> int:
    """The payroll agents the reviewer asked for, or the number in our settings."""
    if agents is not None:
        return agents
    return app_api.get_settings(sign_in)["current"]["agents"]


def started(run: dict[str, Any]) -> str:
    """What the model is told of a run it started: its id and number."""
    return as_json({"run_id": run["run_id"], "number": run["number"]})


@tool
def what_needs_a_reviewer(runtime: ToolRuntime[CopilotContext]) -> str:
    """List the queue's cases awaiting review: flagged, failed, with exceptions."""
    return as_json(needs_a_reviewer(app_api.list_cases(sign_in_of(runtime))))


@tool
def wait_for_run(run_id: str, runtime: ToolRuntime[CopilotContext]) -> str:
    """Wait for a dispatch or evaluation you started to end, and get how it went."""
    sign_in = sign_in_of(runtime)
    return as_json(waiting.how_it_went(sign_in, waiting.wait_for(sign_in, run_id)))


@tool
def start_dispatch(agents: Agents, runtime: ToolRuntime[CopilotContext]) -> str:
    """Start a dispatch of the queue with the payroll agents at once given."""
    sign_in = sign_in_of(runtime)
    return started(app_api.start_dispatch(sign_in, agents_or_settings(sign_in, agents)))


@tool
def start_evaluation(
    evaluation_set: Annotated[
        EvaluationSet,
        "The development set, the held-out set, or the development set's tiny cases",
    ],
    agents: Agents,
    runtime: ToolRuntime[CopilotContext],
) -> str:
    """Start an evaluation of one of our labelled sets, or the tiny set."""
    sign_in = sign_in_of(runtime)
    run = app_api.start_evaluation(
        sign_in, evaluation_set, agents_or_settings(sign_in, agents)
    )
    return started(run)


PAYROLL_TOOLS: list[BaseTool] = [
    list_cases,
    get_case,
    list_steps,
    what_needs_a_reviewer,
]
SUBCONTRACTOR_TOOLS: list[BaseTool] = [
    find_subcontractors,
    get_subcontractor,
]
WORK_TOOLS: list[BaseTool] = [
    get_latest_dispatch,
    list_evaluations,
    get_settings,
    wait_for_run,
]
ACTION_TOOLS: list[BaseTool] = [
    start_dispatch,
    start_evaluation,
]
COPILOT_TOOLS = (
    PAYROLL_TOOLS + SUBCONTRACTOR_TOOLS + CONTEXT_TOOLS + WORK_TOOLS + ACTION_TOOLS
)


def kind_of_each(names: list[str], kind: CardKind) -> dict[str, CardKind]:
    return {name: kind for name in names}


def names(tools: list[BaseTool]) -> list[str]:
    return [tool.name for tool in tools]


# The kind of card each tool makes, and the memory's lookup.
KINDS = (
    kind_of_each(names(PAYROLL_TOOLS), "cases")
    | kind_of_each(names(SUBCONTRACTOR_TOOLS), "subcontractors")
    | kind_of_each(names(CONTEXT_TOOLS), "context")
    | kind_of_each(names(WORK_TOOLS), "work")
    | kind_of_each(names(ACTION_TOOLS), "action")
    | kind_of_each([SEARCH_MEMORY], "memory")
)
