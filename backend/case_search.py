"""Finding the queue's cases for the Copilot by project, subcontractor, status,
period, open exceptions and flag, each case with its shortfall in dollars, and the
cases grouped by subcontractor with their open exceptions counted, so no model
counts them."""

from sqlalchemy import Connection, func

from backend.business_date import business_date
from backend.database import case_view, cases, open_on_latest
from backend.models import CaseFilters, FoundCase, FoundCases, SubcontractorCases
from backend.money import cents_in_dollars
from backend.periods import answer_of, resolve
from backend.scope import Scope, cases_in
from backend.views import to_summary


def find_cases(db: Connection, filters: CaseFilters, scope: Scope) -> FoundCases:
    """The queue's cases in scope that match every filter given, in id order."""
    period = resolve(business_date(db), filters.period) if filters.period else None
    query = case_view.where(cases.c.evaluation_id.is_(None), cases_in(scope))
    if filters.project_id is not None:
        query = query.where(cases.c.project_id == filters.project_id)
    if filters.subcontractor_id is not None:
        query = query.where(cases.c.subcontractor_id == filters.subcontractor_id)
    if filters.status is not None:
        query = query.where(cases.c.status == filters.status)
    if period is not None:
        query = query.where(
            cases.c.week_ending.between(
                period.first.isoformat(), period.last.isoformat()
            )
        )
    if filters.flag == "screening":
        query = query.where(cases.c.screening_flag.is_(True))
    if filters.flag == "agent_failed":
        query = query.where(cases.c.agent_failed.is_(True))
    if filters.has_open_exceptions is not None:
        has_open = func.coalesce(open_on_latest.c.open_exceptions, 0) > 0
        query = query.where(has_open == filters.has_open_exceptions)
    found = [
        FoundCase(
            **to_summary(row).model_dump(),
            shortfall=cents_in_dollars(row["shortfall_cents"]),
        )
        for row in db.execute(query.order_by(cases.c.case_id)).mappings()
    ]
    return FoundCases(
        period=answer_of(period) if period else None,
        cases=found,
        by_subcontractor=by_subcontractor(found),
    )


def by_subcontractor(found: list[FoundCase]) -> list[SubcontractorCases]:
    """The cases grouped by subcontractor, in the order each first appears."""
    grouped: dict[str, SubcontractorCases] = {}
    for case in found:
        group = grouped.setdefault(
            case.subcontractor_id,
            SubcontractorCases(
                subcontractor_id=case.subcontractor_id,
                name=case.subcontractor_name,
                case_ids=[],
                open_exceptions=0,
            ),
        )
        group.case_ids.append(case.case_id)
        group.open_exceptions += case.open_exceptions
    return list(grouped.values())
