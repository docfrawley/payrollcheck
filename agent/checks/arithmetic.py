"""Hours and arithmetic: each line's daily hours add up to its total, and its gross
is its base rate for every hour plus half of it for each overtime hour."""

from decimal import Decimal

from agent.checks.findings import (
    GROSS,
    HOURS_TOTAL,
    Finding,
    Parameters,
    dollars,
    hours,
)
from agent.checks.inputs import CheckInputs
from context import wage_rules

REGISTER = "MW-562 payroll register"


def check(inputs: CheckInputs, parameters: Parameters) -> list[Finding]:
    found = []
    for item in inputs.lines:
        line = item.line
        total = sum(line.hours, Decimal(0))
        if total != line.total_hours:
            found.append(
                Finding(
                    HOURS_TOTAL,
                    line.worker_id,
                    item.line_no,
                    f"{hours(total)}, the daily hours added up",
                    hours(line.total_hours),
                    None,
                    f"{REGISTER}: the daily hours add up to the total",
                )
            )
        expected = wage_rules.gross(line.base_rate, total, line.overtime_hours)
        difference = expected - line.gross
        if parameters.owed(abs(difference)):
            found.append(
                Finding(
                    GROSS,
                    line.worker_id,
                    item.line_no,
                    dollars(expected),
                    dollars(line.gross),
                    difference if difference > 0 else None,
                    f"{REGISTER}: hours at the base rate, overtime at time and a half",
                )
            )
    return found
