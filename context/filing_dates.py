"""When a payroll is late, written once for the payroll agent's timeliness check, the
Copilot's late and missing filings and the generator's expected answers. A payroll
is filed when its first submission is received, since a correction amends the
filing rather than making a new one: a correction never makes a payroll late, and
never makes a late one on time. It is late when that first submission is received
more than the filing rules' due days after its wages were paid, and an expected
payroll with no submission is late once its week ending and the due days have
passed, since no wages are paid before the week ends. It needs no packages, so the
app's function and the agent's runtime each ship it beside their own code."""

from datetime import date, timedelta


def days_after_payment(paid_on: date, filed_on: date) -> int:
    """The days from the wages paid to the payroll's filing, its first submission's
    received date."""
    return (filed_on - paid_on).days


def late(paid_on: date, filed_on: date, due_days: int) -> bool:
    """Whether a payroll filed on a date, its first submission's, was filed late."""
    return days_after_payment(paid_on, filed_on) > due_days


def deadline(week_ending: date, due_days: int) -> date:
    """The earliest a payroll not yet filed is late after: its week ending and the
    due days, since its wages are paid on the week ending at the soonest."""
    return week_ending + timedelta(days=due_days)
