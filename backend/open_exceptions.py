"""The one reader of the open exceptions on each copy's latest submission, each with
its worker's name: the scoring matches them to the labels, and the judge and the
improver read them beside a notice (`as_read`)."""

from sqlalchemy import ColumnElement, Connection, RowMapping, select

from backend.database import cases, exceptions, run_cases, workers
from backend.models import ExceptionAsRead, ExceptionStatus
from backend.money import dollars


def open_on_latest(
    db: Connection, which: ColumnElement[bool]
) -> dict[str, list[RowMapping]]:
    """The open exceptions on the latest submission of each copy `which` picks, by
    copy, in the order they were raised, in one query."""
    query = (
        select(exceptions, workers.c.name.label("worker"))
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
    shortfall = row["shortfall_cents"]
    return ExceptionAsRead(
        rule=row["rule"],
        worker=row["worker"],
        line_no=row["line_no"],
        expected=row["expected"],
        actual=row["actual"],
        shortfall=dollars(shortfall / 100) if shortfall is not None else None,
        citation=row["citation"],
    )
