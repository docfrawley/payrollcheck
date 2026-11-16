"""Form completeness: every required field of the MW-562 certification filled in,
signed, and matching the project and the subcontractor's records."""

from agent.checks.findings import (
    MISSING_FIELD,
    PROJECT_MISMATCH,
    UNSIGNED,
    Finding,
    Parameters,
)
from agent.checks.inputs import CheckInputs

CERTIFICATION = "MW-562 payroll certification"
RECORDS = "Our project and subcontractor records"
REQUIRED = ("contractor_name", "fein", "registration_no", "project_id")


def check(inputs: CheckInputs, parameters: Parameters) -> list[Finding]:
    cert = inputs.certification
    found = []
    blank = [field for field in REQUIRED if not getattr(cert, field)]
    if blank:
        found.append(
            Finding(
                MISSING_FIELD,
                None,
                None,
                "Every required field filled in",
                f"Blank: {', '.join(blank)}",
                None,
                CERTIFICATION,
            )
        )
    unsigned = [
        name
        for name, value in (
            ("signed by", cert.signed_by),
            ("signed on", cert.signed_on),
        )
        if not value
    ]
    if unsigned:
        found.append(
            Finding(
                UNSIGNED,
                None,
                None,
                "Signed, with who signed and when",
                f"Blank: {', '.join(unsigned)}",
                None,
                CERTIFICATION,
            )
        )
    on_record = (
        ("contractor_name", inputs.legal_name),
        ("fein", inputs.fein),
        ("registration_no", inputs.registration_no),
        ("project_id", inputs.project_id),
    )
    differ = [
        (field, record)
        for field, record in on_record
        if getattr(cert, field) and getattr(cert, field) != record
    ]
    if differ:
        found.append(
            Finding(
                PROJECT_MISMATCH,
                None,
                None,
                "; ".join(f"{field}: {record}" for field, record in differ),
                "; ".join(f"{field}: {getattr(cert, field)}" for field, _ in differ),
                None,
                RECORDS,
            )
        )
    return found
