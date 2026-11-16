"""The rule catalogue: the 15 rule codes an exception can have, each with the check
that finds it, its severity, whether it carries money, whether it is a worker's
line's or the whole payroll's, and what an exception seeded from the history or
added by a reviewer cites."""

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
        FORM, Severity.MEDIUM, False, "MW-562 payroll certification", False
    ),
    "form.unsigned": Rule(
        FORM, Severity.HIGH, False, "MW-562 payroll certification", False
    ),
    "form.project_mismatch": Rule(
        FORM, Severity.MEDIUM, False, "Our project and subcontractor records", False
    ),
    "registration.inactive": Rule(
        REGISTRATION,
        Severity.HIGH,
        False,
        "Contractor registry; N.J.S.A. 34:11-56.51",
        False,
    ),
    "rate.base_short": Rule(RATES, Severity.HIGH, True, RATE_DETERMINATION, True),
    "rate.fringe_short": Rule(RATES, Severity.HIGH, True, RATE_DETERMINATION, True),
    "overtime.underpaid": Rule(
        OVERTIME,
        Severity.HIGH,
        True,
        f"{RATE_DETERMINATION}: the craft's overtime rules",
        True,
    ),
    "arithmetic.hours_total": Rule(
        ARITHMETIC, Severity.MEDIUM, False, "MW-562 payroll register", True
    ),
    "arithmetic.gross": Rule(
        ARITHMETIC, Severity.HIGH, True, "MW-562 payroll register", True
    ),
    "apprentice.unregistered": Rule(
        APPRENTICES,
        Severity.HIGH,
        True,
        f"Apprentice registrations; {RATE_DETERMINATION}",
        True,
    ),
    "apprentice.ratio": Rule(
        APPRENTICES, Severity.MEDIUM, False, "N.J.A.C. 12:60-6.3", False
    ),
    "timeliness.late": Rule(
        TIMELINESS,
        Severity.MEDIUM,
        False,
        "N.J.S.A. 34:11-56.29(b)(2); N.J.A.C. 12:60-5.1(c)(1)(i)",
        False,
    ),
    "sequence.gap": Rule(
        TIMELINESS, Severity.LOW, False, 'MW-562 "Payroll No."', False
    ),
    "classification.changed": Rule(
        CLASSIFICATION, Severity.LOW, False, "Last week's payroll of record", True
    ),
    "classification.mismatch": Rule(
        CLASSIFICATION,
        Severity.HIGH,
        True,
        f"Our worker records, the established craft; {RATE_DETERMINATION}",
        True,
    ),
}
