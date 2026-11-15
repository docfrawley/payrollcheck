"""The decoys: clean payrolls shaped to look wrong, each kept correct by the one
rate logic. A decoy gives the payrolls its case is filed with, two for a corrected
resubmission, and leaves no label."""

from collections.abc import Callable
from dataclasses import replace

from data.payroll_world import rules
from data.payroll_world.classifications import classification_text
from data.payroll_world.clean import paid_correctly, with_hours, works_as
from data.payroll_world.filings import Filing
from data.payroll_world.manifest import Decoy, ManifestError
from data.payroll_world.template import Payroll
from data.payroll_world.world import World


def worked(
    world: World, filing: Filing, payroll: Payroll, decoy: Decoy
) -> list[Payroll]:
    """A line with the hours the decoy gives, paid correctly: a day over 8 hours or
    a Saturday in a week under 40, or the week of a rate increase worked before the
    increase."""
    if decoy.hours is None:
        raise ManifestError(f"{decoy.case}: the {decoy.kind} decoy needs its hours")
    line = with_hours(world, filing, payroll.line_of(decoy.worker), decoy.hours)
    return [payroll.with_line(line)]


def as_it_is(
    world: World, filing: Filing, payroll: Payroll, decoy: Decoy
) -> list[Payroll]:
    """A clean payroll that already looks wrong: the award date's rates below a
    later determination's, or an apprentice paid at their level."""
    return [payroll]


def noted_change(
    world: World, filing: Filing, payroll: Payroll, decoy: Decoy
) -> list[Payroll]:
    """A worker paid correctly as another classification of their craft, with a line
    note that says why."""
    worker = world.worker(decoy.worker)
    classification = decoy.given["classification"]
    works = works_as(world, filing, worker.craft, classification, None)
    line = paid_correctly(payroll.line_of(decoy.worker), worker.craft, works)
    text = classification_text(worker.craft, classification)
    noted = replace(line, classification=text, line_notes=decoy.given["note"])
    return [payroll.with_line(noted)]


def no_work(
    world: World, filing: Filing, payroll: Payroll, decoy: Decoy
) -> list[Payroll]:
    cert = replace(payroll.certification, no_work_week=True)
    return [replace(payroll, certification=cert, lines=())]


def resubmitted(
    world: World, filing: Filing, payroll: Payroll, decoy: Decoy
) -> list[Payroll]:
    """A payroll filed first without a worker, then again in full as its
    correction."""
    return [payroll.without(decoy.worker), payroll]


def renamed(
    world: World, filing: Filing, payroll: Payroll, decoy: Decoy
) -> list[Payroll]:
    """The contractor's name as the subcontractor writes it, not as its legal name."""
    cert = replace(payroll.certification, contractor_name=decoy.given["name"])
    return [replace(payroll, certification=cert)]


def cash_fringe(
    world: World, filing: Filing, payroll: Payroll, decoy: Decoy
) -> list[Payroll]:
    """Part of a line's fringe paid in cash in lieu of benefits."""
    line = payroll.line_of(decoy.worker)
    cash = decoy.given["cash_cents"]
    paid = replace(line, fringe_rate=line.fringe_rate - cash, fringe_cash=cash)
    return [payroll.with_line(paid)]


SHAPES: dict[str, Callable[[World, Filing, Payroll, Decoy], list[Payroll]]] = {
    rules.DAILY_OVERTIME: worked,
    rules.RATE_INCREASE_WEEK: worked,
    rules.SATURDAY_OVERTIME: worked,
    rules.LATER_DETERMINATION: as_it_is,
    rules.APPRENTICE_AT_LEVEL: as_it_is,
    rules.CLASSIFICATION_NOTE: noted_change,
    rules.NO_WORK_WEEK: no_work,
    rules.CORRECTED_RESUBMISSION: resubmitted,
    rules.NAME_VARIANT: renamed,
    rules.CASH_IN_LIEU: cash_fringe,
}


def shape_decoy(
    world: World, filing: Filing, payroll: Payroll, decoy: Decoy
) -> list[Payroll]:
    """The payrolls a decoy's case is filed with."""
    return SHAPES[decoy.kind](world, filing, payroll, decoy)
