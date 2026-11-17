"""The judge's grades of an evaluation's notices: as the evaluation finishes, each
copy whose latest submission has an open exception has its draft notice graded
against the rubric, all at once, one thread each; a copy with no draft scores 0,
and one the judge couldn't grade is kept ungraded. A copy with nothing open needs
no notice and isn't graded. With a free model there's no judge."""

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import Connection, func, insert, select

from backend import judge
from backend.database import notice_grades, now
from backend.free_models import free_model
from backend.models import (
    NoticeGrade,
    NoticeGradeRecord,
    NoticeResult,
    NoticeToGrade,
)
from backend.notices import drafts_of
from backend.open_exceptions import as_read, open_exceptions_in


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
            case_id: NoticeToGrade(
                notice=drafts[case_id],
                exceptions=[as_read(row) for row in found[case_id]],
            )
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
