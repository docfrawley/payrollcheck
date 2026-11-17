"""Every period resolved by the backend from the business date, with the periods
module the generator's expected answers use, and matched on a case's week
ending."""

from datetime import date

import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from backend.business_date import business_date
from backend.database import cases, engine, submissions
from backend.models import PeriodRequest
from backend.periods import answer_of, resolve
from backend.seeding import DATA
from backend.tests.settings_requests import change_settings
from data.payroll_world.expected_answers import answer_to, read_expected

PERIOD = TypeAdapter(PeriodRequest)


def resolved(period):
    with engine().connect() as db:
        return resolve(business_date(db), PERIOD.validate_python(period))


def weeks(found):
    return (found.first, found.last)


def test_from_the_seeded_business_date():
    assert weeks(resolved({"kind": "last_week"})) == (
        date(2026, 11, 22),
        date(2026, 11, 22),
    )
    assert weeks(resolved({"kind": "last_weeks", "count": 4})) == (
        date(2026, 11, 1),
        date(2026, 11, 22),
    )
    assert weeks(resolved({"kind": "this_month"})) == (
        date(2026, 11, 1),
        date(2026, 11, 29),
    )
    between = {"kind": "between", "first": "2026-10-04", "last": "2026-11-01"}
    found = resolved(between)
    assert weeks(found) == (date(2026, 10, 4), date(2026, 11, 1))
    assert found.holds(date(2026, 10, 4))
    assert found.holds(date(2026, 11, 1))


def test_a_week_that_crosses_a_month_counts_in_the_month_it_ends():
    # The week ending Sun Nov 1 began on Mon Oct 26.
    november = resolved({"kind": "this_month"})
    assert november.holds(date(2026, 11, 1))
    assert not november.holds(date(2026, 10, 25))


def test_on_a_sunday_last_week_is_the_week_ending_the_sunday_before(client):
    change_settings(client, business_date="2026-11-22")
    assert weeks(resolved({"kind": "last_week"})) == (
        date(2026, 11, 15),
        date(2026, 11, 15),
    )


def test_a_period_matches_a_cases_week_ending_not_its_other_dates():
    # PC-1208's wages were paid Nov 11 and it was received Nov 23, both outside
    # last week, which holds its week ending.
    last_week = resolved({"kind": "last_week"})
    with engine().connect() as db:
        row = db.execute(
            select(cases.c.week_ending, submissions)
            .join(submissions, submissions.c.case_id == cases.c.case_id)
            .where(cases.c.case_id == "PC-1208")
        ).one()
    assert last_week.holds(date.fromisoformat(row.week_ending))
    assert not last_week.holds(date.fromisoformat(row.wage_payment_date))
    assert not last_week.holds(date.fromisoformat(row.received_on))


@pytest.mark.parametrize(
    "period",
    [
        {"kind": "between", "first": "2026-10-05", "last": "2026-11-01"},
        {"kind": "between", "first": "2026-11-01", "last": "2026-10-04"},
        {"kind": "last_weeks", "count": 0},
        {"kind": "yesterday"},
    ],
)
def test_a_period_that_isnt_one_is_refused(period):
    with pytest.raises(ValidationError):
        PERIOD.validate_python(period)


def test_the_copilots_expected_answers_have_the_periods_the_backend_resolves():
    expected = read_expected(DATA)
    assert expected["business_date"] == "2026-11-23"
    periods = {
        "this_month": answer_to(expected, 2)["period"],
        "last_week": answer_to(expected, 3)["period"],
        "last_weeks": answer_to(expected, 5)["period"],
    }
    asked = {"this_month": {}, "last_week": {}, "last_weeks": {"count": 4}}
    for kind, period in periods.items():
        found = answer_of(resolved({"kind": kind, **asked[kind]}))
        assert found.model_dump() == period
