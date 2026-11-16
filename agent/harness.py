"""The harness: it builds the payroll agent's graph, with the screening for hidden
instructions first and the check tools after it, before the model, and works a
case with it."""

import logging
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from typing import Any, cast

from langchain.tools import ToolException
from langchain_core.exceptions import ModelRateLimitError, ModelTimeoutError
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command, RetryPolicy

from agent import api, app_terms, check_inputs, tool_route
from agent.app_operations import RECORD_CHECK_FINDINGS, RECORD_SCREENING_FLAG
from agent.checkpoints import Pool
from agent.checks import CHECKS
from agent.checks.findings import Parameters
from agent.connection import Refused
from agent.console import describe
from agent.json_text import as_json
from agent.openrouter import chat_model, usage_of
from agent.refusals import REFUSED
from agent.root_run import as_root_run
from agent.routes import GatewayRefused, Route, Target
from agent.screening import screen, text_cells
from agent.tools import PAYROLL_TOOLS, TARGETS, PayrollContext, PayrollState

log = logging.getLogger(__name__)

PayrollGraph = CompiledStateGraph[PayrollState, PayrollContext, Any, Any]
Messages = dict[str, list[BaseMessage]]
Start = Messages | None
# Tags for a case's trace beside its run's, such as the round it works in.
Tags = tuple[str, ...]

# The model's errors that pass with time: a case that hits one is left in progress,
# with its progress saved, to carry on later.
TRANSIENT = (ModelRateLimitError, ModelTimeoutError)

CASE_MODEL_CALLS = 30
NO_REPORT = "The agent finished without recording an exception report"
WORK_CASE = "Work case"
CARRY_ON = "Carry on"
SCREEN = "screen"
FLAG = "flag"
CHECK = "check"
AGENT = "agent"
TOOLS = "tools"
REFUSAL = "refusal"


# The screening's result as the case's first step.
FOUND = "Instructions found. {reason}"
NONE_FOUND = "No instructions found. {reason}"
# Who raises the payroll agent's exceptions: the version of its configuration.
AGENT_RAISES = "PayrollCheck Agent, version {number}"
# What the model is told the check tools found, which code writes.
CANDIDATES = "Their candidate findings:\n"
CHECKED = (
    "The check tools ran on the case's latest submission, in order: {checks}. "
    + CANDIDATES
    + "{candidates}"
)
NOTHING_FOUND = (
    "The check tools ran on the case's latest submission, in order: {checks}. "
    "They found nothing."
)


class TooManyModelCalls(Exception):
    """The payroll agent made as many model calls as it may without finishing."""


class UnreadableScreening(Exception):
    """The check for hidden instructions gave an answer that can't be read."""


# Tries the check three times in all when its answer can't be read, and for nothing
# else: a rate limit, a timeout or a refusal goes on like any error in the graph.
SCREEN_RETRY = RetryPolicy(max_attempts=3, retry_on=UnreadableScreening)


def model(named: dict[str, Any]) -> ChatOpenAI:
    """Return the model a version or get_screening names, at its reasoning effort."""
    return chat_model(named["model"], named["reasoning_effort"])


def refusal(error: Exception) -> str:
    """Show the model why a tool was refused, by the app, the Gateway or the tool's
    own checks, and let any other error stop the agent."""
    if isinstance(error, Refused):
        return f"Refused with status {error}"
    if isinstance(error, GatewayRefused):
        return error.answer
    if isinstance(error, ToolException):
        return REFUSED.format(reason=error)
    raise error


def named(context: PayrollContext, tool: str) -> str:
    """Name a call to one of the payroll agent's tools as its route names it, or as
    the model did for a tool the payroll agent doesn't have."""
    target = TARGETS.get(tool)
    return context.route.name(target, tool) if target else tool


def record_reply(context: PayrollContext, reply: BaseMessage) -> None:
    """Record the model's reply on the case: its text, then each tool it calls,
    named as the route names it."""
    if reply.text:
        api.record_step(context.case_id, "message", reply.text, [])
    if isinstance(reply, AIMessage):
        for call in reply.tool_calls:
            args = ", ".join(f"{k}={as_json(v)}" for k, v in call["args"].items())
            name = named(context, call["name"])
            api.record_step(context.case_id, "tool_call", f"{name}({args})", [])


def record_result(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    """Run a tool and record its result on the case, or its refusal, named as the
    route names the tool, then any step it gives as its artifact, such as what it
    looked up and the files that came from."""
    result = execute(request)
    if isinstance(result, ToolMessage):
        message = result
    else:
        message = cast(dict[str, Any], result.update)["messages"][0]
    context = cast(PayrollContext, request.runtime.context)
    kind = REFUSAL if message.status == "error" else "tool_result"
    name = named(context, request.tool_call["name"])
    api.record_step(context.case_id, kind, f"{name}: {message.text}", [])
    if message.artifact:
        api.record_step(context.case_id, *message.artifact)
    return result


def record_call(context: PayrollContext, reply: BaseMessage) -> None:
    """Record the tokens and the cost of one model call, as OpenRouter reports them."""
    api.record_model_call(context.case_id, context.run_id, *usage_of(reply))


def screen_case(
    state: PayrollState, runtime: Runtime[PayrollContext], screener: BaseChatModel
) -> dict[str, Any]:
    """Have the screening read every text cell of the case's latest submission,
    before the payroll agent's model sees it, and record its call and its result as
    the case's first step. Raise UnreadableScreening, after recording the call,
    when its answer can't be read."""
    context = runtime.context
    reply, screening = screen(screener, text_cells(api.get_case(context.case_id)))
    record_call(context, reply)
    if screening is None:
        raise UnreadableScreening("The security check's answer couldn't be read")
    line = FOUND if screening.instructions_found else NONE_FOUND
    checked = line.format(reason=screening.reason)
    api.record_step(context.case_id, "screening", checked, [])
    return {"screening": screening.model_dump()}


def flag(state: PayrollState, runtime: Runtime[PayrollContext]) -> dict[str, Any]:
    """Flag a case the screening found an instruction in, for a reviewer to work by
    hand, with the screening's reason."""
    context = runtime.context
    reason = {"case_id": context.case_id, "reason": state["screening"]["reason"]}
    case = context.route.call(Target.APP, RECORD_SCREENING_FLAG, reason)
    return {"status": case["status"]}


def check_case(state: PayrollState, runtime: Runtime[PayrollContext]) -> dict[str, Any]:
    """Run the eight check tools in order on the case's latest submission, record
    each one's findings with the app, which keeps them as the attempt's candidates,
    and tell the model what they found."""
    context = runtime.context
    inputs = check_inputs.fetch_inputs(context.route, context.case_id)
    parameters = Parameters.read(context.parameters)
    candidates = []
    for name, check in CHECKS:
        findings = [found.record() for found in check(inputs, parameters)]
        candidates += context.route.call(
            Target.APP,
            RECORD_CHECK_FINDINGS,
            {"case_id": context.case_id, "check": name, "findings": findings},
        )
    checks = ", ".join(name for name, _ in CHECKS)
    told = (
        CHECKED.format(checks=checks, candidates=as_json(candidates))
        if candidates
        else NOTHING_FOUND.format(checks=checks)
    )
    return {"messages": [HumanMessage(told)]}


def call_model(
    state: PayrollState,
    runtime: Runtime[PayrollContext],
    llm: Runnable[LanguageModelInput, BaseMessage],
    instructions: SystemMessage,
) -> dict[str, Any]:
    """Ask the model for its next step, up to CASE_MODEL_CALLS times in all, and
    record its cost and its reply on the case."""
    calls = state["model_calls"]
    if calls >= CASE_MODEL_CALLS:
        message = f"The payroll agent made {calls} model calls without finishing"
        raise TooManyModelCalls(message)
    reply = llm.invoke([instructions, *state["messages"]])
    record_call(runtime.context, reply)
    record_reply(runtime.context, reply)
    return {"messages": [reply], "model_calls": 1}


def after_screen(state: PayrollState) -> str:
    """Flag a case the screening found an instruction in, or check it."""
    return FLAG if state["screening"]["instructions_found"] else CHECK


def after_agent(state: PayrollState) -> str:
    """Run the tools the model asked for, or stop: it finished without a report."""
    reply = state["messages"][-1]
    return TOOLS if isinstance(reply, AIMessage) and reply.tool_calls else END


def after_tools(state: PayrollState) -> str:
    """Go back to the model until its report is recorded, which ends its work."""
    return END if state["status"] else AGENT


def payroll_graph(
    llm: BaseChatModel,
    screener: BaseChatModel,
    saver: BaseCheckpointSaver[Any],
    instructions: str,
) -> PayrollGraph:
    """Build the payroll agent's graph, which saves its progress after every step:
    the screening on its own model, then the check tools, then the payroll agent
    on its model, with its instructions, until it records its report."""
    builder = StateGraph(PayrollState, context_schema=PayrollContext)
    builder.add_node(
        SCREEN, partial(screen_case, screener=screener), retry_policy=SCREEN_RETRY
    )
    builder.add_node(FLAG, flag)
    builder.add_node(CHECK, check_case)
    builder.add_node(
        AGENT,
        partial(
            call_model,
            llm=llm.bind_tools(PAYROLL_TOOLS),
            instructions=SystemMessage(instructions),
        ),
    )
    builder.add_node(
        TOOLS,
        ToolNode(
            PAYROLL_TOOLS, handle_tool_errors=refusal, wrap_tool_call=record_result
        ),
    )
    builder.add_edge(START, SCREEN)
    builder.add_conditional_edges(SCREEN, after_screen, [FLAG, CHECK])
    builder.add_edge(FLAG, END)
    builder.add_edge(CHECK, AGENT)
    builder.add_conditional_edges(AGENT, after_agent, [TOOLS, END])
    builder.add_conditional_edges(TOOLS, after_tools, [AGENT, END])
    return builder.compile(checkpointer=saver)


@dataclass
class PayrollAgent:
    """A payroll graph with a saver of its own, and what its cases' contexts need:
    the route its tools take, who its exceptions are raised by and its version's
    parameters for the check tools."""

    graph: PayrollGraph
    route: Route
    raised_by: str
    parameters: dict[str, Any]


NewAgent = Callable[[], PayrollAgent]


def maker_of(version: dict[str, Any]) -> str:
    """Say who raises the exceptions of a version of the payroll agent."""
    return AGENT_RAISES.format(number=version["number"])


def payroll_graphs(version: dict[str, Any], pool: Pool) -> NewAgent:
    """Return how to build a version's payroll agent: a payroll graph with a saver
    of its own on the pool, since a saver lets one case at a time read or write, on
    the route read when the run's agents are built. The screening runs on the
    model the backend names for it."""
    llm, screener = model(version), model(api.get_screening())
    route = tool_route.from_environment()
    raised_by = maker_of(version)

    def new_agent() -> PayrollAgent:
        graph = payroll_graph(
            llm, screener, PostgresSaver(pool), version["instructions"]
        )
        return PayrollAgent(graph, route, raised_by, version["parameters"])

    return new_agent


def thread_of(case: dict[str, Any]) -> RunnableConfig:
    """Address the case's thread, where the payroll graph saves its progress."""
    return {"configurable": {"thread_id": case["thread_id"]}}


def case_config(
    case: dict[str, Any], name: str, run_id: str | None, tags: Tags
) -> RunnableConfig:
    """Run on the case's thread, traced in Langfuse in the session of that thread
    and tagged with the run, if any, and any other tags, such as its round."""
    session = f"{case['case_id']}:{case['thread_id']}"
    metadata: dict[str, Any] = {
        "langfuse_session_id": session,
        "langfuse_trace_name": name,
    }
    if run_id is not None:
        metadata["langfuse_tags"] = [run_id, *tags]
    return thread_of(case) | {
        "callbacks": [CallbackHandler()],
        "metadata": metadata,
        # One tool call at a time, so two reports in one reply can't race.
        "max_concurrency": 1,
    }


def context_of(
    case: dict[str, Any], run_id: str | None, agent: PayrollAgent
) -> PayrollContext:
    """What the payroll agent knows of the case it works on, in the run given if
    any."""
    return PayrollContext(
        case["case_id"],
        run_id,
        case["project_id"],
        case["subcontractor_id"],
        agent.route,
        agent.raised_by,
        agent.parameters,
    )


def begin(case_id: str) -> Messages:
    """Give a payroll agent its first message, naming the case it works on."""
    return {"messages": [HumanMessage(f"Case {case_id}")]}


def report(case: dict[str, Any], reason: str) -> str:
    """Say in one line how a case ended: its exceptions and shortfall, clean,
    flagged by the screening, or why it failed."""
    case_id, status = case["case_id"], case["status"]
    if status == app_terms.Status.RECEIVED:
        return f"{case_id}  failed: {reason}, back in the queue"
    if case["agent_failed"]:
        return f"{case_id}  failed: {reason}, left for a reviewer"
    if case["screening_flag"]:
        return f"{case_id}  flagged by the screening"
    if not case["open_exceptions"]:
        return f"{case_id}  clean, awaiting review"
    count, short = case["open_exceptions"], case["shortfall_cents"] / 100
    exceptions = "exception" if count == 1 else "exceptions"
    return f"{case_id}  {count} {exceptions}, ${short:,.2f} short, awaiting review"


def run_payroll_graph(
    graph: PayrollGraph, start: Start, config: RunnableConfig, context: PayrollContext
) -> str | None:
    """Run the payroll graph on the case's thread, saving each step, and say what went
    wrong, if anything. A rate limit or a timeout is raised again, leaving the case
    in progress with its progress saved, to carry on later."""
    try:
        as_root_run(graph.invoke, start, config, context=context, durability="sync")
    except TRANSIENT:
        raise
    except Exception as error:  # a case that fails must not stop the run
        return describe(error)
    return None


@contextmanager
def spell(case_id: str, run_id: str | None) -> Iterator[None]:
    """Time one spell of work on a case, and record it however it ends."""
    started = time.monotonic()
    try:
        yield
    finally:
        api.record_work_time(case_id, run_id, time.monotonic() - started)


def settle(case_id: str, error: str | None) -> str:
    """Fail a case the agent left in progress, and report how the case ended. An
    error after the report is logged, and the case keeps its report."""
    case = api.get_case(case_id)
    reason = error or NO_REPORT
    if case["status"] == app_terms.Status.IN_PROGRESS:
        case = api.fail_case(case_id, reason)
    elif error:
        log.warning("%s  %s", case_id, error)
    line = report(case, reason)
    log.info(line)
    return line


def work_on(
    case: dict[str, Any],
    start: Start,
    config: RunnableConfig,
    run_id: str | None,
    agent: PayrollAgent,
) -> str:
    """Run the payroll graph on the case's thread from a start, in the run given if
    any, timed as one spell of work, then settle the case and report how it
    ended."""
    case_id = case["case_id"]
    context = context_of(case, run_id, agent)
    with spell(case_id, run_id):
        error = run_payroll_graph(agent.graph, start, config, context)
        return settle(case_id, error)


def work_case(
    case_id: str, run_id: str | None, agent: PayrollAgent, tags: Tags = ()
) -> str:
    """Work one case from a clean start, as a new attempt, in the run given if any,
    and report how it ended."""
    case = api.start_case(case_id, str(uuid.uuid4()))
    config = case_config(case, WORK_CASE, run_id, tags)
    return work_on(case, begin(case_id), config, run_id, agent)


def carry_on(
    case_id: str, run_id: str | None, agent: PayrollAgent, tags: Tags = ()
) -> str:
    """Carry a case in progress on from its saved progress, as the same attempt, and
    report how it ended. One with nothing saved, stopped before its first step,
    starts on its own thread; any other carries on, finishing a step whose writes
    were saved."""
    case = api.get_case(case_id)
    saved = agent.graph.get_state(thread_of(case))
    start: Start = begin(case_id) if saved.created_at is None else None
    config = case_config(case, CARRY_ON, run_id, tags)
    return work_on(case, start, config, run_id, agent)


def work_in_run(case_id: str, run_id: str, new_agent: NewAgent, tags: Tags = ()) -> str:
    """Work one case in a run with a payroll agent of its own, carrying it on if it
    is in progress, as one a stopped run left is, or starting it if it is Received,
    and report how it ended, with any tags for its trace beside the run's."""
    agent = new_agent()
    if api.get_case(case_id)["status"] == app_terms.Status.IN_PROGRESS:
        return carry_on(case_id, run_id, agent, tags)
    return work_case(case_id, run_id, agent, tags)
