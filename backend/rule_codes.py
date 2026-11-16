"""The rule catalogue: the 15 rule codes an exception can have, each with the check
that finds it, its severity, whether it carries money, and what an exception
seeded from the history cites."""

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
        FORM, Severity.MEDIUM, False, "MW-562 payroll certification"
    ),
    "form.unsigned": Rule(FORM, Severity.HIGH, False, "MW-562 payroll certification"),
    "form.project_mismatch": Rule(
        FORM, Severity.MEDIUM, False, "Our project and subcontractor records"
    ),
    "registration.inactive": Rule(
        REGISTRATION,
        Severity.HIGH,
        False,
        "Contractor registry; N.J.S.A. 34:11-56.51",
    ),
    "rate.base_short": Rule(RATES, Severity.HIGH, True, RATE_DETERMINATION),
    "rate.fringe_short": Rule(RATES, Severity.HIGH, True, RATE_DETERMINATION),
    "overtime.underpaid": Rule(
        OVERTIME,
        Severity.HIGH,
        True,
        f"{RATE_DETERMINATION}: the craft's overtime rules",
    ),
    "arithmetic.hours_total": Rule(
        ARITHMETIC, Severity.MEDIUM, False, "MW-562 payroll register"
    ),
    "arithmetic.gross": Rule(
        ARITHMETIC, Severity.HIGH, True, "MW-562 payroll register"
    ),
    "apprentice.unregistered": Rule(
        APPRENTICES,
        Severity.HIGH,
        True,
        f"Apprentice registrations; {RATE_DETERMINATION}",
    ),
    "apprentice.ratio": Rule(APPRENTICES, Severity.MEDIUM, False, "N.J.A.C. 12:60-6.3"),
    "timeliness.late": Rule(
        TIMELINESS,
        Severity.MEDIUM,
        False,
        "N.J.S.A. 34:11-56.29(b)(2); N.J.A.C. 12:60-5.1(c)(1)(i)",
    ),
    "sequence.gap": Rule(TIMELINESS, Severity.LOW, False, 'MW-562 "Payroll No."'),
    "classification.changed": Rule(
        CLASSIFICATION, Severity.LOW, False, "Last week's payroll of record"
    ),
    "classification.mismatch": Rule(
        CLASSIFICATION,
        Severity.HIGH,
        True,
        f"Our worker records, the established craft; {RATE_DETERMINATION}",
    ),
}
