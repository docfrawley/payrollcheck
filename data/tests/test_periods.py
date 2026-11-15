"""Periods are resolved from the business date and matched on week endings."""

from datetime import date

import pytest

from data.payroll_world import periods

MONDAY = date(2026, 11, 23)


@pytest.mark.parametrize(
    ("business_date", "ending"),
    [
        (MONDAY, date(2026, 11, 22)),
        (date(2026, 11, 25), date(2026, 11, 22)),
        (date(2026, 11, 28), date(2026, 11, 22)),
        # On a Sunday, that week hasn't ended before the business date.
        (date(2026, 11, 22), date(2026, 11, 15)),
    ],
)
def test_last_week_is_the_latest_week_ending_before_the_business_date(
    business_date, ending
):
    assert periods.last_week(business_date) == periods.Period(ending, ending)


def test_the_last_four_weeks():
    four = periods.last_weeks(MONDAY, 4)
    assert (four.first, four.last) == (date(2026, 11, 1), date(2026, 11, 22))
    assert four.holds(date(2026, 11, 8))
    assert not four.holds(date(2026, 10, 25))


def test_this_month_holds_the_week_endings_in_the_business_dates_month():
    november = periods.this_month(date(2026, 11, 25))
    assert (november.first, november.last) == (date(2026, 11, 1), date(2026, 11, 29))
    assert november.holds(date(2026, 11, 1))
    assert not november.holds(date(2026, 10, 25))
    december = periods.this_month(date(2026, 12, 31))
    assert (december.first, december.last) == (date(2026, 12, 6), date(2026, 12, 27))
