"""Registration: the subcontractor's public works contractor registration is
active on every date its workers work on the project."""

from agent.checks.findings import INACTIVE, Finding, Parameters
from agent.checks.inputs import CheckInputs


def check(inputs: CheckInputs, parameters: Parameters) -> list[Finding]:
    inactive = [day for day, found in inputs.registration.items() if not found.active]
    if not inactive:
        return []
    citations = dict.fromkeys(inputs.registration[day].citation for day in inactive)
    rule = inputs.filing_rules["registration"]
    return [
        Finding(
            INACTIVE,
            None,
            None,
            f"Registration {inputs.registration_no} active on every work date",
            f"Not active on {', '.join(day.isoformat() for day in inactive)}",
            None,
            "; ".join([*citations, rule.citation()]),
        )
    ]
