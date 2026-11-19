from datetime import date

from context import filing_dates

PAID = date(2026, 9, 14)


def test_ten_days_after_the_wages_is_on_time_and_eleven_is_late():
    assert not filing_dates.late(PAID, date(2026, 9, 24), 10)
    assert filing_dates.late(PAID, date(2026, 9, 25), 10)
    assert filing_dates.days_after_payment(PAID, date(2026, 9, 25)) == 11


def test_a_payroll_not_yet_filed_is_late_after_its_week_ending_and_the_due_days():
    assert filing_dates.deadline(date(2026, 11, 22), 10) == date(2026, 12, 2)
