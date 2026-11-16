"""Timeliness and sequence: received within the filing rules' due days of the wage
payment date, and numbered in sequence from 1 in the first week of the
subcontractor's engagement window."""

from agent.checks.findings import GAP, LATE, Finding, Parameters
from agent.checks.inputs import CheckInputs


def check(inputs: CheckInputs, parameters: Parameters) -> list[Finding]:
    cert = inputs.certification
    found = []
    days = (inputs.received_on - cert.wage_payment_date).days
    if days > inputs.due_days:
        found.append(
            Finding(
                LATE,
                None,
                None,
                f"Received within {inputs.due_days} days of the wages paid on "
                f"{cert.wage_payment_date.isoformat()}",
                f"Received {inputs.received_on.isoformat()}, {days} days after",
                None,
                inputs.filing_rules["due_date"].citation(),
            )
        )
    expected = (inputs.week_ending - inputs.first_week_ending).days // 7 + 1
    if cert.payroll_no != expected:
        found.append(
            Finding(
                GAP,
                None,
                None,
                f"Payroll No. {expected}, from 1 in the week ending "
                f"{inputs.first_week_ending.isoformat()}",
                f"Payroll No. {cert.payroll_no}",
                None,
                inputs.filing_rules["sequence"].citation(),
            )
        )
    return found
