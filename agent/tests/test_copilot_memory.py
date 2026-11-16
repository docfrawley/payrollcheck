"""The Copilot's memory of each reviewer: searched as a turn starts, with a card of
what it found, which goes into the instructions, and the reviewer's message and the
answer saved as the turn ends, and nothing else."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from botocore.exceptions import EndpointConnectionError
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.store.base import BaseStore, Op, PutOp, Result, SearchItem, SearchOp

from agent import agentcore_memory
from agent.copilot.memory import MEMORY_ID, memory_store
from agent.tests.copilot_driver import Copilot
from agent.tests.stubs import call, stub
from backend.tests.case_requests import awaiting_review, finding
from backend.tests.sign_in import MARCUS

PREFERENCE = "Dana likes amounts first, in short bullet points"
QUESTION = "What needs me today?"
ANSWER = "- $0.32 short on PC-1201, awaiting your review"
ENDPOINT = "https://bedrock-agentcore.us-east-1.amazonaws.com"


@dataclass
class Event:
    """An event a put wrote: its actor, its session and its message."""

    actor: str
    session: str
    message: BaseMessage


@dataclass
class MemoryStandIn(BaseStore):
    """A stand-in for AgentCore Memory in place of AgentCoreMemoryStore: the
    memories AgentCore would have made, each a namespace and a text, the events
    written and the namespaces searched. It answers a search in
    AgentCoreMemoryStore's shape, every result's namespace the prefix searched, and
    one that can't be reached raises what botocore raises then."""

    memories: list[tuple[str, str]] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    searched: list[str] = field(default_factory=list)
    reachable: bool = True

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        if not self.reachable:
            raise EndpointConnectionError(endpoint_url=ENDPOINT)
        return [self.handle(op) for op in ops]

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        return self.batch(ops)

    def handle(self, op: Op) -> Result:
        if isinstance(op, PutOp):
            actor, session = op.namespace
            assert op.value is not None
            self.events.append(Event(actor, session, op.value["message"]))
            return None
        assert isinstance(op, SearchOp)
        path = "/" + "/".join(op.namespace_prefix)
        self.searched.append(path)
        now = datetime.now(UTC)
        found = [
            SearchItem(
                namespace=op.namespace_prefix,
                key=f"record-{n}",
                value={"content": text, "namespaces": [namespace]},
                created_at=now,
                updated_at=now,
            )
            for n, (namespace, text) in enumerate(self.memories)
            if namespace.startswith(f"{path}/")
        ]
        return found[: op.limit]


def remembering() -> MemoryStandIn:
    """A memory with one of Dana's preferences in it."""
    return MemoryStandIn(memories=[("/reviewers/HND-01/preferences/", PREFERENCE)])


def test_a_turn_starts_with_what_the_copilot_remembers(copilot: Copilot):
    copilot.store = remembering()
    copilot.model = stub(ANSWER)
    conversation = copilot.ask(QUESTION)
    [turn] = conversation["turns"]
    [card] = turn["steps"]
    assert (card["tool"], card["kind"], card["input"], card["status"]) == (
        "search_memory",
        "memory",
        QUESTION,
        "done",
    )
    assert card["answer"] == f"- {PREFERENCE}"
    [system, *_] = copilot.model.prompts[0]
    assert f"- {PREFERENCE}" in system.text
    assert copilot.store.searched == ["/reviewers/HND-01"]


def test_a_turn_saves_the_message_and_the_answer_and_nothing_else(
    client, copilot: Copilot
):
    awaiting_review(client, "PC-1201", finding())
    copilot.store = remembering()
    copilot.model = stub(call("get_case", case_id="PC-1201"), ANSWER)
    conversation_id = copilot.ask(QUESTION)["conversation_id"]
    message, answer = copilot.store.events
    assert (message.actor, message.session) == ("HND-01", conversation_id)
    assert (answer.actor, answer.session) == ("HND-01", conversation_id)
    assert isinstance(message.message, HumanMessage)
    assert isinstance(answer.message, AIMessage)
    assert (message.message.text, answer.message.text) == (QUESTION, ANSWER)
    sign_in = copilot.last_payload()["sign_in"]
    assert sign_in not in repr(copilot.store.events)


def test_each_reviewer_is_searched_alone(copilot: Copilot):
    copilot.store = remembering()
    copilot.model = stub("Hello, Marcus.")
    [turn] = copilot.ask("Hello", email=MARCUS)["turns"]
    assert copilot.store.searched == ["/reviewers/HND-02"]
    assert turn["steps"][0]["answer"] == "Nothing remembered that bears on this"
    assert PREFERENCE not in copilot.model.prompts[0][0].text
    assert [event.actor for event in copilot.store.events] == ["HND-02", "HND-02"]


def test_with_memory_off_nothing_is_searched_or_saved(copilot: Copilot):
    copilot.model = stub("Hello.")
    [turn] = copilot.ask("Hello")["turns"]
    assert turn["steps"] == []
    assert "Nothing yet." in copilot.model.prompts[0][0].text


def test_a_memory_that_cant_be_reached(copilot: Copilot, caplog):
    copilot.store = MemoryStandIn(reachable=False)
    copilot.model = stub("Hello.")
    [turn] = copilot.ask("Hello")["turns"]
    [card] = turn["steps"]
    assert (card["tool"], card["status"]) == ("search_memory", "refused")
    assert card["reason"].startswith("The memory can't be reached.")
    assert (turn["status"], turn["answer"]) == ("done", "Hello.")
    [warning] = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warning.getMessage().startswith(
        "The Copilot's memory wasn't saved: EndpointConnectionError"
    )


def test_the_memory_is_read_from_its_setting(monkeypatch):
    made = []

    def recorder(**settings):
        made.append(settings)
        return MemoryStandIn()

    monkeypatch.setattr(agentcore_memory, "AgentCoreMemoryStore", recorder)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
    assert memory_store() is None
    monkeypatch.setenv(MEMORY_ID, "payrollcheck_copilot_memory-abc")
    assert isinstance(memory_store(), MemoryStandIn)
    assert made == [
        {"memory_id": "payrollcheck_copilot_memory-abc", "region_name": "eu-west-2"}
    ]
