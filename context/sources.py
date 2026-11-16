"""What every answer of the context layer names: the files its content came from,
each with that file's system, owner and review date. It reads only from its own
folder and writes nothing."""

from pathlib import Path
from typing import Any

import yaml

FOLDER = Path(__file__).parent
# What every file of PayrollCheck's synthetic reference data says it is.
SYNTHETIC = "Synthetic data — not real rates"
# The payroll files. The first three are written by data/generate.py, so their
# names are here, where nothing is read as they are imported.
RATE_DETERMINATIONS = "rate_determinations.yaml"
CONTRACTOR_REGISTRY = "contractor_registry.yaml"
APPRENTICE_REGISTRATIONS = "apprentice_registrations.yaml"
FILING_RULES = "filing_rules.yaml"
PAYROLL_GLOSSARY = "payroll_glossary.yaml"


class Refused(Exception):
    """A lookup the context layer refuses, with its reason."""


def file_source(file: str, source: dict[str, str]) -> dict[str, str]:
    """A file's source as an answer names it: the file, and its system, owner and
    review date."""
    return {"file": file} | source


def read_yaml(file: str) -> dict[str, Any]:
    """Read one of the YAML files, with its source."""
    data = yaml.safe_load((FOLDER / file).read_text(encoding="utf-8"))
    return data | {"source": file_source(file, data["source"])}
