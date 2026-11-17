"""The periods a reviewer asks about, resolved from the business date and matched
on a payroll's week ending: last week, the last N weeks, this month, and the weeks
ending between two dates. The generator's expected answers and the app's tools
resolve every period here, so they can't disagree."""

from dataclasses import dataclass
from datetime import date, timedelta

SUNDAY = 6


@dataclass(frozen=True)
class Period:
    """The week endings from the first to the last, both included."""

    first: date
    last: date

    def holds(self, week_ending: date) -> bool:
        return self.first <= week_ending <= self.last

    def record(self) -> dict[str, str]:
        """The period as an answer gives it: its first and last week endings."""
        return {
            "first_week_ending": self.first.isoformat(),
            "last_week_ending": self.last.isoformat(),
        }


def last_week_ending(business_date: date) -> date:
    """The latest week ending, a Sunday, before the business date."""
    return business_date - timedelta(days=(business_date.weekday() - SUNDAY) % 7 or 7)


def last_week(business_date: date) -> Period:
    """The latest payroll week ending before the business date."""
    ending = last_week_ending(business_date)
    return Period(ending, ending)


def last_weeks(business_date: date, count: int) -> Period:
    """The latest number of payroll weeks ending before the business date."""
    ending = last_week_ending(business_date)
    return Period(ending - timedelta(weeks=count - 1), ending)


def this_month(business_date: date) -> Period:
    """Every week ending in the business date's month: its first Sunday to its
    last."""
    first_day = business_date.replace(day=1)
    following = (first_day + timedelta(days=31)).replace(day=1)
    first_sunday = first_day + timedelta(days=(SUNDAY - first_day.weekday()) % 7)
    return Period(first_sunday, last_week_ending(following))


def between(first: date, last: date) -> Period:
    """The week endings from one to another, both included."""
    return Period(first, last)
