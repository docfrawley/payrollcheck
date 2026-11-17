"""The Copilot's graph, written by hand: a node that asks the model, LangGraph's
ToolNode, and the loop between them, and with a memory, the reviewer's memories
searched as a turn starts and its message and answer saved as it ends. The graph
saves its state after every step on the conversation's thread."""

import logging
import operator
from collections.abc import Callable
from functools import partial
from http import HTTPStatus
from typing import Annotated, Any, TypedDict, cast

from langchain.tools import ToolException
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore
from langgraph.types import Command, Overwrite

from agent.agentcore_memory import UNREACHABLE
from agent.console import describe
from agent.context_tools import Sources
from agent.copilot import app_api, cards, memory
from agent.copilot.instructions import instructions_for
from agent.copilot.tools import (
    COPILOT_TOOLS,
    KINDS,
    SEARCH_MEMORY,
    CopilotContext,
)
from agent.openrouter import usage_of
from agent.refusals import REFUSED
from agent.routes import GatewayRefused

log = logging.getLogger(__name__)

TURN_MODEL_CALLS = 25
BEGIN = "begin"
RECALL = "recall"
REMEMBER = "remember"
AGENT = "agent"
TOOLS = "tools"
FOUND_NOTHING = "Nothing remembered that bears on this"
MEMORY_UNREACHABLE = "The memory can't be reached. {error}"
# The app's, the Gateway's and a tool's own refusals, which go back to the model.
REFUSALS = (app_api.Refused, GatewayRefused, ToolException)

CopilotGraph = CompiledStateGraph["CopilotState", CopilotContext, Any, Any]


class TooManyModelCalls(Exception):
    """The Copilot made as many model calls in a turn as it may without
    finishing."""


class CopilotState(TypedDict):
    """What the graph keeps for a conversation, saved after every step: its
    messages, the turn's model calls and their cost, and what the memory found."""

    messages: Annotated[list[AnyMessage], add_messages]
    model_calls: Annotated[int, operator.add]
    cost: Annotated[float, operator.add]
    remembered: list[str]


def begin(state: CopilotState) -> dict[str, Any]:
    """Start a turn's counts again from zero, with nothing remembered."""
    return {
        "model_calls": Overwrite(0),
        "cost": Overwrite(0.0),
        "remembered": [],
    }


def message_of(state: CopilotState) -> str:
    """The reviewer's message this turn answers."""
    return next(
        m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)
    ).text


def what_was_found(found: list[str]) -> str:
    """What a search of the memory found, as its card shows it."""
    return "\n".join(f"- {text}" for text in found) or FOUND_NOTHING


def recall(state: CopilotState, runtime: Runtime[CopilotContext]) -> dict[str, Any]:
    """Search the reviewer's memories for what bears on their message, with a card
    of what it found, and keep it for the instructions. A memory that can't be
    reached refuses the card, and the turn goes on without it."""
    context, message = runtime.context, message_of(state)
    card = cards.start(context, SEARCH_MEMORY, {"query": message})
    store = cast(BaseStore, runtime.store)
    try:
        found = memory.recall(store, context.reviewer["reviewer_id"], message)
    except UNREACHABLE as error:
        cards.refused(context, card, MEMORY_UNREACHABLE.format(error=error))
        return {"remembered": []}
    cards.done(context, card, what_was_found(found))
    return {"remembered": found}


def remember(state: CopilotState, runtime: Runtime[CopilotContext]) -> None:
    """Save the reviewer's message and the turn's answer to the reviewer's memory,
    and nothing else. A memory that can't be reached is logged as a warning, and
    the turn is still answered."""
    context = runtime.context
    try:
        memory.remember(
            cast(BaseStore, runtime.store),
            context.reviewer["reviewer_id"],
            context.conversation_id,
            message_of(state),
            state["messages"][-1].text,
        )
    except UNREACHABLE as error:
        log.warning("The Copilot's memory wasn't saved: %s", describe(error))


def call_model(
    state: CopilotState,
    runtime: Runtime[CopilotContext],
    llm: Runnable[LanguageModelInput, BaseMessage],
) -> dict[str, Any]:
    """Ask the model for its next step, up to TURN_MODEL_CALLS times in a turn,
    with the instructions for this reviewer, built for each call and never saved,
    and keep the call's cost."""
    calls = state["model_calls"]
    if calls >= TURN_MODEL_CALLS:
        message = f"The Copilot made {calls} model calls without finishing"
        raise TooManyModelCalls(message)
    context = runtime.context
    system = SystemMessage(
        instructions_for(context.reviewer, context.business_date, state["remembered"])
    )
    reply = llm.invoke([system, *state["messages"]])
    return {"messages": [reply], "model_calls": 1, "cost": usage_of(reply).cost}


def after_agent(state: CopilotState) -> str:
    """Run the tools the model asks for, or end the turn with its answer."""
    reply = state["messages"][-1]
    return TOOLS if isinstance(reply, AIMessage) and reply.tool_calls else END


def refusal_answer(refusal: Exception) -> str:
    """A refusal as the model is told it."""
    if isinstance(refusal, app_api.Refused | GatewayRefused):
        return refusal.answer
    return REFUSED.format(reason=refusal)


def refusal_reason(refusal: Exception) -> str:
    """A refusal as its card gives it."""
    if isinstance(refusal, app_api.Refused):
        return str(refusal.detail)
    return str(refusal)


def signed_out(refusal: Exception) -> bool:
    """Say whether the app refused the reviewer's sign-in itself, as when it has
    run out, after which it refuses everything sent with it."""
    return (
        isinstance(refusal, app_api.Refused)
        and refusal.status_code == HTTPStatus.UNAUTHORIZED
    )


def with_card(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    """Run a tool with a card recorded as it starts and again when it ends. A
    refusal goes back to the model, its card keeping the bare reason, and any other
    error marks the card failed and stops the turn. A sign-in the app no longer
    accepts stops the turn at once: nothing more can be recorded with it, so the
    card stays working and the app shows the turn working until it reads as
    stopped. A tool the Copilot doesn't have is left to the ToolNode."""
    call = request.tool_call
    if call["name"] not in KINDS:
        return execute(request)
    context = cast(CopilotContext, request.runtime.context)
    card = cards.start(context, call["name"], call["args"])
    try:
        result = execute(request)
    except REFUSALS as refusal:
        if signed_out(refusal):
            raise
        cards.refused(context, card, refusal_reason(refusal))
        return ToolMessage(
            refusal_answer(refusal),
            tool_call_id=call["id"],
            name=call["name"],
            status="error",
        )
    except Exception as error:
        cards.failed(context, card, describe(error))
        raise
    # No Copilot tool answers with a Command, so every result is a message.
    message = cast(ToolMessage, result)
    cards.done(context, card, message.text, sources_of(message))
    return result


def sources_of(message: ToolMessage) -> Sources:
    """The files a context layer answer came from, in the step it gives as its
    artifact."""
    return message.artifact[2] if message.artifact else []


def copilot_graph(
    llm: BaseChatModel, saver: BaseCheckpointSaver[Any], store: BaseStore | None
) -> CopilotGraph:
    """Build the Copilot's graph on its model, which saves its state after every
    step with the saver given. With a memory, a turn starts by searching the
    reviewer's memories and ends by saving its message and answer."""
    remembers = store is not None
    answered = REMEMBER if remembers else END
    tools = ToolNode(COPILOT_TOOLS, handle_tool_errors=False, wrap_tool_call=with_card)
    bound = llm.bind_tools(COPILOT_TOOLS, parallel_tool_calls=False)
    builder = StateGraph(CopilotState, context_schema=CopilotContext)
    builder.add_node(BEGIN, begin)
    builder.add_node(AGENT, partial(call_model, llm=bound))
    builder.add_node(TOOLS, tools)
    builder.add_edge(START, BEGIN)
    if remembers:
        builder.add_node(RECALL, recall)
        builder.add_node(REMEMBER, remember)
        builder.add_edge(BEGIN, RECALL)
        builder.add_edge(RECALL, AGENT)
        builder.add_edge(REMEMBER, END)
    else:
        builder.add_edge(BEGIN, AGENT)
    builder.add_conditional_edges(AGENT, after_agent, {TOOLS: TOOLS, END: answered})
    builder.add_edge(TOOLS, AGENT)
    return builder.compile(checkpointer=saver, store=store)
