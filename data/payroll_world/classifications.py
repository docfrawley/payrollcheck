"""A line's classification as the template writes it, such as "Electrician
Journeyman" or "Operating Engineer Apprentice", and the craft and classification
it names."""

from data.payroll_world.determinations import RATES

CRAFTS_BY_NAME = {craft.name: key for key, craft in RATES.crafts.items()}


def classification_text(craft: str, classification: str) -> str:
    return f"{RATES.crafts[craft].name} {classification.title()}"


def classification_of(text: str) -> tuple[str, str]:
    """The craft and classification a line's classification names."""
    craft_name, classification = text.rsplit(" ", 1)
    return CRAFTS_BY_NAME[craft_name], classification.lower()
