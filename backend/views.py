"""Cases as the API shows them: a case's line in the queue from its row of the case
view, and a case in full with its submissions, workers, exceptions, the current
attempt's candidates and checks, and its notice."""

from typing import cast

from sqlalchemy import Connection, RowMapping, select

from backend.database import (
    candidates,
    check_runs,
    exceptions,
    notices,
    submissions,
    workers,
)
from backend.lookups import find_case
from backend.models import (
    Candidate,
    Case,
    CaseSummary,
    CheckName,
    ExceptionRecord,
    Notice,
    Submission,
    Worker,
)
from backend.rule_codes import CHECKS


def to_summary(row: RowMapping) -> CaseSummary:
    """A case's line in the queue, from its row of the case view."""
    return CaseSummary(**{field: row[field] for field in CaseSummary.model_fields})


def submissions_of(db: Connection, case_id: str) -> list[Submission]:
    query = (
        select(submissions)
        .where(submissions.c.case_id == case_id)
        .order_by(submissions.c.submission_no)
    )
    return [Submission(**row) for row in db.execute(query).mappings()]


def workers_on(db: Connection, latest: Submission) -> list[Worker]:
    """Each worker on a submission, as our records have them."""
    ids = [line["worker_id"] for line in latest.lines]
    query = select(workers).where(workers.c.worker_id.in_(ids))
    found = {row["worker_id"]: Worker(**row) for row in db.execute(query).mappings()}
    return [found[i] for i in dict.fromkeys(ids) if i in found]


def exceptions_of(db: Connection, case_id: str) -> list[ExceptionRecord]:
    query = (
        select(exceptions)
        .where(exceptions.c.case_id == case_id)
        .order_by(exceptions.c.exception_id)
    )
    return [ExceptionRecord(**row) for row in db.execute(query).mappings()]


def candidates_of(
    db: Connection, case_id: str, thread_id: str | None
) -> list[Candidate]:
    """The current attempt's candidates, in the order the checks ran."""
    query = select(candidates).where(
        candidates.c.case_id == case_id, candidates.c.thread_id == thread_id
    )
    found = [Candidate(**row) for row in db.execute(query).mappings()]
    return sorted(found, key=lambda c: (CHECKS.index(c.check), c.candidate_id))


def checks_run_on(
    db: Connection, case_id: str, thread_id: str | None
) -> list[CheckName]:
    query = select(check_runs.c.check).where(
        check_runs.c.case_id == case_id, check_runs.c.thread_id == thread_id
    )
    ran = set(db.execute(query).scalars())
    return [cast(CheckName, check) for check in CHECKS if check in ran]


def notice_of(db: Connection, case_id: str, submission_no: int) -> Notice | None:
    query = select(notices).where(
        notices.c.case_id == case_id, notices.c.submission_no == submission_no
    )
    row = db.execute(query).mappings().first()
    return None if row is None else Notice(**row)


def case_in_full(db: Connection, case_id: str) -> Case:
    """One case in full, as the API shows it, or raise a 404."""
    row = find_case(db, case_id)
    found = submissions_of(db, case_id)
    thread_id = row["thread_id"]
    return Case(
        **to_summary(row).model_dump(),
        **{field: row[field] for field in CASE_FIELDS},
        submissions=found,
        workers=workers_on(db, found[-1]),
        exceptions=exceptions_of(db, case_id),
        candidates=candidates_of(db, case_id, thread_id),
        checks_run=checks_run_on(db, case_id, thread_id),
        notice=notice_of(db, case_id, row["latest_submission_no"]),
    )


# The columns of a case's row that its record in full shows beside its line.
CASE_FIELDS = (
    "screening_reason",
    "latest_submission_no",
    "thread_id",
    "attempts",
    "evaluation_id",
    "copy_of",
    "reviewed_by",
    "reviewed_on",
)
