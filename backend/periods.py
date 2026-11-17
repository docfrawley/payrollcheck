"""The periods the Copilot asks about, as a request names them, resolved from the
business date by the periods module the generator's expected answers use, so the
two can't disagree. A period is matched on a case's week ending, and an answer
gives back the week endings it resolved, so no model works out a date."""

from datetime import date

from backend.models import (
    Between,
    LastWeek,
    LastWeeks,
    PeriodAnswer,
    PeriodRequest,
    ThisMonth,
)
from data.payroll_world import periods


def resolve(today: date, period: PeriodRequest) -> periods.Period:
    """The week endings a period holds, from the business date."""
    match period:
        case LastWeek():
            return periods.last_week(today)
        case ThisMonth():
            return periods.this_month(today)
        case LastWeeks(count=count):
            return periods.last_weeks(today, count)
        case Between(first=first, last=last):
            return periods.between(first, last)


def answer_of(period: periods.Period) -> PeriodAnswer:
    return PeriodAnswer(**period.record())
