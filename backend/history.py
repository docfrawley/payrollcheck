"""A case's payroll history: the latest submission of each earlier week of the
same subcontractor and project, from the queue, or for an evaluation's copy from
its own labelled set, never the queue. Nothing in it comes from the labels."""

from typing import Any

from sqlalchemy import Connection, RowMapping, select

from backend.database import cases, labelled_cases, runs, submissions
from backend.models import LABELLED_SET, PayrollHistory, PayrollOfRecord
from backend.scope import EVERYTHING, queue_cases_in


def of_record(
    case_id: str, week_ending: str, latest: dict[str, Any]
) -> PayrollOfRecord:
    return PayrollOfRecord(
        case_id=case_id,
        week_ending=week_ending,
        submission_no=latest["submission_no"],
        certification=latest["certification"],
        lines=latest["lines"],
    )


def from_the_queue(db: Connection, case: RowMapping) -> list[PayrollOfRecord]:
    query = (
        select(cases.c.case_id, cases.c.week_ending, submissions)
        .join(
            submissions,
            (submissions.c.case_id == cases.c.case_id)
            & (submissions.c.submission_no == cases.c.latest_submission_no),
        )
        .where(
            queue_cases_in(EVERYTHING),
            cases.c.subcontractor_id == case["subcontractor_id"],
            cases.c.project_id == case["project_id"],
            cases.c.week_ending < case["week_ending"],
        )
        .order_by(cases.c.week_ending)
    )
    return [
        of_record(row["case_id"], row["week_ending"], dict(row))
        for row in db.execute(query).mappings()
    ]


def from_its_set(db: Connection, case: RowMapping) -> list[PayrollOfRecord]:
    """A copy's history: its labelled set's earlier weeks, each as the generator
    wrote its latest submission."""
    evaluation_set = db.execute(
        select(runs.c.evaluation_set).where(runs.c.run_id == case["evaluation_id"])
    ).scalar_one()
    query = (
        select(labelled_cases)
        .where(
            labelled_cases.c.labelled_set == LABELLED_SET[evaluation_set],
            labelled_cases.c.subcontractor_id == case["subcontractor_id"],
            labelled_cases.c.project_id == case["project_id"],
            labelled_cases.c.week_ending < case["week_ending"],
        )
        .order_by(labelled_cases.c.week_ending)
    )
    return [
        of_record(row["case_id"], row["week_ending"], row["submissions"][-1])
        for row in db.execute(query).mappings()
    ]


def payroll_history(db: Connection, case: RowMapping) -> PayrollHistory:
    if case["evaluation_id"] is None:
        return PayrollHistory(payrolls=from_the_queue(db, case))
    return PayrollHistory(payrolls=from_its_set(db, case))
