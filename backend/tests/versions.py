"""Versions of the payroll agent's configuration that the tests add straight to the
backend's table, as a round does once a reviewer approves a change."""

from sqlalchemy import func, insert, select

from backend.database import engine, now, versions
from backend.parameters import FIRST_PARAMETERS


def add_version(
    instructions,
    model="google/gemini-3.5-flash-lite",
    reasoning_effort="minimal",
    verdict=None,
    based_on=1,
    **columns,
):
    """Add the next version, under test unless it has a verdict, with version 1's
    parameters and no motivating cases unless the columns given say otherwise, and
    return its number."""
    with engine().begin() as db:
        number = db.execute(select(func.max(versions.c.number))).scalar_one() + 1
        db.execute(
            insert(versions).values(
                number=number,
                instructions=instructions,
                model=model,
                reasoning_effort=reasoning_effort,
                reason=f"The reason for version {number}",
                proposed_by=f"Round {number - 1}",
                based_on=based_on,
                approved_by="Dana Whitfield",
                approved_at=now(),
                created_at=now(),
                verdict=verdict,
                verdict_reason=verdict and f"version {number} was {verdict}",
                **({"parameters": FIRST_PARAMETERS, "motivating_cases": []} | columns),
            )
        )
    return number
