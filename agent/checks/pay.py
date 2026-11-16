"""What a line's pay leaves short against a requirement, which the rates, the
apprentices and the classification checks each compute: its hours split by the
requirement's craft, and the base and fringe shortfalls."""

from collections.abc import Callable

from agent.checks.findings import hourly
from agent.checks.inputs import DayRate, LineInputs, Requirement
from context import wage_rules
from context.wage_rules import Hours


def split(requirement: Requirement, found: LineInputs) -> list[Hours]:
    """The line's hours as straight and premium time by the craft's rules."""
    return wage_rules.premium_split(
        requirement.table, requirement.craft, list(found.days)
    )


def shortfalls(requirement: Requirement, found: LineInputs) -> tuple[int, int]:
    """The base and the fringe the line's pay leaves short of the requirement."""
    hours = split(requirement, found)
    wages = {day: rate.wage for day, rate in requirement.rates.items()}
    fringes = {day: rate.fringe for day, rate in requirement.rates.items()}
    line = found.line
    return (
        wage_rules.base_shortfall(hours, wages, line.base_rate),
        wage_rules.fringe_shortfall(hours, fringes, line.fringe_paid),
    )


def required(requirement: Requirement, part: Callable[[DayRate], int]) -> str:
    """A requirement's wage or fringe per hour, each change in the week after the
    one before."""
    rates = [part(rate) for _, rate in sorted(requirement.rates.items())]
    return " then ".join(hourly(rate) for rate in dict.fromkeys(rates))


def wage(rate: DayRate) -> int:
    return rate.wage


def fringe(rate: DayRate) -> int:
    return rate.fringe
