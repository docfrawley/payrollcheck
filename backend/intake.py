"""Intake: an uploaded CSV turned into a submission by the template's strict reader,
with no model, or refused with its reason and no case created. Only a file that
can't become a submission is refused; anything else it says is accepted, however
wrong, for the payroll agent to find. The first upload for a subcontractor,
project and week creates its case, Received, and any later one is a correction:
the case's next submission, which reopens it."""

import re
from datetime import date

from fastapi import HTTPException
from sqlalchemy import Connection, RowMapping, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from backend.business_date import business_date
from backend.database import (
    cases,
    engagements,
    exceptions,
    now,
    projects,
    submissions,
)
from backend.models import ExceptionStatus, Reviewer, Status, UploadRequest
from data.payroll_world.template import Payroll, Unreadable, payroll_record, read_upload

CSV = ".csv"
NOT_CSV = "{file_name} isn't a CSV file: upload the payroll in our CSV template"
WRONG_PROJECT = "This payroll is for {theirs}, not {ours}."
NOT_ON_PROJECT = "{subcontractor_id} isn't a subcontractor on {project_id}"
NOT_A_WEEK = "The week ending {week_ending} isn't a week of our projects"
ALREADY = (
    "Case {case_id} already holds {subcontractor_id}'s payroll on {project_id} for "
    "the week ending {week_ending}"
)
BEING_CHECKED = (
    "{case_id} is being checked: upload the correction once it's awaiting review"
)
UPLOADED_MEANWHILE = (
    "{case_id} took another upload a moment ago: reload it, then upload again"
)
# A new or reopened case, as the next dispatch finds it: Received, never started,
# with nothing flagged and no review.
FRESH = {
    "status": Status.RECEIVED,
    "thread_id": None,
    "attempts": 0,
    "agent_failed": False,
    "screening_flag": False,
    "screening_reason": None,
    "reviewed_by": None,
    "reviewed_on": None,
}
CASE_ID = "PC-{week:02d}{pair:02d}"
# Any case id the template makes, as it reads in text.
ANY_CASE_ID = re.compile(r"PC-\d{4}")
# A case's id holds its week in two digits.
MOST_WEEKS = 99


def read_file(request: UploadRequest) -> Payroll:
    """The payroll in an uploaded file, or a 422 for a file that isn't a CSV by its
    name or its content, or that the template can't read."""
    if not request.file_name.lower().endswith(CSV) or "\x00" in request.content:
        raise HTTPException(422, NOT_CSV.format(file_name=request.file_name))
    try:
        return read_upload(request.content)
    except Unreadable as reason:
        raise HTTPException(422, str(reason)) from reason


def engagement_of(db: Connection, project_id: str, subcontractor_id: str) -> RowMapping:
    query = select(engagements).where(
        engagements.c.project_id == project_id,
        engagements.c.subcontractor_id == subcontractor_id,
    )
    found = db.execute(query).mappings().first()
    if found is None:
        message = NOT_ON_PROJECT.format(
            subcontractor_id=subcontractor_id, project_id=project_id
        )
        raise HTTPException(422, message)
    return found


def week_of(db: Connection, week_ending: date) -> int:
    """The week of our projects a week ending is, from 1 in the earliest week any
    engagement starts, as a case's id numbers it, or a 422 for a date that isn't
    one."""
    first = db.execute(
        select(func.min(engagements.c.first_week_ending))
        .join(projects, projects.c.project_id == engagements.c.project_id)
        .where(projects.c.held_out.is_(False))
    ).scalar_one()
    days = (week_ending - date.fromisoformat(first)).days
    if days < 0 or days % 7 or days // 7 + 1 > MOST_WEEKS:
        raise HTTPException(422, NOT_A_WEEK.format(week_ending=week_ending))
    return days // 7 + 1


def existing_case(
    db: Connection, project_id: str, subcontractor_id: str, week_ending: date
) -> RowMapping | None:
    """The queue's case for a subcontractor, project and week, if it has one."""
    query = select(cases).where(
        cases.c.evaluation_id.is_(None),
        cases.c.project_id == project_id,
        cases.c.subcontractor_id == subcontractor_id,
        cases.c.week_ending == week_ending.isoformat(),
    )
    return db.execute(query).mappings().first()


def already(
    case_id: str, project_id: str, subcontractor_id: str, week_ending: date
) -> str:
    return ALREADY.format(
        case_id=case_id,
        subcontractor_id=subcontractor_id,
        project_id=project_id,
        week_ending=week_ending.isoformat(),
    )


def take_upload(
    db: Connection, project_id: str, request: UploadRequest, reviewer: Reviewer
) -> str:
    """Turn an upload on a project's page into a submission, uploaded by the
    reviewer and received on the business date: a Received case's first, or the
    next of the case the week's payroll already has, which reopens it. Return the
    case's id."""
    payroll = read_file(request)
    certification = payroll.certification
    if certification.project_id != project_id:
        message = WRONG_PROJECT.format(theirs=certification.project_id, ours=project_id)
        raise HTTPException(422, message)
    subcontractor_id = request.subcontractor_id
    engagement = engagement_of(db, project_id, subcontractor_id)
    week_ending = certification.week_ending
    case = existing_case(db, project_id, subcontractor_id, week_ending)
    if case is not None:
        reopen(db, case, request, payroll, reviewer)
        return case["case_id"]
    case_id = CASE_ID.format(week=week_of(db, week_ending), pair=engagement["pair"])
    record_case(db, case_id, request, payroll, reviewer)
    return case_id


def record_case(
    db: Connection,
    case_id: str,
    request: UploadRequest,
    payroll: Payroll,
    reviewer: Reviewer,
) -> None:
    """Record a new Received case with the upload as its first submission, or a
    409 when the same upload made it a moment before: no other case can share its
    id, since a pair is our projects' own and held-out projects take no uploads."""
    certification = payroll.certification
    project_id, subcontractor_id = certification.project_id, request.subcontractor_id
    week_ending = certification.week_ending
    try:
        db.execute(
            insert(cases).values(
                case_id=case_id,
                subcontractor_id=subcontractor_id,
                project_id=project_id,
                week_ending=week_ending.isoformat(),
                latest_submission_no=1,
                **FRESH,
            )
        )
    except IntegrityError as taken:
        message = already(case_id, project_id, subcontractor_id, week_ending)
        raise HTTPException(409, message) from taken
    record_submission(db, (case_id, 1), request, payroll, reviewer)


def record_submission(
    db: Connection,
    submission: tuple[str, int],
    request: UploadRequest,
    payroll: Payroll,
    reviewer: Reviewer,
) -> None:
    """Record an upload as a case's submission, by the case's id and the
    submission's number, received on the business date."""
    case_id, submission_no = submission
    certification = payroll.certification
    db.execute(
        insert(submissions).values(
            case_id=case_id,
            submission_no=submission_no,
            uploaded_by=reviewer.reviewer_id,
            uploaded_at=now(),
            received_on=business_date(db).isoformat(),
            file_name=request.file_name,
            payroll_no=certification.payroll_no,
            wage_payment_date=certification.wage_payment_date.isoformat(),
            **payroll_record(payroll),
        )
    )


def reopen(
    db: Connection,
    case: RowMapping,
    request: UploadRequest,
    payroll: Payroll,
    reviewer: Reviewer,
) -> None:
    """Add the upload to a case as its next submission, in one move: the case back
    to Received as a fresh first attempt on no thread, and the open exceptions of
    its earlier submissions superseded, its dismissed ones left as they are. A case
    the agent is checking is refused, and so is the second of two uploads at the
    same moment, which finds the case moved on."""
    case_id, latest = case["case_id"], case["latest_submission_no"]
    if case["status"] == Status.IN_PROGRESS:
        raise HTTPException(409, BEING_CHECKED.format(case_id=case_id))
    moved = db.execute(
        update(cases)
        .where(
            cases.c.case_id == case_id,
            cases.c.latest_submission_no == latest,
            cases.c.status != Status.IN_PROGRESS,
        )
        .values(latest_submission_no=latest + 1, **FRESH)
    )
    if moved.rowcount != 1:
        raise HTTPException(409, why_not_reopened(db, case_id))
    record_submission(db, (case_id, latest + 1), request, payroll, reviewer)
    db.execute(
        update(exceptions)
        .where(
            exceptions.c.case_id == case_id,
            exceptions.c.submission_no <= latest,
            exceptions.c.status == ExceptionStatus.OPEN,
        )
        .values(status=ExceptionStatus.SUPERSEDED)
    )


def why_not_reopened(db: Connection, case_id: str) -> str:
    """Why a case another request moved on a moment ago wasn't reopened: the agent
    started checking it, or it took another upload."""
    status = db.execute(
        select(cases.c.status).where(cases.c.case_id == case_id)
    ).scalar_one()
    template = BEING_CHECKED if status == Status.IN_PROGRESS else UPLOADED_MEANWHILE
    return template.format(case_id=case_id)
