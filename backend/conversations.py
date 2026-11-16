"""The Copilot's records in the app: each reviewer's conversations, their turns and
each turn's cards. A conversation is found only for its own reviewer and takes one
message at a time. A turn that has worked too long reads as stopped and stays
stopped, refusing a late record."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Connection, RowMapping, insert, select, update

from backend.database import (
    conversations,
    copilot_steps,
    copilot_turns,
    now_precisely,
)
from backend.models import (
    CardStatus,
    Conversation,
    ConversationSummary,
    CopilotStep,
    CopilotStepRequest,
    CopilotStepResult,
    CopilotTurn,
    Reviewer,
    TurnFinishRequest,
    TurnStatus,
)

TITLE_LENGTH = 120
# A turn still working this long after it started reads as stopped.
STOPPED_AFTER = timedelta(minutes=20)
CONVERSATION_NOT_FOUND = "Conversation {conversation_id} not found"
TURN_NOT_FOUND = "Turn {turn_id} not found"
STEP_NOT_FOUND = "Step {step_id} not found"
STILL_WORKING = "The Copilot is still working on your last message"
NOT_WORKING = "Turn {number} isn't working"
STEP_FINISHED = "Step {step_id} has finished"


def new_conversation_id() -> str:
    """A conversation's id, which works as a Runtime session's id and as the
    memory's session: conversation- and a UUID, 49 letters, digits and hyphens."""
    return f"conversation-{uuid.uuid4()}"


def seconds_from(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def status_of(turn: RowMapping) -> TurnStatus:
    """Where a turn stands: stopped when it is still working STOPPED_AFTER its
    start, and otherwise as recorded."""
    if turn["status"] == TurnStatus.WORKING:
        since = datetime.now(UTC) - datetime.fromisoformat(turn["started_at"])
        if since > STOPPED_AFTER:
            return TurnStatus.STOPPED
    return TurnStatus(turn["status"])


def seconds_of(turn: RowMapping) -> float | None:
    """How long a turn that has finished took."""
    if turn["finished_at"] is None:
        return None
    return seconds_from(turn["started_at"], turn["finished_at"])


def to_step(row: RowMapping) -> CopilotStep:
    """A card, with its seconds so far while it works."""
    end = row["finished_at"] or now_precisely()
    return CopilotStep(**row, seconds=seconds_from(row["started_at"], end))


def to_turn(row: RowMapping, steps: list[CopilotStep]) -> CopilotTurn:
    """A turn with its cards, as it stands."""
    return CopilotTurn(
        **dict(row)
        | {"status": status_of(row), "seconds": seconds_of(row), "steps": steps}
    )


def steps_by_turn(db: Connection, turn_ids: list[str]) -> dict[str, list[CopilotStep]]:
    """The cards of the turns given, in order, by turn, in one query."""
    query = (
        select(copilot_steps)
        .where(copilot_steps.c.turn_id.in_(turn_ids))
        .order_by(copilot_steps.c.step_id)
    )
    cards: dict[str, list[CopilotStep]] = {turn_id: [] for turn_id in turn_ids}
    for row in db.execute(query).mappings():
        cards[row["turn_id"]].append(to_step(row))
    return cards


def owned(db: Connection, conversation_id: str, reviewer: Reviewer) -> RowMapping:
    """Return one of the reviewer's own conversations, or raise a 404, as for a
    conversation that isn't there."""
    query = select(conversations).where(
        conversations.c.conversation_id == conversation_id,
        conversations.c.reviewer_id == reviewer.reviewer_id,
    )
    row = db.execute(query).mappings().first()
    if row is None:
        message = CONVERSATION_NOT_FOUND.format(conversation_id=conversation_id)
        raise HTTPException(404, message)
    return row


def conversation(
    db: Connection, conversation_id: str, reviewer: Reviewer
) -> Conversation:
    """One of the reviewer's conversations, with every turn and its cards."""
    row = owned(db, conversation_id, reviewer)
    query = (
        select(copilot_turns)
        .where(copilot_turns.c.conversation_id == conversation_id)
        .order_by(copilot_turns.c.number)
    )
    turns = list(db.execute(query).mappings())
    cards = steps_by_turn(db, [turn["turn_id"] for turn in turns])
    return Conversation(
        conversation_id=conversation_id,
        title=row["title"],
        created_at=row["created_at"],
        turns=[to_turn(turn, cards[turn["turn_id"]]) for turn in turns],
    )


def conversations_of(db: Connection, reviewer: Reviewer) -> list[ConversationSummary]:
    """The reviewer's conversations, newest first."""
    query = (
        select(conversations)
        .where(conversations.c.reviewer_id == reviewer.reviewer_id)
        .order_by(conversations.c.created_at.desc(), conversations.c.conversation_id)
    )
    return [ConversationSummary(**row) for row in db.execute(query).mappings()]


def add_turn(db: Connection, conversation_id: str, number: int, message: str) -> str:
    """Record a conversation's turn, working on its message from now, and return
    its id."""
    turn_id = str(uuid.uuid4())
    db.execute(
        insert(copilot_turns).values(
            turn_id=turn_id,
            conversation_id=conversation_id,
            number=number,
            message=message,
            status=TurnStatus.WORKING,
            started_at=now_precisely(),
        )
    )
    return turn_id


def start(db: Connection, reviewer: Reviewer, message: str) -> tuple[str, str]:
    """Start a conversation for the reviewer, titled with its first message, with
    that message as its first turn, and return their ids."""
    conversation_id = new_conversation_id()
    db.execute(
        insert(conversations).values(
            conversation_id=conversation_id,
            reviewer_id=reviewer.reviewer_id,
            title=message[:TITLE_LENGTH],
            turns=1,
            created_at=now_precisely(),
        )
    )
    return conversation_id, add_turn(db, conversation_id, 1, message)


def latest_turn(db: Connection, row: RowMapping) -> RowMapping:
    """A conversation's latest turn."""
    query = select(copilot_turns).where(
        copilot_turns.c.conversation_id == row["conversation_id"],
        copilot_turns.c.number == row["turns"],
    )
    return db.execute(query).mappings().one()


def refuse_while_busy(turn: RowMapping) -> None:
    """Raise a 409 while a turn is still working and hasn't stopped."""
    if status_of(turn) == TurnStatus.WORKING:
        raise HTTPException(409, STILL_WORKING)


def next_turn(
    db: Connection, conversation_id: str, reviewer: Reviewer, message: str
) -> str:
    """Add a turn to one of the reviewer's conversations, and return its id."""
    return add_after(db, owned(db, conversation_id, reviewer), message)


def add_after(db: Connection, row: RowMapping, message: str) -> str:
    """Add a turn after a conversation's latest, as the row read it, once that turn
    is done, failed or stopped, and return its id. The conversation's count of
    turns moves on with a conditional update, so of two messages at once one is
    refused."""
    refuse_while_busy(latest_turn(db, row))
    number = row["turns"] + 1
    moved = db.execute(
        update(conversations)
        .where(
            conversations.c.conversation_id == row["conversation_id"],
            conversations.c.turns == row["turns"],
        )
        .values(turns=number)
    )
    if moved.rowcount != 1:
        raise HTTPException(409, STILL_WORKING)
    return add_turn(db, row["conversation_id"], number, message)


def fail_untaken(db: Connection, turn_id: str, reason: str) -> None:
    """Fail a turn the Copilot didn't take, with why."""
    db.execute(
        update(copilot_turns)
        .where(
            copilot_turns.c.turn_id == turn_id,
            copilot_turns.c.status == TurnStatus.WORKING,
        )
        .values(status=TurnStatus.FAILED, failure=reason, finished_at=now_precisely())
    )


# The Copilot's own records of a turn.


def turn_of(db: Connection, turn_id: str, reviewer: Reviewer) -> RowMapping:
    """Return a turn of one of the reviewer's own conversations, with how many turns
    its conversation has, or raise a 404."""
    query = (
        select(copilot_turns, conversations.c.turns)
        .join(conversations)
        .where(
            copilot_turns.c.turn_id == turn_id,
            conversations.c.reviewer_id == reviewer.reviewer_id,
        )
    )
    row = db.execute(query).mappings().first()
    if row is None:
        raise HTTPException(404, TURN_NOT_FOUND.format(turn_id=turn_id))
    return row


def working_turn(db: Connection, turn_id: str, reviewer: Reviewer) -> RowMapping:
    """Return the reviewer's turn when it is its conversation's latest and still
    working, by the rule status_of reads it by, or raise a 404 or a 409. A stopped
    turn stays stopped."""
    turn = turn_of(db, turn_id, reviewer)
    if turn["number"] != turn["turns"] or status_of(turn) != TurnStatus.WORKING:
        raise HTTPException(409, NOT_WORKING.format(number=turn["number"]))
    return turn


def move(db: Connection, turn: RowMapping, **values: Any) -> None:
    """Move a working turn on with the values given, or raise a 409 when another
    record moved it first."""
    moved = db.execute(
        update(copilot_turns)
        .where(
            copilot_turns.c.turn_id == turn["turn_id"],
            copilot_turns.c.status == TurnStatus.WORKING,
        )
        .values(**values)
    )
    if moved.rowcount != 1:
        raise HTTPException(409, NOT_WORKING.format(number=turn["number"]))


def turn_view(db: Connection, turn_id: str) -> CopilotTurn:
    """A turn as it stands, with its cards."""
    row = db.execute(
        select(copilot_turns).where(copilot_turns.c.turn_id == turn_id)
    ).mappings()
    return to_turn(row.one(), steps_by_turn(db, [turn_id])[turn_id])


def step_view(db: Connection, step_id: int) -> CopilotStep:
    query = select(copilot_steps).where(copilot_steps.c.step_id == step_id)
    return to_step(db.execute(query).mappings().one())


def add_step(db: Connection, turn: RowMapping, request: CopilotStepRequest) -> int:
    """Record a card for a tool the Copilot starts, working, and return its id."""
    query = (
        insert(copilot_steps)
        .values(
            turn_id=turn["turn_id"],
            **request.model_dump(),
            status=CardStatus.WORKING,
            sources=[],
            started_at=now_precisely(),
        )
        .returning(copilot_steps.c.step_id)
    )
    return db.execute(query).scalar_one()


def finish_step(
    db: Connection, turn: RowMapping, step_id: int, request: CopilotStepResult
) -> None:
    """Finish a working card of a turn with what came back, or raise a 404 for a
    card of another turn or a 409 for one that has finished."""
    query = select(copilot_steps.c.status).where(
        copilot_steps.c.step_id == step_id,
        copilot_steps.c.turn_id == turn["turn_id"],
    )
    if db.execute(query).scalar_one_or_none() is None:
        raise HTTPException(404, STEP_NOT_FOUND.format(step_id=step_id))
    finished = db.execute(
        update(copilot_steps)
        .where(
            copilot_steps.c.step_id == step_id,
            copilot_steps.c.status == CardStatus.WORKING,
        )
        .values(**request.model_dump(mode="json"), finished_at=now_precisely())
    )
    if finished.rowcount != 1:
        raise HTTPException(409, STEP_FINISHED.format(step_id=step_id))


def finish(db: Connection, turn: RowMapping, request: TurnFinishRequest) -> None:
    """Record a working turn's answer, with its model calls and their cost."""
    move(
        db,
        turn,
        status=TurnStatus.DONE,
        **request.model_dump(),
        finished_at=now_precisely(),
    )


def fail(db: Connection, turn: RowMapping, reason: str) -> None:
    """Record that a working turn failed, with why."""
    move(
        db, turn, status=TurnStatus.FAILED, failure=reason, finished_at=now_precisely()
    )
