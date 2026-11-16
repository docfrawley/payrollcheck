"""Version 1 of the payroll agent's configuration and of the improver's recipe, as
seeding makes them, and the folder their instructions are in, which the improver
reads too."""

from pathlib import Path

from backend.models import Verdict
from backend.parameters import FIRST_PARAMETERS

INSTRUCTIONS = Path(__file__).resolve().parent / "instructions"
# Version 1 is kept from the start, so the current version is the newest kept.
FIRST_VERSION = {
    "number": 1,
    "reason": "The payroll agent as our compliance team first wrote it",
    "proposed_by": "The compliance team",
    "verdict": Verdict.KEPT,
    "verdict_reason": "the first version",
    "parameters": FIRST_PARAMETERS,
    "motivating_cases": [],
}
# The model version 1 of the payroll agent is on, with no reasoning, so a higher
# reasoning effort is an improvement to find, unless a student is on a free model.
FIRST_MODEL = ("openai/gpt-6-luna", "none")
FIRST_RECIPE = {
    "number": 1,
    "reason": "The lab's first recipe, which tries the models and reasoning efforts "
    "not yet tried, then makes the narrowest general change behind the "
    "development mistakes and the reviewers' corrections",
    "proposed_by": "The compliance team",
}
