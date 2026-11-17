"""Holding a case for a reviewer's work, which the case page's operations and the
Copilot's draft of a notice share: a case's move from one status to another with a
conditional update, the statuses each kind of work needs with their refusals, and
the row lock a review takes while it works, so two pieces of work on one case
never interleave."""

from typing import Any, NamedTuple

from fastapi import HTTPException
from sqlalchemy import Connection, RowMapping, update

from backend.database import cases
from backend.lookups import find_case
from backend.models import Status
from backend.scope import Scope

A_COPY = "Case {case_id} is a copy in an evaluation and can't be {answered}"


class Review(NamedTuple):
    """The statuses a kind of a reviewer's work needs, and the refusal of a case
    in another."""

    statuses: tuple[Status, ...]
    refusal: str


AWAITING = Review((Status.AWAITING_REVIEW,), "Case {case_id} is not awaiting review")
RETURNED = Review(
    (Status.RETURNED_TO_SUB,), "Case {case_id} is not returned to its subcontractor"
)
NOTICED = Review(
    (Status.AWAITING_REVIEW, Status.RETURNED_TO_SUB),
    "Case {case_id}'s notice is written while it awaits review or is returned to "
    "its subcontractor",
)


def move_case(
    db: Connection, case_id: str, old: Status, new: Status, **columns: Any
) -> bool:
    """Move a case from one status to another, setting any other columns given, and
    say whether it moved: only the first of two requests at the same moment finds
    it in the old status."""
    moved = db.execute(
        update(cases)
        .where(cases.c.case_id == case_id, cases.c.status == old)
        .values(status=new, **columns)
    )
    return moved.rowcount == 1


def in_review(
    db: Connection, case_id: str, scope: Scope, answered: str, review: Review
) -> RowMapping:
    """A case a reviewer can work in one of the review's statuses: its row, or
    raise a 404, or a 409 for an evaluation's copy, which nobody answers, or a case
    in another status."""
    case = find_case(db, case_id, scope)
    if case["evaluation_id"] is not None:
        raise HTTPException(409, A_COPY.format(case_id=case_id, answered=answered))
    if case["status"] not in review.statuses:
        raise HTTPException(409, review.refusal.format(case_id=case_id))
    return case


def hold_for_review(db: Connection, case: RowMapping, review: Review) -> None:
    """Hold a case in the status it was read in while a reviewer overrides its
    exceptions or writes or sends its notice, by taking its row's lock with a
    conditional update, or raise a 409. A sign-off takes the same lock first, so
    the two never interleave: whichever comes second finds what the first did."""
    status = case["status"]
    if not move_case(db, case["case_id"], status, status):
        raise HTTPException(409, review.refusal.format(case_id=case["case_id"]))
