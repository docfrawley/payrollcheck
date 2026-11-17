"""Dates as our notices and emails give them, such as Nov 22, 2026."""

from datetime import date


def in_words(day: str) -> str:
    """A date, or the date of a moment, as people read it, such as Nov 22, 2026."""
    found = date.fromisoformat(day[:10])
    return f"{found:%b} {found.day}, {found.year}"
