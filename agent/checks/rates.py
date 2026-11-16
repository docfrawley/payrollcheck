"""Rates: each line's base wage and fringe meet the rate its craft and
classification require in the project's county on each work date, from the
determination in force on the award date. A misclassified line is owed its
established craft's rates instead, and an unregistered apprentice's shortfall is
the apprentices check's."""

from agent.checks import pay
from agent.checks.findings import BASE_SHORT, FRINGE_SHORT, Finding, Parameters, hourly
from agent.checks.inputs import CheckInputs


def check(inputs: CheckInputs, parameters: Parameters) -> list[Finding]:
    found = []
    for line in inputs.lines:
        claimed = line.claimed
        if claimed is None or line.misclassified or line.unregistered:
            continue
        base, fringe = pay.shortfalls(claimed, line)
        worker, number = line.line.worker_id, line.line_no
        if parameters.owed(base):
            found.append(
                Finding(
                    BASE_SHORT,
                    worker,
                    number,
                    pay.required(claimed, pay.wage),
                    hourly(line.line.base_rate),
                    base,
                    claimed.citation(),
                )
            )
        if parameters.owed(fringe):
            found.append(
                Finding(
                    FRINGE_SHORT,
                    worker,
                    number,
                    pay.required(claimed, pay.fringe),
                    f"{hourly(line.line.fringe_paid)}, plans and cash together",
                    fringe,
                    claimed.citation(),
                )
            )
    return found
