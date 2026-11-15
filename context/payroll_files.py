"""The context layer's payroll files, read once when the process starts: the rate
determinations, the contractor registry, the apprentice registrations, the filing
rules and the payroll glossary. Every answer holds its sources, the files it came
from with their system, owner and review date. It reads only from its own folder
and writes nothing."""

from typing import Any

from context import wage_rules
from context.sources import read_yaml

RATE_DETERMINATIONS = "rate_determinations.yaml"
FILING_RULES = "filing_rules.yaml"
PAYROLL_GLOSSARY = "payroll_glossary.yaml"
CONTRACTOR_REGISTRY = "contractor_registry.yaml"
APPRENTICE_REGISTRATIONS = "apprentice_registrations.yaml"

FILES: dict[str, dict[str, Any]] = {
    file: read_yaml(file)
    for file in (
        RATE_DETERMINATIONS,
        CONTRACTOR_REGISTRY,
        APPRENTICE_REGISTRATIONS,
        FILING_RULES,
        PAYROLL_GLOSSARY,
    )
}
RATES = wage_rules.rate_table(FILES[RATE_DETERMINATIONS])
# A payroll is due this many calendar days after its wages are paid.
DUE_DAYS: int = FILES[FILING_RULES]["due_days"]
