"""The steps of the agent's work on a case, which the agent records and the app
adds itself: a check's findings and an attempt's failure."""

from sqlalchemy import Connection, insert

from backend.database import now, steps
from backend.models import NewStep, Step


def add_step(db: Connection, case_id: str, thread_id: str, step: NewStep) -> Step:
    """Add one step of the agent's work to a case."""
    query = (
        insert(steps)
        .values(
            case_id=case_id,
            thread_id=thread_id,
            **step.model_dump(),
            created_at=now(),
        )
        .returning(steps)
    )
    return Step(**db.execute(query).mappings().one())
