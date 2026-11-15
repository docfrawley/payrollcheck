"""A payroll week's days: Monday to Sunday, ending on its week ending."""

from datetime import date, timedelta


def week_days(week_ending: date) -> list[date]:
    return [week_ending - timedelta(days=6 - day) for day in range(7)]
