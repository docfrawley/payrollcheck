"""A world's cases: every expected filing's clean payroll, made into its case by
the lifecycle."""

from data.payroll_world.clean import clean_payroll
from data.payroll_world.filings import filings
from data.payroll_world.lifecycle import Case, Fate, make_case
from data.payroll_world.world import World


def world_cases(world: World) -> tuple[Case, ...]:
    """Every filing's case, in case id order: history cases accepted as they came,
    the last week's waiting."""
    return tuple(
        make_case(
            world,
            filing,
            Fate.WAITING if filing.week == world.spec.weeks else Fate.ACCEPTED,
            [clean_payroll(world, filing)],
        )
        for filing in filings(world)
    )
