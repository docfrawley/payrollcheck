"""The one rate logic, against the rate determinations in context/."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from context import payroll_files, wage_rules
from context.payroll_files import RATES
from context.wage_rules import Premium, Work

LINCOLN_AWARD = date(2026, 4, 15)
INCREASE = date(2026, 10, 1)
# A week of work, Monday 2026-10-05 to Sunday 2026-10-11.
MONDAY = date(2026, 10, 5)
TIME_AND_A_HALF = Decimal("1.5")
STRAIGHT = Premium(Decimal(1), Decimal(1))


def week(*hours: float) -> list[tuple[date, Decimal]]:
    """Each day's hours from Monday, for as many days as given."""
    return [(MONDAY + timedelta(days), Decimal(str(h))) for days, h in enumerate(hours)]


def electrician(work_date: date, award: date = LINCOLN_AWARD, level=None):
    classification = "apprentice" if level else "journeyman"
    work = Work("electrician", classification, "Middlesex", award, level)
    return wage_rules.required_rate(RATES, work, work_date)


@pytest.mark.parametrize(
    ("award", "determination"),
    [
        (date(2025, 6, 2), "MID-2024-11"),
        (LINCOLN_AWARD, "MID-2025-11"),
        (date(2026, 7, 6), "MID-2026-07"),
    ],
)
def test_the_determination_in_force_on_the_award_date(award, determination):
    found = wage_rules.determination_in_force(RATES, "Middlesex", award)
    assert found is not None
    assert found.id == determination


def test_a_later_determination_is_never_chosen():
    for day in (date(2026, 7, 6), date(2026, 11, 23), date(2027, 6, 1)):
        assert electrician(day).determination.id == "MID-2025-11"
    assert (
        wage_rules.determination_in_force(RATES, "Middlesex", date(2024, 1, 2)) is None
    )


def test_the_row_before_and_after_the_pre_listed_increase():
    before = electrician(INCREASE - timedelta(days=1))
    after = electrician(INCREASE)
    assert (before.row.effective, before.wage, before.fringe) == (
        date(2025, 11, 3),
        5885,
        3465,
    )
    assert (after.row.effective, after.wage, after.fringe) == (INCREASE, 6110, 3540)
    assert after.row.total == 9650


def test_a_statewide_crafts_rates_are_the_same_in_every_county():
    for county in ("Middlesex", "Monmouth", "Ocean"):
        work = Work("laborer", "journeyman", county, LINCOLN_AWARD)
        found = wage_rules.required_rate(RATES, work, MONDAY)
        assert (found.determination.id, found.wage) == ("STW-2026-01", 4495)


def test_every_rows_total_is_its_wage_and_fringe():
    rates = payroll_files.FILES[payroll_files.RATE_DETERMINATIONS]
    for found in rates["determinations"]:
        for rate in found["rates"]:
            for row in rate["rows"]:
                assert row["total"] == row["wage"] + row["fringe"]


def test_a_rate_that_isnt_there_is_a_lookup_error():
    with pytest.raises(LookupError):
        electrician(MONDAY, award=date(2024, 1, 2))
    with pytest.raises(LookupError):
        electrician(date(2025, 1, 6), award=date(2025, 12, 1))
    no_level = Work("electrician", "apprentice", "Middlesex", LINCOLN_AWARD)
    with pytest.raises(LookupError, match="needs a level"):
        wage_rules.required_rate(RATES, no_level, MONDAY)


def test_daily_overtime_over_8_hours():
    split = wage_rules.premium_split(RATES, "electrician", week(10, 8, 8, 8, 6))
    premium = [(part.day, part.hours) for part in split if part.premium != STRAIGHT]
    assert premium == [(MONDAY, 2)]
    assert wage_rules.premium_hours(split) == 2


def test_saturday_at_time_and_a_half_and_a_holiday_at_double_time():
    saturday = wage_rules.premium_split(RATES, "painter", week(8, 8, 8, 8, 8, 4))
    assert saturday[-1].hours == 4
    assert saturday[-1].premium == Premium(TIME_AND_A_HALF, Decimal(1))
    sunday = [(MONDAY + timedelta(6), Decimal(6))]
    [on_sunday] = wage_rules.premium_split(RATES, "plumber", sunday)
    assert on_sunday.premium == Premium(Decimal(2), Decimal(1))
    labor_day = date(2026, 9, 7)
    [holiday] = wage_rules.premium_split(RATES, "carpenter", [(labor_day, Decimal(8))])
    assert holiday.premium == Premium(Decimal(2), Decimal(2))


def test_the_40_hour_floor_when_the_crafts_rules_dont_apply():
    split = wage_rules.premium_split(RATES, "painter", week(10, 8, 8, 8, 8))
    premium = [
        (part.day, part.hours, part.premium)
        for part in split
        if part.premium != STRAIGHT
    ]
    assert premium == [(MONDAY + timedelta(4), 2, Premium(TIME_AND_A_HALF, Decimal(1)))]
    # Daily overtime already paid isn't counted toward the 40 straight hours.
    daily = wage_rules.premium_split(RATES, "plumber", week(10, 10, 10, 10, 2))
    assert wage_rules.premium_hours(daily) == 8


def test_fringe_is_multiplied_only_where_the_craft_says_so():
    hours = week(10, 8, 8, 8, 8)
    required = {day: 3540 for day, _ in hours}
    with_fringe = wage_rules.premium_split(RATES, "electrician", hours)
    wage_only = wage_rules.premium_split(RATES, "plumber", hours)
    # $5.40 short on 42 hours, 2 of them at time and a half on the fringe too.
    assert wage_rules.fringe_shortfall(with_fringe, required, 3000) == 540 * 43
    assert wage_rules.fringe_shortfall(wage_only, required, 3000) == 540 * 42


def test_the_apprentice_rate_by_level():
    level_2 = electrician(INCREASE, level=2)
    # 49% of $61.10 and of $35.40, each to the cent.
    assert (level_2.wage, level_2.fringe) == (2994, 1735)
    carpenter = wage_rules.required_rate(
        RATES, Work("carpenter", "apprentice", "Middlesex", LINCOLN_AWARD, 1), MONDAY
    )
    assert (carpenter.wage, carpenter.fringe) == (2756, 3376)
    # 58% of $58.85 is $34.133, and of $34.65 is $20.097.
    level_3 = electrician(INCREASE - timedelta(days=1), level=3)
    assert (level_3.wage, level_3.fringe) == (3413, 2010)
    # Half a cent rounds up: 50% of $57.05 is $28.525.
    row = wage_rules.Row(MONDAY, 5705, 4120)
    assert wage_rules.apprentice_rate(RATES.crafts["carpenter"], row, 1)[0] == 2853


def test_the_base_shortfall_at_each_hours_premium():
    hours = week(10, 8, 8, 8, 8)
    split = wage_rules.premium_split(RATES, "electrician", hours)
    required = {day: 6110 for day, _ in hours}
    # $1.10 short on 40 straight hours and 2 at time and a half.
    assert wage_rules.base_shortfall(split, required, 6000) == 110 * 40 + 165 * 2
    assert wage_rules.base_shortfall(split, required, 6110) == 0


def test_the_overtime_shortfall_on_hours_paid_straight():
    split = wage_rules.premium_split(RATES, "electrician", week(8, 8, 8, 8, 8, 4))
    # Half of $61.10 and of $35.40 on each of the 4 Saturday hours.
    assert wage_rules.overtime_shortfall(split, Decimal(0), 6110, 3540) == 4825 * 4
    assert wage_rules.overtime_shortfall(split, Decimal(4), 6110, 3540) == 0
    assert wage_rules.overtime_shortfall(split, Decimal(6), 6110, 3540) == 0
    painter = wage_rules.premium_split(RATES, "painter", week(8, 8, 8, 8, 8, 4))
    assert wage_rules.overtime_shortfall(painter, Decimal(1), 4790, 2660) == 2395 * 3


def test_the_overtime_shortfall_on_double_time():
    [holiday] = wage_rules.premium_split(
        RATES, "painter", [(date(2026, 9, 7), Decimal(8))]
    )
    # Time and a half paid on a holiday at double time leaves half the wage unpaid.
    assert wage_rules.overtime_shortfall([holiday], Decimal(8), 4790, 2660) == 2395 * 8
    assert wage_rules.overtime_shortfall([holiday], Decimal(0), 4790, 2660) == 4790 * 8


def test_the_unregistered_apprentices_shortfall():
    hours = week(8, 8, 8, 8, 8)
    split = wage_rules.premium_split(RATES, "electrician", hours)
    journeyman = electrician(INCREASE)
    apprentice = electrician(INCREASE, level=2)
    wage = {day: journeyman.wage for day, _ in hours}
    fringe = {day: journeyman.fringe for day, _ in hours}
    short = wage_rules.base_shortfall(split, wage, apprentice.wage)
    short += wage_rules.fringe_shortfall(split, fringe, apprentice.fringe)
    assert short == (6110 - 2994 + 3540 - 1735) * 40


def test_gross_and_the_rounding_rule():
    assert wage_rules.gross(6110, Decimal(42), Decimal(2)) == 6110 * 42 + 6110
    assert wage_rules.gross(4795, Decimal("7.25"), Decimal(0)) == 34764
    assert wage_rules.to_cents(Decimal("2.5")) == 3
    assert wage_rules.to_cents(Decimal("3.5")) == 4
    assert wage_rules.to_cents(Decimal("1.49")) == 1


def test_the_apprentice_ratio():
    assert wage_rules.ratio_allows(RATES, "electrician", 1, 2)
    assert not wage_rules.ratio_allows(RATES, "electrician", 1, 1)
    assert wage_rules.ratio_allows(RATES, "carpenter", 1, 2)
    assert not wage_rules.ratio_allows(RATES, "carpenter", 2, 3)
