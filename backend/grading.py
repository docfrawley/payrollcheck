"""The judge's grades of an evaluation's notices: as the evaluation finishes, each
copy whose latest submission has an open exception has its draft notice graded
against the rubric, all at once, one thread each; a copy with no draft scores 0,
and one the judge couldn't grade is kept ungraded. A copy with nothing open needs
no notice and isn't graded. With a free model there's no judge."""

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import Connection, func, insert, select

from backend import judge
from backend.database import (
    cases,
    exceptions,
    notice_grades,
    now,
    run_cases,
    workers,
)
from backend.free_models import free_model
from backend.models import (
    ExceptionAsRead,
    ExceptionStatus,
    NoticeGrade,
    NoticeGradeRecord,
    NoticeResult,
    NoticeToGrade,
)
from backend.money import dollars
from backend.notices import drafts_of


def open_exceptions_in(db: Connection, run_id: str) -> dict[str, list[ExceptionAsRead]]:
    """Each of a run's copies with an open exception on its latest submission, with
    those exceptions as the judge reads them, in one query."""
    query = (
        select(exceptions, workers.c.name.label("worker"))
        .join(cases, cases.c.case_id == exceptions.c.case_id)
        .join(run_cases, run_cases.c.case_id == cases.c.case_id)
        .outerjoin(workers, workers.c.worker_id == exceptions.c.worker_id)
        .where(
            run_cases.c.run_id == run_id,
            exceptions.c.status == ExceptionStatus.OPEN,
            exceptions.c.submission_no == cases.c.latest_submission_no,
        )
        .order_by(exceptions.c.case_id, exceptions.c.exception_id)
    )
    found: dict[str, list[ExceptionAsRead]] = {}
    for row in db.execute(query).mappings():
        shortfall = row["shortfall_cents"]
        found.setdefault(row["case_id"], []).append(
            ExceptionAsRead(
                rule=row["rule"],
                worker=row["worker"],
                line_no=row["line_no"],
                expected=row["expected"],
                actual=row["actual"],
                shortfall=dollars(shortfall / 100) if shortfall is not None else None,
                citation=row["citation"],
            )
        )
    return found


def grade_of(graded: NoticeGrade | None, drafted: bool) -> NoticeGradeRecord:
    """A copy's grade: graded, no notice, which scores 0, or ungraded."""
    if not drafted:
        return NoticeGradeRecord(result=NoticeResult.NO_NOTICE, score=0.0, cost=0.0)
    if graded is None:
        return NoticeGradeRecord(result=NoticeResult.NOT_GRADED, score=None, cost=0.0)
    return NoticeGradeRecord(result=NoticeResult.GRADED, **graded.model_dump())


def ask_all(to_ask: dict[str, NoticeToGrade]) -> dict[str, NoticeGrade | None]:
    """Ask the judge to grade every notice at once, one thread each."""
    with ThreadPoolExecutor(max_workers=max(len(to_ask), 1)) as pool:
        graded = pool.map(judge.grade, to_ask.values())
        return dict(zip(to_ask, graded, strict=True))


def record(db: Connection, run_id: str, grades: dict[str, NoticeGradeRecord]) -> None:
    """Record each copy's grade with its run."""
    db.execute(
        insert(notice_grades),
        [
            {
                "case_id": case_id,
                "run_id": run_id,
                **grade.model_dump(),
                "graded_at": now(),
            }
            for case_id, grade in grades.items()
        ],
    )


def grade_notices(db: Connection, run_id: str) -> None:
    """Grade the draft notices of an evaluation's copies that need one, all at
    once, and record every grade."""
    if free_model():
        return
    found = open_exceptions_in(db, run_id)
    if not found:
        return
    drafts = drafts_of(db, list(found))
    graded = ask_all(
        {
            case_id: NoticeToGrade(notice=drafts[case_id], exceptions=found[case_id])
            for case_id in found
            if case_id in drafts
        }
    )
    record(
        db,
        run_id,
        {
            case_id: grade_of(graded.get(case_id), case_id in drafts)
            for case_id in found
        },
    )


def grades_of(db: Connection, case_ids: list[str]) -> dict[str, NoticeGradeRecord]:
    """The grade of each copy's notice, for the copies that have one."""
    query = select(notice_grades).where(notice_grades.c.case_id.in_(case_ids))
    return {
        row["case_id"]: NoticeGradeRecord(**row) for row in db.execute(query).mappings()
    }


def judge_costs(db: Connection, run_ids: list[str]) -> dict[str, float]:
    """What the judge cost on each run, in one query for them all."""
    query = (
        select(notice_grades.c.run_id, func.sum(notice_grades.c.cost))
        .where(notice_grades.c.run_id.in_(run_ids))
        .group_by(notice_grades.c.run_id)
    )
    costs = dict.fromkeys(run_ids, 0.0)
    costs.update({run_id: cost for run_id, cost in db.execute(query)})
    return costs
