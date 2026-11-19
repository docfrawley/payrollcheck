"""Exposure: the money exceptions on each case's latest submission, in a reviewer's
scope, the filters and a period. Flagged is those not dismissed, which on a latest
submission means open, since only an earlier submission's are superseded;
outstanding is the flagged ones on cases Awaiting review or Returned to sub. Both
in cents and as dollars, with the cases behind them, by rule."""

from collections import defaultdict

from sqlalchemy import Connection, select

from backend.business_date import business_date
from backend.database import cases, exceptions
from backend.models import (
    ExposedException,
    Exposure,
    ExposureRequest,
    RuleExposure,
    Status,
)
from backend.money import cents_in_dollars
from backend.open_exceptions import open_on_latest
from backend.periods import answer_of, resolve
from backend.scope import Scope, queue_cases_in

# The statuses whose open exceptions are still outstanding.
OUTSTANDING = (Status.AWAITING_REVIEW, Status.RETURNED_TO_SUB)


def exposure(db: Connection, request: ExposureRequest, scope: Scope) -> Exposure:
    """The flagged and outstanding shortfalls for the request, in two queries."""
    period = resolve(business_date(db), request.period) if request.period else None
    chosen = select(cases.c.case_id).where(queue_cases_in(scope))
    if request.project_id is not None:
        chosen = chosen.where(cases.c.project_id == request.project_id)
    if request.subcontractor_id is not None:
        chosen = chosen.where(cases.c.subcontractor_id == request.subcontractor_id)
    if period is not None:
        chosen = chosen.where(
            cases.c.week_ending.between(
                period.first.isoformat(), period.last.isoformat()
            )
        )
    found = open_on_latest(
        db,
        exceptions.c.case_id.in_(chosen) & exceptions.c.shortfall_cents.is_not(None),
    )
    exposed = [
        ExposedException(
            case_id=row["case_id"],
            status=row["case_status"],
            rule=row["rule"],
            worker_id=row["worker_id"],
            worker_name=row["worker"],
            line_no=row["line_no"],
            shortfall_cents=row["shortfall_cents"],
            shortfall=cents_in_dollars(row["shortfall_cents"]),
            outstanding=row["case_status"] in OUTSTANDING,
            screening_flag=row["screening_flag"],
        )
        for rows in found.values()
        for row in rows
    ]
    flagged, outstanding = totals(exposed)
    return Exposure(
        period=answer_of(period) if period else None,
        project_id=request.project_id,
        subcontractor_id=request.subcontractor_id,
        flagged_cents=flagged,
        flagged=cents_in_dollars(flagged),
        outstanding_cents=outstanding,
        outstanding=cents_in_dollars(outstanding),
        case_ids=case_ids(exposed),
        by_rule=by_rule(exposed),
        exceptions=exposed,
    )


def totals(exposed: list[ExposedException]) -> tuple[int, int]:
    """The flagged and the outstanding shortfalls, in cents."""
    flagged = sum(e.shortfall_cents for e in exposed)
    return flagged, sum(e.shortfall_cents for e in exposed if e.outstanding)


def case_ids(exposed: list[ExposedException]) -> list[str]:
    return sorted({e.case_id for e in exposed})


def by_rule(exposed: list[ExposedException]) -> list[RuleExposure]:
    """Each rule's part of the totals, in the order the rules first appear."""
    grouped: dict[str, list[ExposedException]] = defaultdict(list)
    for exception in exposed:
        grouped[exception.rule].append(exception)
    return [rule_exposure(rule, found) for rule, found in grouped.items()]


def rule_exposure(rule: str, exposed: list[ExposedException]) -> RuleExposure:
    flagged, outstanding = totals(exposed)
    return RuleExposure(
        rule=rule,
        flagged_cents=flagged,
        flagged=cents_in_dollars(flagged),
        outstanding_cents=outstanding,
        outstanding=cents_in_dollars(outstanding),
        case_ids=case_ids(exposed),
    )
