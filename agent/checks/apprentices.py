"""Apprentices: anyone paid an apprentice's rate is a registered apprentice on
each work date, or is owed the journeyman rate, and each craft's apprentices are
within its ratio to its journeymen and foremen on the payroll."""

from agent.checks import pay
from agent.checks.findings import RATIO, UNREGISTERED, Finding, Parameters, hourly
from agent.checks.inputs import CheckInputs, LineInputs
from context import wage_rules
from context.wage_rules import APPRENTICE, RateTable

REGISTRATIONS = "Apprentice registrations"


def unregistered(line: LineInputs, parameters: Parameters) -> list[Finding]:
    claimed = line.claimed
    if claimed is None or line.misclassified or not line.unregistered:
        return []
    base, fringe = pay.shortfalls(claimed, line)
    if not parameters.owed(base + fringe):
        return []
    days = [day.isoformat() for day, level in line.levels.items() if level is None]
    return [
        Finding(
            UNREGISTERED,
            line.line.worker_id,
            line.line_no,
            f"The journeyman rate, {pay.required(claimed, pay.wage)} and "
            f"{pay.required(claimed, pay.fringe)} fringe",
            f"{hourly(line.line.base_rate)} and {hourly(line.line.fringe_paid)} fringe",
            base + fringe,
            f"{REGISTRATIONS}: {line.line.worker_id} not a registered apprentice on "
            f"{', '.join(days)}; {claimed.citation()}",
        )
    ]


def ratio(inputs: CheckInputs) -> list[Finding]:
    counts: dict[str, list[int]] = {}
    tables: dict[str, RateTable] = {}
    for line in inputs.lines:
        if line.claimed is None:
            continue
        craft = line.claimed.craft
        tables[craft] = line.claimed.table
        kind = 0 if line.claimed.classification == APPRENTICE else 1
        counts.setdefault(craft, [0, 0])[kind] += 1
    over = [
        (craft, apprentices, journeymen)
        for craft, (apprentices, journeymen) in counts.items()
        if not wage_rules.ratio_allows(tables[craft], craft, apprentices, journeymen)
    ]
    if not over:
        return []
    rule = inputs.filing_rules["apprentice_ratio"]
    allowed = []
    for craft, _, _ in over:
        rules = tables[craft].crafts[craft]
        allowed.append(
            f"{rules.name}: {rules.ratio_apprentices} apprentices for every "
            f"{rules.ratio_journeymen} journeymen"
        )
    return [
        Finding(
            RATIO,
            None,
            None,
            "; ".join(allowed),
            "; ".join(
                f"{tables[craft].crafts[craft].name}: apprentices {a}, journeymen "
                f"and foremen {j}"
                for craft, a, j in over
            ),
            None,
            rule.citation(),
        )
    ]


def check(inputs: CheckInputs, parameters: Parameters) -> list[Finding]:
    found = [f for line in inputs.lines for f in unregistered(line, parameters)]
    return found + ratio(inputs)
