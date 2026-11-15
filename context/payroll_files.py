"""The context layer's payroll files, read once when the process starts: the rate
determinations, the filing rules and the payroll glossary. Every answer holds its
sources, the files it came from with their system, owner and review date. It reads
only from its own folder and writes nothing."""

from typing import Any

from context import wage_rules
from context.sources import read_yaml

RATE_DETERMINATIONS = "rate_determinations.yaml"
FILING_RULES = "filing_rules.yaml"
PAYROLL_GLOSSARY = "payroll_glossary.yaml"

FILES: dict[str, dict[str, Any]] = {
    file: read_yaml(file)
    for file in (RATE_DETERMINATIONS, FILING_RULES, PAYROLL_GLOSSARY)
}
RATES = wage_rules.rate_table(FILES[RATE_DETERMINATIONS])
