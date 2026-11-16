"""Classification: no worker paid as a lower-paid craft than their established
one, who is owed its rates, and no change from last week's classification. A
change with a note is still found, for the payroll agent to judge whether the
note explains it."""

from agent.checks import pay
from agent.checks.findings import CHANGED, MISMATCH, Finding, Parameters
from agent.checks.inputs import CheckInputs, LineInputs

ESTABLISHED = "Our worker records, the established craft"
LAST_WEEK = "Last week's payroll of record"
UNKNOWN = "A classification the rate determinations don't have"


def misclassified(line: LineInputs, parameters: Parameters) -> list[Finding]:
    established = line.established
    if established is None or not line.misclassified:
        return []
    base, fringe = pay.shortfalls(established, line)
    if not parameters.owed(base + fringe):
        return []
    return [
        Finding(
            MISMATCH,
            line.line.worker_id,
            line.line_no,
            f"{established.text()}, {pay.required(established, pay.wage)} and "
            f"{pay.required(established, pay.fringe)} fringe",
            line.line.classification,
            base + fringe,
            f"{ESTABLISHED}; {established.citation()}",
        )
    ]


def unknown(line: LineInputs) -> list[Finding]:
    if line.claimed is not None:
        return []
    established = line.established
    return [
        Finding(
            MISMATCH,
            line.line.worker_id,
            line.line_no,
            established.text() if established else "A classification we know",
            line.line.classification,
            None,
            UNKNOWN,
        )
    ]


def changed(line: LineInputs) -> list[Finding]:
    before = line.last_week
    if before is None or before == line.line.classification or line.misclassified:
        return []
    note = line.line.line_notes
    return [
        Finding(
            CHANGED,
            line.line.worker_id,
            line.line_no,
            f"{before}, as last week",
            f'{line.line.classification}, with the note "{note}"'
            if note
            else f"{line.line.classification}, with no note",
            None,
            LAST_WEEK,
        )
    ]


def check(inputs: CheckInputs, parameters: Parameters) -> list[Finding]:
    return [
        finding
        for line in inputs.lines
        for finding in misclassified(line, parameters) + unknown(line) + changed(line)
    ]
