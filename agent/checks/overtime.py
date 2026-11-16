"""Overtime: each line pays as overtime every hour its craft's rules give a
premium (over 8 hours a day, Saturdays, Sundays and holidays), with the state's
40-hour weekly floor, by the rules of the craft it's paid as or, paid as a
lower-paid craft, the worker's established one."""

from agent.checks import pay
from agent.checks.findings import OVERTIME, Finding, Parameters, hours
from agent.checks.inputs import CheckInputs
from context import wage_rules


def check(inputs: CheckInputs, parameters: Parameters) -> list[Finding]:
    found = []
    for line in inputs.lines:
        # A line paid as a lower-paid craft owes the premium by the rules of the
        # worker's established craft; the classification check finds the rest.
        requirement = line.established if line.misclassified else line.claimed
        if requirement is None:
            continue
        split = pay.split(requirement, line)
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
                    f"{requirement.citation()}: its overtime rules, and the state's "
                    "40-hour weekly floor",
                )
            )
    return found
