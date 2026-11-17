"""Filings: the payrolls expected in a period, worked out from each subcontractor's
engagement window on each project in scope, never a stored list, up to the
business date, since a week ending after it isn't due yet. A filing with no case
is missing; a case is late when its first submission was received more than the
due days after its wage payment date, a correction never making it late; and a
missing filing is late too once the business date is past its earliest deadline,
its week ending and the due days, since no wages are paid before the week ends."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import Connection, Row, Select, select

from backend.business_date import business_date
from backend.database import cases, engagements, projects, subcontractors, submissions
from backend.models import Filing, Filings, FilingsRequest, MissingFiling
from backend.periods import answer_of, resolve
from backend.scope import Scope, cases_in, projects_in
from data.payroll_world.periods import WEEK

# The filing rules' due days, N.J.S.A. 34:11-56.29, which the backend can't read
# from the context layer; a test checks they agree.
DUE_DAYS = 10


def filings(db: Connection, request: FilingsRequest, scope: Scope) -> Filings:
    """The late, missing and on-time filings of the period, in three queries."""
    today = business_date(db)
    period = resolve(today, request.period)
    windows = (
        select(engagements, subcontractors.c.legal_name)
        .join(
            subcontractors,
            subcontractors.c.subcontractor_id == engagements.c.subcontractor_id,
        )
        .join(projects, projects.c.project_id == engagements.c.project_id)
        .where(projects_in(scope))
    )
    if request.project_id is not None:
        windows = windows.where(engagements.c.project_id == request.project_id)
    filed = {
        (row.subcontractor_id, row.project_id, row.week_ending): row
        for row in db.execute(first_submissions(period.first, period.last, scope))
    }
    late: list[Filing] = []
    missing: list[MissingFiling] = []
    on_time: list[str] = []
    for window in db.execute(windows.order_by(engagements.c.pair)):
        name = window.legal_name
        for week in weeks_in(window, period.first, period.last, today):
            case = filed.get((window.subcontractor_id, window.project_id, week))
            if case is None:
                missing.append(missing_filing(window, name, week, today))
            elif days_after_payment(case) > DUE_DAYS:
                late.append(filing(case, name))
            else:
                on_time.append(case.case_id)
    return Filings(
        period=answer_of(period),
        business_date=today.isoformat(),
        late=sorted(late, key=lambda f: f.case_id),
        missing=missing,
        on_time=sorted(on_time),
    )


def first_submissions(first: date, last: date, scope: Scope) -> Select:
    """The queue's cases with a week ending in the period, each with its first
    submission's dates."""
    return (
        select(
            cases.c.case_id,
            cases.c.subcontractor_id,
            cases.c.project_id,
            cases.c.week_ending,
            submissions.c.wage_payment_date,
            submissions.c.received_on,
        )
        .join(submissions, submissions.c.case_id == cases.c.case_id)
        .where(
            cases.c.evaluation_id.is_(None),
            cases_in(scope),
            submissions.c.submission_no == 1,
            cases.c.week_ending.between(first.isoformat(), last.isoformat()),
        )
    )


def weeks_in(window: Row[Any], first: date, last: date, today: date) -> list[str]:
    """The week endings of an engagement window in the period, up to the business
    date."""
    week = date.fromisoformat(window.first_week_ending)
    end = min(date.fromisoformat(window.last_week_ending), last, today)
    found = []
    while week <= end:
        if week >= first:
            found.append(week.isoformat())
        week += WEEK
    return found


def days_after_payment(case: Row[Any]) -> int:
    paid = date.fromisoformat(case.wage_payment_date)
    return (date.fromisoformat(case.received_on) - paid).days


def filing(case: Row[Any], name: str) -> Filing:
    return Filing(
        case_id=case.case_id,
        subcontractor_id=case.subcontractor_id,
        subcontractor_name=name,
        project_id=case.project_id,
        week_ending=case.week_ending,
        wage_payment_date=case.wage_payment_date,
        received_on=case.received_on,
        days_after_payment=days_after_payment(case),
    )


def missing_filing(
    window: Row[Any], name: str, week: str, today: date
) -> MissingFiling:
    deadline = date.fromisoformat(week) + timedelta(days=DUE_DAYS)
    return MissingFiling(
        subcontractor_id=window.subcontractor_id,
        subcontractor_name=name,
        project_id=window.project_id,
        week_ending=week,
        deadline=deadline.isoformat(),
        late=today > deadline,
    )
