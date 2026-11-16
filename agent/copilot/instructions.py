"""The Copilot's instructions: its goal, who it works for, what it can see and do,
and how to answer, with what it remembers of the reviewer."""

from pathlib import Path
from typing import Any

INSTRUCTIONS = (Path(__file__).parent / "instructions.md").read_text(encoding="utf-8")
NOTHING_REMEMBERED = "Nothing yet."


def instructions_for(reviewer: dict[str, Any], remembered: list[str]) -> str:
    """The instructions for the reviewer the app says is signed in, with what the
    Copilot remembers of them."""
    memories = "\n".join(f"- {text}" for text in remembered) or NOTHING_REMEMBERED
    return INSTRUCTIONS.format(
        name=reviewer["name"], role=reviewer["role"], remembered=memories
    )
