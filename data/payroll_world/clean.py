"""Pass one: every expected filing of a world as a correct payroll. Each worker's
hours are drawn for the week, never on a Sunday, a holiday or a day the
subcontractor isn't registered, and each line is paid by the one rate logic: at
least the rate every day of its week requires, with its premium hours as overtime."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from context import wage_rules
from context.wage_rules import APPRENTICE, JOURNEYMAN, Work
from data.payroll_world.classifications import classification_text
from data.payroll_world.determinations import RATES
from data.payroll_world.draws import draw
from data.payroll_world.filings import Filing
from data.payroll_world.template import Certification, Line, Payroll
from data.payroll_world.weeks import week_days
from data.payroll_world.world import Project, Worker, World

DAY = Decimal(8)
LONG_DAY = Decimal(10)
SHORT_DAY = Decimal("7.5")
SATURDAYS = (Decimal(4), Decimal(5), Decimal(6), Decimal(8))
# A line's deductions, as a share of its gross: from 20% to 28%, in tenths of a %.
DEDUCTIONS = range(200, 281)


def planned_hours(world: World, worker: Worker, week_ending: date) -> list[Decimal]:
    """A worker's hours for a week from Monday: eight a day as a rule, a day off, a
    long or a short day now and then, sometimes a Saturday, never a Sunday or a
    holiday."""
    source = draw(world.spec.seed, "hours", worker.id, week_ending)
    hours = [DAY] * 5 + [Decimal(0)] * 2
    change = source.choice(
        (None, None, None, None, None, Decimal(0), LONG_DAY, SHORT_DAY)
    )
    if change is not None:
        hours[source.randrange(5)] = change
    if source.randrange(10) == 0:
        hours[5] = source.choice(SATURDAYS)
    return [
        Decimal(0) if day in RATES.holidays else h
        for day, h in zip(week_days(week_ending), hours, strict=True)
    ]


def works_in(worker: Worker, week: int) -> bool:
    return worker.weeks is None or worker.weeks[0] <= week <= worker.weeks[1]


def owed_work(world: World, project: Project, worker: Worker, day: date) -> Work:
    """What a worker's day on a project is owed as: their established craft and
    classification, a registered apprentice at their level that day, and one who
    isn't registered that day as a journeyman."""
    county, award = project.county, project.award_date
    if worker.classification != APPRENTICE:
        return Work(worker.craft, worker.classification, county, award)
    registration = world.apprentice(worker.id)
    level = registration.level_on(day) if registration else None
    if level is None:
        return Work(worker.craft, JOURNEYMAN, county, award)
    return Work(worker.craft, APPRENTICE, county, award, level)


def with_pay(
    line: Line, base: int, fringe_rate: int, fringe_cash: int, overtime_hours: Decimal
) -> Line:
    """A line paid at these rates and overtime hours, its gross and net worked out
    from them and its daily hours, its deductions kept."""
    total = sum(line.hours, Decimal(0))
    gross = wage_rules.gross(base, total, overtime_hours)
    return replace(
        line,
        total_hours=total,
        base_rate=base,
        fringe_rate=fringe_rate,
        fringe_cash=fringe_cash,
        overtime_hours=overtime_hours,
        gross=gross,
        net=gross - line.deductions,
    )


def paid_correctly(line: Line, craft: str, works: dict[date, Work]) -> Line:
    """A line paid what the work of each day of its week, from Monday, requires: the
    highest wage and fringe any of its work days requires, and its premium hours by
    the craft's rules as overtime."""
    worked = [(day, hours) for day, hours in zip(works, line.hours, strict=True)]
    rates = [wage_rules.required_rate(RATES, works[day], day) for day, h in worked if h]
    split = wage_rules.premium_split(RATES, craft, worked)
    base = max(rate.wage for rate in rates)
    fringe = max(rate.fringe for rate in rates)
    return with_pay(line, base, fringe, 0, wage_rules.premium_hours(split))


def with_hours(
    world: World, filing: Filing, line: Line, hours: tuple[Decimal, ...]
) -> Line:
    """A worker's line with these hours in the filing's week, paid correctly."""
    worker = world.worker(line.worker_id)
    worked = replace(line, hours=hours)
    return paid_correctly(worked, worker.craft, owed_works(world, filing, worker))


def owed_works(world: World, filing: Filing, worker: Worker) -> dict[date, Work]:
    """What each day of the filing's week is owed as, for a worker on its crew."""
    project = world.project(filing.engagement.project_id)
    return {
        day: owed_work(world, project, worker, day)
        for day in week_days(filing.week_ending)
    }


def works_as(
    world: World, filing: Filing, craft: str, classification: str, level: int | None
) -> dict[date, Work]:
    """A line's days, as paid at a classification rather than as owed."""
    project = world.project(filing.engagement.project_id)
    return {
        day: Work(craft, classification, project.county, project.award_date, level)
        for day in week_days(filing.week_ending)
    }


def clean_line(
    world: World,
    project: Project,
    worker: Worker,
    week_ending: date,
    hours: list[Decimal],
) -> Line:
    days = week_days(week_ending)
    works = {day: owed_work(world, project, worker, day) for day in days}
    registration = world.apprentice(worker.id)
    level = (
        registration.level_on(max(days)) if registration else worker.unregistered_level
    )
    source = draw(world.spec.seed, "deductions", worker.id, week_ending)
    unpaid = Line(
        worker.id,
        worker.name,
        classification_text(worker.craft, worker.classification),
        level,
        tuple(hours),
        Decimal(0),
        0,
        0,
        0,
        Decimal(0),
        0,
        0,
        0,
        "",
    )
    line = paid_correctly(unpaid, worker.craft, works)
    deductions = wage_rules.to_cents(
        line.gross * Decimal(source.choice(DEDUCTIONS)) / 1000
    )
    return replace(line, deductions=deductions, net=line.gross - deductions)


def worked_hours(
    world: World, filing: Filing, worker: Worker, registered_only: bool
) -> list[Decimal]:
    """A worker's planned hours, without the days the subcontractor isn't registered
    unless the hours worked anyway are wanted."""
    hours = planned_hours(world, worker, filing.week_ending)
    registration = world.registration(filing.engagement.subcontractor_id)
    return [
        h if registration.active_on(day) or not registered_only else Decimal(0)
        for day, h in zip(week_days(filing.week_ending), hours, strict=True)
    ]


def payroll_lines(
    world: World, filing: Filing, registered_only: bool = True
) -> list[Line]:
    """The crew's lines for the week, each paid correctly, leaving out anyone with no
    hours."""
    project = world.project(filing.engagement.project_id)
    lines = []
    for worker in world.crew(filing.engagement.pair):
        hours = worked_hours(world, filing, worker, registered_only)
        if works_in(worker, filing.week) and any(hours):
            lines.append(clean_line(world, project, worker, filing.week_ending, hours))
    return lines


def certification(world: World, filing: Filing, no_work_week: bool) -> Certification:
    sub = world.subcontractor(filing.engagement.subcontractor_id)
    paid_on = world.wage_payment_date(filing.week_ending)
    return Certification(
        sub.legal_name,
        sub.fein,
        sub.registration_no,
        filing.engagement.project_id,
        filing.week - filing.engagement.first_week + 1,
        filing.week_ending,
        paid_on,
        sub.signer,
        paid_on,
        no_work_week,
        "",
    )


def clean_payroll(world: World, filing: Filing) -> Payroll:
    """The filing's correct payroll, or its No Work Week payroll when nobody worked."""
    lines = payroll_lines(world, filing)
    return Payroll(certification(world, filing, not lines), tuple(lines))
