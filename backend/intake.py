"""Intake: an uploaded CSV turned into a submission by the template's strict reader,
with no model, or refused with its reason and no case created. Only a file that
can't become a submission is refused; anything else it says is accepted, however
wrong, for the payroll agent to find. The first upload for a subcontractor,
project and week creates its case, Received."""

from datetime import date

from fastapi import HTTPException
from sqlalchemy import Connection, RowMapping, func, insert, select
from sqlalchemy.exc import IntegrityError

from backend.business_date import business_date
from backend.database import cases, engagements, now, projects, submissions
from backend.models import Reviewer, Status, UploadRequest
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
CASE_ID = "PC-{week:02d}{pair:02d}"
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


def refuse_an_existing_case(
    db: Connection, project_id: str, subcontractor_id: str, week_ending: date
) -> None:
    """A 409 naming the case when the week's payroll already has one. Reopening a
    case with a new submission comes in stage 4."""
    query = select(cases.c.case_id).where(
        cases.c.evaluation_id.is_(None),
        cases.c.project_id == project_id,
        cases.c.subcontractor_id == subcontractor_id,
        cases.c.week_ending == week_ending.isoformat(),
    )
    found = db.execute(query).scalar_one_or_none()
    if found is not None:
        raise HTTPException(
            409, already(found, project_id, subcontractor_id, week_ending)
        )


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
    """Turn an upload on a project's page into a Received case with its first
    submission, uploaded by the reviewer and received on the business date, and
    return the case's id."""
    payroll = read_file(request)
    certification = payroll.certification
    if certification.project_id != project_id:
        message = WRONG_PROJECT.format(theirs=certification.project_id, ours=project_id)
        raise HTTPException(422, message)
    subcontractor_id = request.subcontractor_id
    engagement = engagement_of(db, project_id, subcontractor_id)
    week_ending = certification.week_ending
    refuse_an_existing_case(db, project_id, subcontractor_id, week_ending)
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
                status=Status.RECEIVED,
                screening_flag=False,
                agent_failed=False,
                latest_submission_no=1,
                attempts=0,
            )
        )
    except IntegrityError as taken:
        message = already(case_id, project_id, subcontractor_id, week_ending)
        raise HTTPException(409, message) from taken
    db.execute(
        insert(submissions).values(
            case_id=case_id,
            submission_no=1,
            uploaded_by=reviewer.reviewer_id,
            uploaded_at=now(),
            received_on=business_date(db).isoformat(),
            file_name=request.file_name,
            payroll_no=certification.payroll_no,
            wage_payment_date=certification.wage_payment_date.isoformat(),
            **payroll_record(payroll),
        )
    )
