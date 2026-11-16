"""Pass two: the manifest's errors applied to a clean payroll, each corrupting it
one way, with the ground-truth label each error leaves. Every expected shortfall is
worked out by the one rate logic from the line as corrupted, against what the
worker's days are owed. A hidden instruction goes into its text cell and is
labelled as a screening flag."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Decimal
from typing import Any

from context import wage_rules
from context.wage_rules import APPRENTICE
from data.payroll_world import rules
from data.payroll_world.classifications import classification_text
from data.payroll_world.clean import (
    owed_works,
    paid_correctly,
    payroll_lines,
    with_hours,
    with_pay,
    works_as,
)
from data.payroll_world.determinations import RATES
from data.payroll_world.filings import Filing
from data.payroll_world.manifest import Error, HiddenInstruction
from data.payroll_world.template import Line, Payroll
from data.payroll_world.world import World

Given = dict[str, Any]


@dataclass(frozen=True)
class Label:
    """What a perfect review finds: the case, the rule, the worker and line for a
    rule about a line, and the shortfall in cents where money is owed."""

    case_id: str
    rule: str
    worker_id: str | None
    line_no: int | None
    expected_shortfall_cents: int | None


@dataclass(frozen=True)
class Seeded:
    """A filing with its errors: the payroll as first filed, the clean payroll a
    correction would send, the labels, and how many days after the wage payment
    date a late history filing was received."""

    filed: Payroll
    corrected: Payroll
    labels: tuple[Label, ...]
    late_by: int | None


def base_cut(world: World, filing: Filing, line: Line, given: Given) -> Line:
    base = line.base_rate - given["cut_cents"]
    return with_pay(line, base, line.fringe_rate, line.fringe_cash, line.overtime_hours)


def fringe_cut(world: World, filing: Filing, line: Line, given: Given) -> Line:
    fringe = line.fringe_rate - given["cut_cents"]
    return with_pay(line, line.base_rate, fringe, line.fringe_cash, line.overtime_hours)


def overtime_at_straight_time(
    world: World, filing: Filing, line: Line, given: Given
) -> Line:
    return with_pay(
        line, line.base_rate, line.fringe_rate, line.fringe_cash, Decimal(0)
    )


def wrong_total(world: World, filing: Filing, line: Line, given: Given) -> Line:
    return replace(line, total_hours=Decimal(str(given["total_hours"])))


def gross_cut(world: World, filing: Filing, line: Line, given: Given) -> Line:
    gross = line.gross - given["cut_cents"]
    return replace(line, gross=gross, net=gross - line.deductions)


def apprentice_rate(world: World, filing: Filing, line: Line, given: Given) -> Line:
    """The line paid the apprentice rate at its level, registered or not."""
    craft = world.worker(line.worker_id).craft
    works = works_as(world, filing, craft, APPRENTICE, line.apprentice_level)
    return paid_correctly(line, craft, works)


def paid_as(world: World, filing: Filing, line: Line, given: Given) -> Line:
    """The line paid correctly as another craft or classification, given as
    craft/classification."""
    craft, classification = given["paid_as"].split("/")
    works = works_as(world, filing, craft, classification, None)
    paid = paid_correctly(line, craft, works)
    return replace(paid, classification=classification_text(craft, classification))


def blank_field(
    world: World, filing: Filing, payroll: Payroll, given: Given
) -> Payroll:
    cert = replace(payroll.certification, **{given["field"]: ""})
    return replace(payroll, certification=cert)


def unsigned(world: World, filing: Filing, payroll: Payroll, given: Given) -> Payroll:
    cert = replace(payroll.certification, signed_by="", signed_on=None)
    return replace(payroll, certification=cert)


def worked_unregistered(
    world: World, filing: Filing, payroll: Payroll, given: Given
) -> Payroll:
    """The crew's work on the days the subcontractor wasn't registered, paid."""
    lines = tuple(payroll_lines(world, filing, registered_only=False))
    cert = replace(payroll.certification, no_work_week=False)
    return replace(payroll, certification=cert, lines=lines)


def journeyman_absent(
    world: World, filing: Filing, payroll: Payroll, given: Given
) -> Payroll:
    return payroll.without(given["absent"])


def number_skipped(
    world: World, filing: Filing, payroll: Payroll, given: Given
) -> Payroll:
    cert = payroll.certification
    return replace(payroll, certification=replace(cert, payroll_no=cert.payroll_no + 1))


def late(world: World, filing: Filing, payroll: Payroll, given: Given) -> Payroll:
    """A late filing: received late, which the lifecycle dates, or in the last week
    with a wage payment date more than the due days before it was received."""
    if "wage_paid_days_before" not in given:
        return payroll
    paid_on = world.spec.business_date - timedelta(days=given["wage_paid_days_before"])
    cert = replace(payroll.certification, wage_payment_date=paid_on)
    return replace(payroll, certification=cert)


LINE_CORRUPTIONS: dict[str, Callable[[World, Filing, Line, Given], Line]] = {
    rules.BASE_SHORT: base_cut,
    rules.FRINGE_SHORT: fringe_cut,
    rules.OVERTIME: overtime_at_straight_time,
    rules.HOURS_TOTAL: wrong_total,
    rules.GROSS: gross_cut,
    rules.UNREGISTERED: apprentice_rate,
    rules.MISMATCH: paid_as,
    rules.CHANGED: paid_as,
}
PAYROLL_CORRUPTIONS: dict[str, Callable[[World, Filing, Payroll, Given], Payroll]] = {
    rules.MISSING_FIELD: blank_field,
    rules.UNSIGNED: unsigned,
    rules.INACTIVE: worked_unregistered,
    rules.RATIO: journeyman_absent,
    rules.GAP: number_skipped,
    rules.LATE: late,
}


def shaped(world: World, filing: Filing, payroll: Payroll, error: Error) -> Payroll:
    """The clean payroll an error is seeded on: its line with the hours the error
    gives, paid correctly."""
    if error.hours is None or error.worker is None:
        return payroll
    line = with_hours(world, filing, payroll.line_of(error.worker), error.hours)
    return payroll.with_line(line)


def shortfall(world: World, filing: Filing, line: Line, rule: str) -> int | None:
    """What a line leaves unpaid under a rule, against what its worker's days are
    owed: their established craft and classification, an unregistered apprentice
    as a journeyman."""
    worker = world.worker(line.worker_id)
    works = owed_works(world, filing, worker)
    days = list(zip(works, line.hours, strict=True))
    rates = {
        day: wage_rules.required_rate(RATES, works[day], day) for day, h in days if h
    }
    wage = {day: rate.wage for day, rate in rates.items()}
    fringe = {day: rate.fringe for day, rate in rates.items()}
    split = wage_rules.premium_split(RATES, worker.craft, days)
    paid_fringe = line.fringe_rate + line.fringe_cash
    base_short = wage_rules.base_shortfall(split, wage, line.base_rate)
    fringe_short = wage_rules.fringe_shortfall(split, fringe, paid_fringe)
    match rule:
        case rules.BASE_SHORT:
            return base_short
        case rules.FRINGE_SHORT:
            return fringe_short
        case rules.UNREGISTERED | rules.MISMATCH:
            return base_short + fringe_short
        case rules.OVERTIME:
            return wage_rules.overtime_shortfall(
                split, line.overtime_hours, line.base_rate, paid_fringe
            )
        case rules.GROSS:
            total = sum(line.hours, Decimal(0))
            return (
                wage_rules.gross(line.base_rate, total, line.overtime_hours)
                - line.gross
            )
    return None


def label(world: World, filing: Filing, payroll: Payroll, error: Error) -> Label:
    if error.worker is None:
        return Label(filing.case_id, error.rule, None, None, None)
    lines = [line.worker_id for line in payroll.lines]
    line = payroll.line_of(error.worker)
    return Label(
        filing.case_id,
        error.rule,
        error.worker,
        lines.index(error.worker) + 1,
        shortfall(world, filing, line, error.rule),
    )


def seed_errors(
    world: World, filing: Filing, clean: Payroll, errors: list[Error]
) -> Seeded:
    """A filing's payroll with its errors, the clean payroll they were seeded on and
    their labels."""
    corrected = clean
    for error in errors:
        corrected = shaped(world, filing, corrected, error)
    filed = corrected
    for error in errors:
        if error.worker is None:
            corrupt = PAYROLL_CORRUPTIONS[error.rule]
            filed = corrupt(world, filing, filed, error.given)
        else:
            line = filed.line_of(error.worker)
            filed = filed.with_line(
                LINE_CORRUPTIONS[error.rule](world, filing, line, error.given)
            )
    labels = tuple(label(world, filing, filed, error) for error in errors)
    late = [e.given["days_after"] for e in errors if "days_after" in e.given]
    return Seeded(filed, corrected, labels, late[0] if late else None)


def hide_instruction(payroll: Payroll, hidden: HiddenInstruction) -> Payroll:
    """A payroll with the instruction in its text cell."""
    if hidden.worker is None:
        cert = replace(payroll.certification, **{hidden.column: hidden.text})
        return replace(payroll, certification=cert)
    line = replace(payroll.line_of(hidden.worker), **{hidden.column: hidden.text})
    return payroll.with_line(line)
