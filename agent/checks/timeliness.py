"""Timeliness and sequence: filed, its first submission received, within the filing
rules' due days of the wage payment date, as context.filing_dates decides; and
numbered in sequence from 1 in the first week of the subcontractor's engagement
window."""

from agent.checks.findings import GAP, LATE, Finding, Parameters
from agent.checks.inputs import CheckInputs
from context import filing_dates


def check(inputs: CheckInputs, parameters: Parameters) -> list[Finding]:
    cert = inputs.certification
    found = []
    paid_on, filed_on = inputs.paid_on, inputs.filed_on
    if filing_dates.late(paid_on, filed_on, inputs.due_days):
        days = filing_dates.days_after_payment(paid_on, filed_on)
        found.append(
            Finding(
                LATE,
                None,
                None,
                f"First submission received within {inputs.due_days} days of the "
                f"wages paid on {paid_on.isoformat()}",
                f"First submission received {filed_on.isoformat()}, {days} days after",
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
