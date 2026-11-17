"""The backend's operation on subcontractors, for the Copilot: finding them by
name in the reviewer's scope. A subcontractor is in a scope while it is on a
project in it, so a held-out subcontractor is never found."""

from fastapi import APIRouter
from sqlalchemy import select

from backend.database import subcontractors
from backend.dependencies import Database
from backend.models import SubcontractorMatch
from backend.names import Name, holding_every_word
from backend.scope import Scoped, subcontractors_in

router = APIRouter()


@router.get("/api/subcontractors", operation_id="find_subcontractors")
def find_subcontractors(
    name: Name, db: Database, scope: Scoped
) -> list[SubcontractorMatch]:
    """Find the subcontractors whose legal name holds every word, ignoring case."""
    query = select(
        subcontractors.c.subcontractor_id, subcontractors.c.legal_name
    ).where(subcontractors_in(scope))
    query = holding_every_word(query, subcontractors.c.legal_name, name)
    rows = db.execute(query.order_by(subcontractors.c.legal_name)).mappings()
    return [SubcontractorMatch(**row) for row in rows]
