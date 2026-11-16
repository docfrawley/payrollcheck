"""The Copilot's tools, which reach the app through its API with the reviewer's
sign-in and the context layer on the route in their context, the context they
read, and the kind of card each one makes. The sign-off is a schema the model can ask
for, which the graph answers itself: no tool pays."""

from dataclasses import dataclass, field
from typing import Annotated, Any

from langchain.tools import BaseTool, ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from agent.app_terms import EvaluationSet
from agent.context_tools import CONTEXT_TOOLS
from agent.copilot import app_api, criteria, waiting
from agent.copilot.app_api import CardKind
from agent.copilot.needs_a_reviewer import needs_a_reviewer
from agent.json_text import as_json
from agent.routes import Route

SIGN_OFF = "sign_off_case"
# The memory's lookup at the start of a turn, which the code makes, not the model.
SEARCH_MEMORY = "search_memory"
# A search needs a word to look for, and a note something to say.
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


class SignOffCase(BaseModel):
    """Sign off a payout held for sign-off, which pays it. The reviewer confirms on
    a card first, and nothing is paid if they cancel."""

    model_config = ConfigDict(title=SIGN_OFF)

    case_id: str = Field(description="The case held for sign-off, such as CLM-1003")


def sign_in_of(runtime: ToolRuntime[CopilotContext]) -> str:
    return runtime.context.sign_in


@tool
def list_cases(runtime: ToolRuntime[CopilotContext]) -> str:
    """List the cases in the queue with where each stands, its decision and payout."""
    return as_json(app_api.list_cases(sign_in_of(runtime)))


@tool
def get_case(case_id: str, runtime: ToolRuntime[CopilotContext]) -> str:
    """Get a case in full, with its decision, payout and any decision sent back."""
    return as_json(app_api.get_case(sign_in_of(runtime), case_id))


@tool
def list_steps(case_id: str, runtime: ToolRuntime[CopilotContext]) -> str:
    """List the payroll agent's steps on a case, in order, with what it looked up."""
    return as_json(app_api.list_steps(sign_in_of(runtime), case_id))


@tool
def find_subcontractors(name: Words, runtime: ToolRuntime[CopilotContext]) -> str:
    """Find subcontractors whose name holds every word given, with their ids."""
    return as_json(app_api.find_subcontractors(sign_in_of(runtime), name))


@tool
def get_subcontractor(
    subcontractor_id: str, runtime: ToolRuntime[CopilotContext]
) -> str:
    """Get a subcontractor with their policies, earlier cases and cases in our queue."""
    return as_json(app_api.get_subcontractor(sign_in_of(runtime), subcontractor_id))


@tool
def get_policy(policy_id: str, runtime: ToolRuntime[CopilotContext]) -> str:
    """Get a policy: the plan, add-ons, purchase date, trip and travelers."""
    return as_json(app_api.get_policy(sign_in_of(runtime), policy_id))


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
    """Get our settings: the approval limit, objectives and payroll agents at once."""
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
    """List what in the queue needs a reviewer: held payouts, referrals and the rest."""
    return as_json(needs_a_reviewer(app_api.list_cases(sign_in_of(runtime))))


@tool
def wait_for_run(run_id: str, runtime: ToolRuntime[CopilotContext]) -> str:
    """Wait for a dispatch or evaluation you started to end, and get how it went."""
    sign_in = sign_in_of(runtime)
    return as_json(waiting.how_it_went(sign_in, waiting.wait_for(sign_in, run_id)))


@tool
def check_success_criteria(runtime: ToolRuntime[CopilotContext]) -> Command:
    """Check the three success criteria we agreed, with an evaluation of their own."""
    answer = criteria.check(sign_in_of(runtime))
    message = ToolMessage(answer, tool_call_id=runtime.tool_call_id)
    return Command(update={"messages": [message], "criteria": answer})


@tool
def start_dispatch(agents: Agents, runtime: ToolRuntime[CopilotContext]) -> str:
    """Start a dispatch of the queue with the payroll agents at once given."""
    sign_in = sign_in_of(runtime)
    return started(app_api.start_dispatch(sign_in, agents_or_settings(sign_in, agents)))


@tool
def start_evaluation(
    evaluation_set: Annotated[
        EvaluationSet, "The evaluation set, or the held-out set our criteria use"
    ],
    tiny: Annotated[bool, "Only the set's five tiny cases, rather than all of it"],
    agents: Agents,
    runtime: ToolRuntime[CopilotContext],
) -> str:
    """Start an evaluation of one of our labeled sets, whole or its tiny cases."""
    sign_in = sign_in_of(runtime)
    run = app_api.start_evaluation(
        sign_in, evaluation_set, tiny, agents_or_settings(sign_in, agents)
    )
    return started(run)


@tool
def send_back_case(
    case_id: str,
    note: Annotated[
        Words, "What the agent should look at again, up to 1,000 characters"
    ],
    runtime: ToolRuntime[CopilotContext],
) -> str:
    """Send a decision held for sign-off back to the agent with a note."""
    return as_json(app_api.send_back_case(sign_in_of(runtime), case_id, note))


PAYROLL_TOOLS: list[BaseTool] = [
    list_cases,
    get_case,
    list_steps,
    what_needs_a_reviewer,
]
SUBCONTRACTOR_TOOLS: list[BaseTool] = [
    find_subcontractors,
    get_subcontractor,
    get_policy,
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
    send_back_case,
    check_success_criteria,
]
COPILOT_TOOLS = (
    PAYROLL_TOOLS + SUBCONTRACTOR_TOOLS + CONTEXT_TOOLS + WORK_TOOLS + ACTION_TOOLS
)


def kind_of_each(names: list[str], kind: CardKind) -> dict[str, CardKind]:
    return {name: kind for name in names}


def names(tools: list[BaseTool]) -> list[str]:
    return [tool.name for tool in tools]


# The kind of card each tool makes, and the sign-off.
KINDS = (
    kind_of_each(names(PAYROLL_TOOLS), "cases")
    | kind_of_each(names(SUBCONTRACTOR_TOOLS), "subcontractors")
    | kind_of_each(names(CONTEXT_TOOLS), "context")
    | kind_of_each(names(WORK_TOOLS), "work")
    | kind_of_each([*names(ACTION_TOOLS), SIGN_OFF], "action")
    | kind_of_each([SEARCH_MEMORY], "memory")
)
