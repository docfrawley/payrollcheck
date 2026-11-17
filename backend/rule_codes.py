"""The rule catalogue: the 15 rule codes an exception can have, each with the check
that finds it, its severity, whether it carries money, whether it is a worker's
line's or the whole payroll's, and what an exception seeded from the history or
added by a reviewer cites, with what a send-back notice calls it and asks the
subcontractor to correct."""

from enum import StrEnum
from typing import NamedTuple


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
    ),
    "sequence.gap": Rule(
        TIMELINESS,
        Severity.LOW,
        False,
        'MW-562 "Payroll No."',
        False,
        name="A payroll number is missing from the sequence",
        asks="Send us the missing payrolls, or tell us why the payroll numbers skip.",
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
