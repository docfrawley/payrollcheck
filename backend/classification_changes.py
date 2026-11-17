"""Classification changes: each worker on a case in scope and in a period whose
classification on its latest submission differs from their line on the same
subcontractor and project's case the week before, also on its latest submission,
with the line's note, the worker's established craft from our records and any
classification exception open on the line."""

from datetime import date
from typing import Any

from sqlalchemy import Connection, RowMapping, select

from backend.business_date import business_date
from backend.database import cases, exceptions, subcontractors, submissions, workers
from backend.models import (
    ClassificationChange,
    ClassificationChanges,
    ClassificationChangesRequest,
    ExceptionOnLine,
)
from backend.open_exceptions import open_on_latest
from backend.periods import answer_of, resolve
from backend.rule_codes import CLASSIFICATION, RULES
from backend.scope import Scope, cases_in
from data.payroll_world.periods import WEEK

CLASSIFICATION_RULES = [
    code for code, rule in RULES.items() if rule.check == CLASSIFICATION
]


def classification_changes(
    db: Connection, request: ClassificationChangesRequest, scope: Scope
) -> ClassificationChanges:
    """The changes in the period, in four queries."""
    period = resolve(business_date(db), request.period)
    latest = latest_payrolls(db, period.first - WEEK, period.last, scope, request)
    by_week = {
        (row["subcontractor_id"], row["project_id"], row["week_ending"]): row
        for row in latest
    }
    changed = [
        (case, line_no, line, earlier)
        for case in latest
        if date.fromisoformat(case["week_ending"]) >= period.first
        for line_no, line, earlier in changes_on(case, by_week)
    ]
    crafts = established_crafts(db, [line["worker_id"] for _, _, line, _ in changed])
    found = open_on_lines(db, [case["case_id"] for case, *_ in changed])
    return ClassificationChanges(
        period=answer_of(period),
        changes=[
            ClassificationChange(
                case_id=case["case_id"],
                case_id_before=by_week[week_before(case)]["case_id"],
                screening_flag=case["screening_flag"],
                screening_flag_before=by_week[week_before(case)]["screening_flag"],
                project_id=case["project_id"],
                subcontractor_id=case["subcontractor_id"],
                subcontractor_name=case["legal_name"],
                worker_id=line["worker_id"],
                worker_name=name,
                week_ending=case["week_ending"],
                line_no=line_no,
                classification_before=earlier["classification"],
                classification_after=line["classification"],
                line_notes=line["line_notes"],
                established_craft=craft,
                exception=found.get((case["case_id"], line_no)),
            )
            for case, line_no, line, earlier in changed
            for name, craft in [crafts.get(line["worker_id"], (None, None))]
        ],
    )


def latest_payrolls(
    db: Connection,
    first: date,
    last: date,
    scope: Scope,
    request: ClassificationChangesRequest,
) -> list[RowMapping]:
    """The queue's cases with a week ending from one date to another, each with its
    latest submission's lines, in case id order."""
    query = (
        select(
            cases.c.case_id,
            cases.c.subcontractor_id,
            cases.c.project_id,
            cases.c.week_ending,
            cases.c.screening_flag,
            subcontractors.c.legal_name,
            submissions.c.lines,
        )
        .join(
            submissions,
            (submissions.c.case_id == cases.c.case_id)
            & (submissions.c.submission_no == cases.c.latest_submission_no),
        )
        .join(
            subcontractors,
            subcontractors.c.subcontractor_id == cases.c.subcontractor_id,
        )
        .where(
            cases.c.evaluation_id.is_(None),
            cases_in(scope),
            cases.c.week_ending.between(first.isoformat(), last.isoformat()),
        )
        .order_by(cases.c.case_id)
    )
    if request.project_id is not None:
        query = query.where(cases.c.project_id == request.project_id)
    return list(db.execute(query).mappings())


def week_before(case: RowMapping) -> tuple[str, str, str]:
    """The subcontractor, project and week ending of a case's week before."""
    week = (date.fromisoformat(case["week_ending"]) - WEEK).isoformat()
    return (case["subcontractor_id"], case["project_id"], week)


def changes_on(
    case: RowMapping, by_week: dict[tuple[str, str, str], RowMapping]
) -> list[tuple[int, dict[str, Any], dict[str, Any]]]:
    """Each line of a case whose classification differs from the worker's line the
    week before, with its number and that earlier line."""
    before = by_week.get(week_before(case))
    if before is None:
        return []
    earlier = {line["worker_id"]: line for line in before["lines"]}
    return [
        (line_no, line, earlier[line["worker_id"]])
        for line_no, line in enumerate(case["lines"], start=1)
        if line["worker_id"] in earlier
        and earlier[line["worker_id"]]["classification"] != line["classification"]
    ]


def established_crafts(
    db: Connection, worker_ids: list[str]
) -> dict[str, tuple[str, str]]:
    """Each worker's name and established craft, from our records."""
    query = select(workers.c.worker_id, workers.c.name, workers.c.craft).where(
        workers.c.worker_id.in_(worker_ids)
    )
    return {worker_id: (name, craft) for worker_id, name, craft in db.execute(query)}


def open_on_lines(
    db: Connection, case_ids: list[str]
) -> dict[tuple[str, int], ExceptionOnLine]:
    """The first classification exception raised and still open on each line of
    these cases' latest submissions, by case and line."""
    found = open_on_latest(
        db,
        exceptions.c.case_id.in_(case_ids)
        & exceptions.c.rule.in_(CLASSIFICATION_RULES),
    )
    on_lines: dict[tuple[str, int], ExceptionOnLine] = {}
    for case_id, rows in found.items():
        for row in rows:
            on_lines.setdefault(
                (case_id, row["line_no"]),
                ExceptionOnLine(
                    exception_id=row["exception_id"],
                    rule=row["rule"],
                    severity=row["severity"],
                ),
            )
    return on_lines
