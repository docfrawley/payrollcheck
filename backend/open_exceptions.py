"""The one reader of the open exceptions on each case's latest submission, each with
its worker's name and its case's status: the scoring matches an evaluation's
copies' to the labels, the judge and the improver read them beside a notice
(`as_read`), and the Copilot's reads give a case's and its exposure."""

from sqlalchemy import ColumnElement, Connection, RowMapping, select

from backend.database import cases, exceptions, run_cases, workers
from backend.models import (
    CaseExceptions,
    ExceptionAsRead,
    ExceptionStatus,
    OpenException,
)
from backend.money import cents_in_dollars, cents_in_dollars_or_none


def open_on_latest(
    db: Connection, which: ColumnElement[bool]
) -> dict[str, list[RowMapping]]:
    """The open exceptions on the latest submission of each case `which` picks, by
    case, in the order they were raised, in one query."""
    query = (
        select(
            exceptions,
            workers.c.name.label("worker"),
            cases.c.status.label("case_status"),
            cases.c.screening_flag,
        )
        .join(cases, cases.c.case_id == exceptions.c.case_id)
        .outerjoin(workers, workers.c.worker_id == exceptions.c.worker_id)
        .where(
            which,
            exceptions.c.status == ExceptionStatus.OPEN,
            exceptions.c.submission_no == cases.c.latest_submission_no,
        )
        .order_by(exceptions.c.case_id, exceptions.c.exception_id)
    )
    found: dict[str, list[RowMapping]] = {}
    for row in db.execute(query).mappings():
        found.setdefault(row["case_id"], []).append(row)
    return found


def open_exceptions_of(
    db: Connection, case_ids: list[str]
) -> dict[str, list[RowMapping]]:
    """The open exceptions on these copies' latest submissions, by copy; a copy with
    none isn't in it."""
    return open_on_latest(db, exceptions.c.case_id.in_(case_ids))


def open_exceptions_in(db: Connection, run_id: str) -> dict[str, list[RowMapping]]:
    """The open exceptions on the latest submissions of a run's copies, by copy; a
    copy with none isn't in it."""
    in_run = select(run_cases.c.case_id).where(run_cases.c.run_id == run_id)
    return open_on_latest(db, exceptions.c.case_id.in_(in_run))


def as_read(row: RowMapping) -> ExceptionAsRead:
    """An exception as the judge and the improver read it beside a notice: the
    worker by name and the shortfall in dollars."""
    return ExceptionAsRead(
        rule=row["rule"],
        worker=row["worker"],
        line_no=row["line_no"],
        expected=row["expected"],
        actual=row["actual"],
        shortfall=cents_in_dollars_or_none(row["shortfall_cents"]),
        citation=row["citation"],
    )


def case_exceptions(db: Connection, case: RowMapping) -> CaseExceptions:
    """A case's open exceptions on its latest submission, each with its citation and
    its shortfall in dollars, and their shortfall together."""
    found = [
        OpenException(
            **row,
            worker_name=row["worker"],
            shortfall=cents_in_dollars_or_none(row["shortfall_cents"]),
        )
        for row in open_exceptions_of(db, [case["case_id"]]).get(case["case_id"], [])
    ]
    total = sum(e.shortfall_cents or 0 for e in found)
    return CaseExceptions(
        case_id=case["case_id"],
        status=case["status"],
        screening_flag=case["screening_flag"],
        screening_reason=case["screening_reason"],
        project_id=case["project_id"],
        subcontractor_id=case["subcontractor_id"],
        week_ending=case["week_ending"],
        exceptions=found,
        shortfall_cents=total,
        shortfall=cents_in_dollars(total),
    )
