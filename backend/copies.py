"""An evaluation's copies of a labelled set's cases: each copy a Received case of
the evaluation's own, holding the submissions its original had before anyone
reviewed it, with an id like PC-1104-E7."""

from typing import Any

from sqlalchemy import Connection, RowMapping, insert, select

from backend.database import cases, labelled_cases, submissions
from backend.models import LABELLED_SET, EvaluationSet, Status

COPY_ID = "{case_id}-E{number}"


def originals(db: Connection, evaluation_set: EvaluationSet) -> list[RowMapping]:
    """A labelled set's cases, or the development set's tiny ones, oldest week
    first."""
    query = select(labelled_cases).where(
        labelled_cases.c.labelled_set == LABELLED_SET[evaluation_set]
    )
    if evaluation_set == EvaluationSet.TINY:
        query = query.where(labelled_cases.c.tiny)
    order = (labelled_cases.c.week_ending, labelled_cases.c.case_id)
    return list(db.execute(query.order_by(*order)).mappings())


def copy_row(original: RowMapping, copy_id: str, run_id: str) -> dict[str, Any]:
    return {
        "case_id": copy_id,
        "subcontractor_id": original["subcontractor_id"],
        "project_id": original["project_id"],
        "week_ending": original["week_ending"],
        "status": Status.RECEIVED,
        "screening_flag": False,
        "agent_failed": False,
        "latest_submission_no": original["before_review"],
        "attempts": 0,
        "evaluation_id": run_id,
        "copy_of": original["case_id"],
    }


def make_copies(db: Connection, run: RowMapping) -> list[str]:
    """Copy each case of the evaluation's set as the evaluation's own, and return
    the copies' ids in order."""
    found = originals(db, run["evaluation_set"])
    ids = [COPY_ID.format(case_id=o["case_id"], number=run["number"]) for o in found]
    db.execute(
        insert(cases),
        [
            copy_row(o, copy_id, run["run_id"])
            for o, copy_id in zip(found, ids, strict=True)
        ],
    )
    db.execute(
        insert(submissions),
        [
            submission | {"case_id": copy_id}
            for o, copy_id in zip(found, ids, strict=True)
            for submission in o["submissions"][: o["before_review"]]
        ],
    )
    return ids
