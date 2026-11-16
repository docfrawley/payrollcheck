"""A world's expected filings: every week of every engagement window, each under
the case id its week and pair give it."""

from dataclasses import dataclass
from datetime import date

from data.payroll_world.world import Engagement, World


@dataclass(frozen=True)
class Filing:
    case_id: str
    engagement: Engagement
    week: int
    week_ending: date


def filings(world: World) -> list[Filing]:
    """Every expected filing, in case id order."""
    found = [
        Filing(world.case_id(e, week), e, week, world.week_ending(week))
        for e in world.engagements
        for week in range(e.first_week, e.last_week + 1)
    ]
    return sorted(found, key=lambda filing: filing.case_id)
