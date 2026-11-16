"""The payroll agent's eight check tools, in the order they run: each a pure
function of what the case's latest submission and its records say, finding
candidates with every amount computed by the one rate logic."""

from collections.abc import Callable

from agent.checks import (
    apprentices,
    arithmetic,
    classification,
    form,
    overtime,
    rates,
    registration,
    timeliness,
)
from agent.checks.findings import Finding, Parameters
from agent.checks.inputs import CheckInputs

Check = Callable[[CheckInputs, Parameters], list[Finding]]
CHECKS: tuple[tuple[str, Check], ...] = (
    ("check_form", form.check),
    ("check_contractor_registration", registration.check),
    ("check_rates", rates.check),
    ("check_overtime", overtime.check),
    ("check_arithmetic", arithmetic.check),
    ("check_apprentices", apprentices.check),
    ("check_timeliness", timeliness.check),
    ("check_classification", classification.check),
)
