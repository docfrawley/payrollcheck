"""The cases a world's filings make, as seeding will load them: each case's
submissions with the dates they were received, its status, and for a history case
the reviewer who decided it and when. A history case is Accepted when it was clean,
Returned to sub and Accepted on a clean correction when its errors could be
corrected, or still Returned to sub; the last week's cases are Received on the
business date."""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from data.payroll_world.draws import draw
from data.payroll_world.filings import Filing
from data.payroll_world.template import Payroll
from data.payroll_world.world import World


class Status(StrEnum):
    RECEIVED = "Received"
    ACCEPTED = "Accepted"
    RETURNED = "Returned to sub"


class Fate(StrEnum):
    """What became of a filing: accepted as it came, sent back and accepted on its
    correction, sent back and not corrected, or waiting in the last week's wave."""

    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    RETURNED = "returned"
    WAITING = "waiting"


@dataclass(frozen=True)
class Submission:
    number: int
    payroll: Payroll
    received_on: date


@dataclass(frozen=True)
class Case:
    case_id: str
    filing: Filing
    status: Status
    submissions: tuple[Submission, ...]
    reviewer: str | None
    returned_on: date | None
    accepted_on: date | None


def waits(world: World, filing: Filing) -> bool:
    """Whether a filing's case is still waiting for review: in the last week's wave,
    or in a world with no history."""
    return not world.spec.history or filing.week == world.spec.weeks


def received_on(
    world: World, filing: Filing, payroll: Payroll, late_by: int | None
) -> date:
    """When the first submission arrived: on the business date in the last week,
    the days after the wage payment date a late filing gives, or 1 to 4 days after
    it."""
    if filing.week == world.spec.weeks:
        return world.spec.business_date
    days = late_by or draw(world.spec.seed, "received", filing.case_id).randint(1, 4)
    return payroll.certification.wage_payment_date + timedelta(days=days)


def reviewer(world: World, filing: Filing) -> str:
    """Who decided a history case: the project's reviewer, or now and then the
    compliance manager."""
    if draw(world.spec.seed, "reviewer", filing.case_id).randrange(8) == 0:
        return world.spec.compliance_manager
    return world.project(filing.engagement.project_id).reviewer


def make_case(
    world: World,
    filing: Filing,
    fate: Fate,
    payrolls: list[Payroll],
    late_by: int | None = None,
) -> Case:
    """A filing's case: a submission for each payroll its fate keeps, and the dates
    it gives, each a day or two after the one before."""
    source = draw(world.spec.seed, "lifecycle", filing.case_id)

    def later(day: date) -> date:
        return day + timedelta(days=source.randint(1, 2))

    first = received_on(world, filing, payrolls[0], late_by)
    if fate == Fate.WAITING:
        waiting = tuple(Submission(n, p, first) for n, p in enumerate(payrolls, 1))
        return Case(filing.case_id, filing, Status.RECEIVED, waiting, None, None, None)
    submissions = [Submission(1, payrolls[0], first)]
    returned = None if fate == Fate.ACCEPTED else later(first)
    if returned and fate == Fate.CORRECTED:
        submissions.append(Submission(2, payrolls[1], later(returned)))
    accepted = None if fate == Fate.RETURNED else later(submissions[-1].received_on)
    status = Status.RETURNED if fate == Fate.RETURNED else Status.ACCEPTED
    return Case(
        filing.case_id,
        filing,
        status,
        tuple(submissions),
        reviewer(world, filing),
        returned,
        accepted,
    )
