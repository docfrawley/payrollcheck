"""Overrides: a reviewer's corrections of a case's exception report, each a row of its
own with who, when and why, never edited or deleted. A reviewer dismisses an open
exception of the latest submission, restores one they dismissed, or adds one the
agent missed. Overrides never touch the labels the agent is scored against. The
override log reads by case, and by date for the improver."""

from typing import NamedTuple

from fastapi import HTTPException
from sqlalchemy import (
    Connection,
    RowMapping,
    Select,
    func,
    insert,
    select,
    update,
)

from backend.database import exceptions, now, overrides, reviewers, submissions
from backend.models import (
    CorrectedException,
    ExceptionSource,
    ExceptionStatus,
    NewException,
    Override,
    OverrideKind,
    Reviewer,
)
from backend.rule_codes import RULES
from backend.scope import Scope

EXCEPTION_NOT_FOUND = (
    "Exception {exception_id} not found on {case_id}'s latest submission"
)
NOT_OPEN = "Exception {exception_id} isn't open, so it can't be dismissed"
NOT_DISMISSED = "Exception {exception_id} isn't dismissed, so it can't be restored"
NEEDS_A_WORKER = "{rule} is found on a worker's line: give the worker and the line"
NOT_THEIR_LINE = "Line {line_no} of the latest submission isn't {worker_id}'s"
NO_WORKER = "{rule} is about the whole payroll: give no worker or line"
NEEDS_A_SHORTFALL = "{rule} carries money: give a shortfall above $0.00"
NO_SHORTFALL = "{rule} carries no money: give no shortfall"


class Overriding(NamedTuple):
    """Who is overriding the exceptions of which case, in their scope."""

    case: RowMapping
    reviewer: Reviewer
    scope: Scope


# What each override of an existing exception moves it from and to, and the
# refusal when it isn't there to move.
MOVES = {
    OverrideKind.DISMISSED: (ExceptionStatus.OPEN, ExceptionStatus.DISMISSED, NOT_OPEN),
    OverrideKind.RESTORED: (
        ExceptionStatus.DISMISSED,
        ExceptionStatus.OPEN,
        NOT_DISMISSED,
    ),
}


def log(
    db: Connection, by: Overriding, exception_id: int, kind: OverrideKind, reason: str
) -> None:
    """Log an override of an exception on the latest submission: who, when and why."""
    db.execute(
        insert(overrides).values(
            exception_id=exception_id,
            case_id=by.case["case_id"],
            submission_no=by.case["latest_submission_no"],
            kind=kind,
            reviewer_id=by.reviewer.reviewer_id,
            reason=reason,
            created_at=now(),
        )
    )


def move(
    db: Connection,
    by: Overriding,
    exception_id: int,
    kind: OverrideKind,
    reason: str,
) -> None:
    """Dismiss an open exception of the latest submission, or restore a dismissed
    one, for the first of two requests at the same moment, and log it, or raise a
    404 or a 409."""
    old, new, refusal = MOVES[kind]
    case = by.case
    on_latest = (
        exceptions.c.exception_id == exception_id,
        exceptions.c.case_id == case["case_id"],
        exceptions.c.submission_no == case["latest_submission_no"],
    )
    moved = db.execute(
        update(exceptions)
        .where(*on_latest, exceptions.c.status == old)
        .values(status=new)
    )
    if moved.rowcount == 1:
        log(db, by, exception_id, kind, reason)
        return
    if db.execute(select(exceptions.c.exception_id).where(*on_latest)).first():
        raise HTTPException(409, refusal.format(exception_id=exception_id))
    message = EXCEPTION_NOT_FOUND.format(
        exception_id=exception_id, case_id=case["case_id"]
    )
    raise HTTPException(404, message)


def dismiss(db: Connection, by: Overriding, exception_id: int, reason: str) -> None:
    """Dismiss an open exception of the latest submission."""
    move(db, by, exception_id, OverrideKind.DISMISSED, reason)


def restore(db: Connection, by: Overriding, exception_id: int, reason: str) -> None:
    """Reopen a dismissed exception of the latest submission."""
    move(db, by, exception_id, OverrideKind.RESTORED, reason)


def refuse_where_it_cant_be(
    db: Connection, case: RowMapping, request: NewException
) -> None:
    """A 422 for an exception whose worker and line don't fit its rule or the
    latest submission: a worker's rule needs the worker on that line, and a rule
    about the whole payroll takes neither."""
    rule = request.rule
    if not RULES[rule].worker:
        if request.worker_id is not None or request.line_no is not None:
            raise HTTPException(422, NO_WORKER.format(rule=rule))
        return
    if request.worker_id is None or request.line_no is None:
        raise HTTPException(422, NEEDS_A_WORKER.format(rule=rule))
    lines = db.execute(
        select(submissions.c.lines).where(
            submissions.c.case_id == case["case_id"],
            submissions.c.submission_no == case["latest_submission_no"],
        )
    ).scalar_one()
    if not (
        1 <= request.line_no <= len(lines)
        and lines[request.line_no - 1]["worker_id"] == request.worker_id
    ):
        message = NOT_THEIR_LINE.format(
            line_no=request.line_no, worker_id=request.worker_id
        )
        raise HTTPException(422, message)


def refuse_the_wrong_shortfall(request: NewException) -> None:
    """A 422 for a rule that carries money without a shortfall above zero, or one
    that carries none with a shortfall."""
    rule = request.rule
    shortfall = request.shortfall_cents
    if RULES[rule].money and (shortfall is None or shortfall <= 0):
        raise HTTPException(422, NEEDS_A_SHORTFALL.format(rule=rule))
    if not RULES[rule].money and shortfall is not None:
        raise HTTPException(422, NO_SHORTFALL.format(rule=rule))


def add(db: Connection, by: Overriding, request: NewException) -> None:
    """Add an open exception to the latest submission, raised by the reviewer with
    its severity and citation from the catalogue, and log it."""
    case = by.case
    refuse_where_it_cant_be(db, case, request)
    refuse_the_wrong_shortfall(request)
    rule = RULES[request.rule]
    added = db.execute(
        insert(exceptions)
        .values(
            case_id=case["case_id"],
            submission_no=case["latest_submission_no"],
            **request.model_dump(exclude={"reason"}),
            severity=rule.severity,
            citation=rule.cites,
            raised_by=by.reviewer.name,
            source=ExceptionSource.REVIEWER,
            status=ExceptionStatus.OPEN,
        )
        .returning(exceptions.c.exception_id)
    ).scalar_one()
    log(db, by, added, OverrideKind.ADDED, request.reason)


def the_log() -> Select:
    """The override log, each with its reviewer's name, oldest first."""
    return (
        select(overrides, reviewers.c.name.label("reviewer_name"))
        .join(reviewers, reviewers.c.reviewer_id == overrides.c.reviewer_id)
        .order_by(overrides.c.override_id)
    )


def overrides_of(db: Connection, case_id: str) -> list[Override]:
    """A case's overrides, oldest first."""
    query = the_log().where(overrides.c.case_id == case_id)
    return [Override(**row) for row in db.execute(query).mappings()]


def overrides_between(
    db: Connection, start: str, end: str, most: int
) -> tuple[int, list[CorrectedException]]:
    """How many overrides were made from one moment up to another, and the newest
    of them, each with its case and the exception it corrected, for the improver
    to read the reviewers' corrections since its last round."""
    window = overrides.c.created_at >= start, overrides.c.created_at < end
    total = db.execute(select(func.count()).where(*window)).scalar_one()
    query = (
        the_log()
        .add_columns(
            exceptions.c.rule,
            exceptions.c.worker_id,
            exceptions.c.line_no,
            exceptions.c.expected,
            exceptions.c.actual,
            exceptions.c.shortfall_cents,
            exceptions.c.source,
        )
        .join(exceptions, exceptions.c.exception_id == overrides.c.exception_id)
        .where(*window)
        .order_by(None)
        .order_by(overrides.c.override_id.desc())
        .limit(most)
    )
    return total, [CorrectedException(**row) for row in db.execute(query).mappings()]
