"""Overtime: each line pays as overtime every hour its craft's rules give a
premium (over 8 hours a day, Saturdays, Sundays and holidays), with the state's
40-hour weekly floor."""

from agent.checks import pay
from agent.checks.findings import OVERTIME, Finding, Parameters, hours
from agent.checks.inputs import CheckInputs
from context import wage_rules


def check(inputs: CheckInputs, parameters: Parameters) -> list[Finding]:
    found = []
    for line in inputs.lines:
        claimed = line.claimed
        if claimed is None or line.misclassified:
            continue
        split = pay.split(claimed, line)
        premium = wage_rules.premium_hours(split)
        paid = line.line.overtime_hours
        if paid >= premium:
            continue
        short = wage_rules.overtime_shortfall(
            split, paid, line.line.base_rate, line.line.fringe_paid
        )
        if parameters.owed(short):
            found.append(
                Finding(
                    OVERTIME,
                    line.line.worker_id,
                    line.line_no,
                    f"{hours(premium)} at a premium",
                    f"{hours(paid)} paid as overtime",
                    short,
                    f"{claimed.citation()}: its overtime rules, and the state's "
                    "40-hour weekly floor",
                )
            )
    return found
