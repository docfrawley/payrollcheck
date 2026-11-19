"""The rule catalogue: the 15 rule codes an exception can have, each with the check
that finds it, its severity, whether it carries money, whether it is a worker's
line's or the whole payroll's, whether its check alone decides it, and what an
exception seeded from the history or added by a reviewer cites, with what a
send-back notice calls it and asks the subcontractor to correct. It also says why
an exception added without a check's finding can't be raised, and why the payroll
agent can't dismiss a finding under a rule its check alone decides."""

from collections.abc import Sequence
from enum import StrEnum
from typing import NamedTuple, Protocol


class Severity(StrEnum):
    """High for money or legal exposure, medium, low."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Rule(NamedTuple):
    check: str
    severity: Severity
    money: bool
    cites: str
    # Found on a worker's line, rather than on the payroll as a whole.
    worker: bool
    # What a send-back notice calls it, and asks the subcontractor to correct.
    name: str
    asks: str
    # Decided by its check alone: the payroll agent raises it only from the
    # check's finding, never of its own, and raises every such finding, never
    # dismissing one; a reviewer may still add or dismiss it.
    check_decides: bool = False


FORM = "check_form"
REGISTRATION = "check_contractor_registration"
RATES = "check_rates"
OVERTIME = "check_overtime"
ARITHMETIC = "check_arithmetic"
APPRENTICES = "check_apprentices"
TIMELINESS = "check_timeliness"
CLASSIFICATION = "check_classification"
# The check tools, in the order they run.
CHECKS = (
    FORM,
    REGISTRATION,
    RATES,
    OVERTIME,
    ARITHMETIC,
    APPRENTICES,
    TIMELINESS,
    CLASSIFICATION,
)
RATE_DETERMINATION = "The rate determination in force on the project's award date"

RULES = {
    "form.missing_field": Rule(
        FORM,
        Severity.MEDIUM,
        False,
        "MW-562 payroll certification",
        False,
        name="A required field of the payroll certification is missing",
        asks="Fill in every required field of the MW-562 payroll certification.",
    ),
    "form.unsigned": Rule(
        FORM,
        Severity.HIGH,
        False,
        "MW-562 payroll certification",
        False,
        name="The payroll certification isn't signed",
        asks="Sign and date the MW-562 payroll certification.",
    ),
    "form.project_mismatch": Rule(
        FORM,
        Severity.MEDIUM,
        False,
        "Our project and subcontractor records",
        False,
        name="The certification doesn't match our project records",
        asks=(
            "Give the project, your firm's legal name, FEIN and registration number "
            "exactly as they are on the contract."
        ),
    ),
    "registration.inactive": Rule(
        REGISTRATION,
        Severity.HIGH,
        False,
        "Contractor registry; N.J.S.A. 34:11-56.51",
        False,
        name="Your public works contractor registration wasn't active",
        asks=(
            "Send us proof of an active public works contractor registration for every "
            "work date on this payroll."
        ),
    ),
    "rate.base_short": Rule(
        RATES,
        Severity.HIGH,
        True,
        RATE_DETERMINATION,
        True,
        name="The base rate paid is below the prevailing wage",
        asks=(
            "Pay the worker the difference up to the base rate for their craft, and "
            "show it on the corrected payroll."
        ),
    ),
    "rate.fringe_short": Rule(
        RATES,
        Severity.HIGH,
        True,
        RATE_DETERMINATION,
        True,
        name="The fringe benefits paid are below the prevailing wage",
        asks=(
            "Pay the fringe benefits owed, in cash or to the benefit plan, and show "
            "them on the corrected payroll."
        ),
    ),
    "overtime.underpaid": Rule(
        OVERTIME,
        Severity.HIGH,
        True,
        f"{RATE_DETERMINATION}: the craft's overtime rules",
        True,
        name="Overtime wasn't paid at the premium rate",
        asks=(
            "Pay the overtime hours at the premium rate the craft's rate sheet sets, "
            "and pay the difference."
        ),
    ),
    "arithmetic.hours_total": Rule(
        ARITHMETIC,
        Severity.MEDIUM,
        False,
        "MW-562 payroll register",
        True,
        name="The daily hours don't add up to the total",
        asks="Correct the daily hours or the total so that they agree.",
    ),
    "arithmetic.gross": Rule(
        ARITHMETIC,
        Severity.HIGH,
        True,
        "MW-562 payroll register",
        True,
        name="The gross pay doesn't match the hours and rates",
        asks=(
            "Correct the gross pay to the hours worked times the rates paid, and pay "
            "any difference."
        ),
    ),
    "apprentice.unregistered": Rule(
        APPRENTICES,
        Severity.HIGH,
        True,
        f"Apprentice registrations; {RATE_DETERMINATION}",
        True,
        name="A worker paid as an apprentice isn't registered",
        asks=(
            "Pay the worker the journeyman rate for these hours, or send us their "
            "apprentice registration for the work dates."
        ),
    ),
    "apprentice.ratio": Rule(
        APPRENTICES,
        Severity.MEDIUM,
        False,
        "N.J.A.C. 12:60-6.3",
        False,
        name="There are more apprentices than the craft's ratio allows",
        asks=(
            "Add the journeymen who worked and were left off, or pay the hours over the"
            " ratio at the journeyman rate."
        ),
    ),
    "timeliness.late": Rule(
        TIMELINESS,
        Severity.MEDIUM,
        False,
        "N.J.S.A. 34:11-56.29(b)(2); N.J.A.C. 12:60-5.1(c)(1)(i)",
        False,
        name="The payroll was filed late",
        asks="File each certified payroll within 10 days of paying the wages.",
        check_decides=True,
    ),
    "sequence.gap": Rule(
        TIMELINESS,
        Severity.LOW,
        False,
        'MW-562 "Payroll No."',
        False,
        name="A payroll number is missing from the sequence",
        asks="Send us the missing payrolls, or tell us why the payroll numbers skip.",
        check_decides=True,
    ),
    "classification.changed": Rule(
        CLASSIFICATION,
        Severity.LOW,
        False,
        "Last week's payroll of record",
        True,
        name="A worker's classification changed from last week without a note",
        asks="Tell us why the worker's classification changed, or correct it.",
    ),
    "classification.mismatch": Rule(
        CLASSIFICATION,
        Severity.HIGH,
        True,
        f"Our worker records, the established craft; {RATE_DETERMINATION}",
        True,
        name="A worker was paid under a lower classification than their craft",
        asks=(
            "Pay the worker under their established craft's classification and rates, "
            "and pay the difference."
        ),
    ),
}


NEEDS_A_WORKER = "{rule} is found on a worker's line: give the worker and the line"
NOT_THEIR_LINE = "Line {line_no} of the latest submission isn't {worker_id}'s"
NO_WORKER = "{rule} is about the whole payroll: give no worker or line"
NEEDS_A_SHORTFALL = "{rule} carries money: give a shortfall above $0.00"
NO_SHORTFALL = "{rule} carries no money: give no shortfall"
MONEY_RULE = (
    "A {rule} exception{where} carries money: it must be one a check tool found, "
    "raised by its candidate id"
)
DECIDED_BY_CHECK = (
    "{rule} is decided by {check} alone: raise its finding by its candidate id, "
    "or add none when it found nothing"
)
NOT_YOURS_TO_DISMISS = (
    "Candidate {candidate_id}, {rule}, is decided by {check} alone: raise it, and "
    "a reviewer may dismiss it"
)


class Addition(Protocol):
    """An exception added without a check's finding, as a reviewer's override or
    the payroll agent's report gives it."""

    @property
    def rule(self) -> str: ...
    @property
    def worker_id(self) -> str | None: ...
    @property
    def line_no(self) -> int | None: ...
    @property
    def shortfall_cents(self) -> int | None: ...


def where(added: Addition) -> str:
    """Where an exception is, for a refusal: its worker and line, or nothing for a
    rule about the whole payroll."""
    if added.worker_id is None:
        return ""
    return f" for {added.worker_id} on line {added.line_no}"


def agents_refusal(added: Addition, workers_by_line: Sequence[str]) -> str | None:
    """Why the payroll agent can't add this exception of its own judgment, or None
    when it can: not under a rule its check alone decides, not under one that
    carries money, and with a worker and line that fit the rule and the latest
    submission, whose worker ids by line are given."""
    return not_the_agents(added) or out_of_place(added, workers_by_line)


def agents_dismissal_refusal(candidate_id: int, rule: str) -> str | None:
    """Why the payroll agent can't dismiss a check's finding under this rule, or
    None when it can: a rule its check alone decides is the check's, and a
    reviewer's to dismiss."""
    found = RULES[rule]
    if found.check_decides:
        return NOT_YOURS_TO_DISMISS.format(
            candidate_id=candidate_id, rule=rule, check=found.check
        )
    return None


def reviewers_refusal(added: Addition, workers_by_line: Sequence[str]) -> str | None:
    """Why a reviewer can't add this exception as an override, or None when they
    can: a worker and line that fit the rule and the latest submission, and a
    shortfall above $0.00 just when the rule carries money."""
    return out_of_place(added, workers_by_line) or wrong_shortfall(added)


def not_the_agents(added: Addition) -> str | None:
    """Why the payroll agent can't add this of its own judgment, or None."""
    found = RULES[added.rule]
    if found.check_decides:
        return DECIDED_BY_CHECK.format(rule=added.rule, check=found.check)
    if found.money:
        return MONEY_RULE.format(rule=added.rule, where=where(added))
    return None


def out_of_place(added: Addition, workers_by_line: Sequence[str]) -> str | None:
    """Why the worker and line don't fit the rule or the latest submission, or
    None."""
    worker_id, line_no = added.worker_id, added.line_no
    if not RULES[added.rule].worker:
        if worker_id is not None or line_no is not None:
            return NO_WORKER.format(rule=added.rule)
        return None
    if worker_id is None or line_no is None:
        return NEEDS_A_WORKER.format(rule=added.rule)
    if (
        1 <= line_no <= len(workers_by_line)
        and workers_by_line[line_no - 1] == worker_id
    ):
        return None
    return NOT_THEIR_LINE.format(line_no=line_no, worker_id=worker_id)


def wrong_shortfall(added: Addition) -> str | None:
    """Why a reviewer's shortfall doesn't fit the rule, or None: one above $0.00
    just when the rule carries money."""
    shortfall = added.shortfall_cents
    if RULES[added.rule].money and (shortfall is None or shortfall <= 0):
        return NEEDS_A_SHORTFALL.format(rule=added.rule)
    if not RULES[added.rule].money and shortfall is not None:
        return NO_SHORTFALL.format(rule=added.rule)
    return None
