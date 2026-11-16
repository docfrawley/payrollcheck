"""The backend's operations on subcontractors, for the Copilot: finding them by
name, and one subcontractor with its record, its projects and its cases in the
queue, each in the reviewer's scope. A subcontractor is in a scope while it is on
a project in it, so a held-out subcontractor is never found."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from backend.database import case_view, cases, engagements, projects, subcontractors
from backend.dependencies import Database
from backend.models import Project, Subcontractor, SubcontractorMatch
from backend.scope import Scoped, cases_in, projects_in, subcontractors_in
from backend.views import to_summary

SUBCONTRACTOR_NOT_FOUND = "Subcontractor {subcontractor_id} not found"

router = APIRouter()

# A name to look for, with something in it besides spaces.
Name = Annotated[
    str, Query(pattern=r"\S", description="Words in the subcontractor's legal name")
]


@router.get("/api/subcontractors", operation_id="find_subcontractors")
def find_subcontractors(
    name: Name, db: Database, scope: Scoped
) -> list[SubcontractorMatch]:
    """Find the subcontractors whose legal name holds every word, ignoring case."""
    query = select(
        subcontractors.c.subcontractor_id, subcontractors.c.legal_name
    ).where(subcontractors_in(scope))
    for word in name.lower().split():
        query = query.where(
            func.lower(subcontractors.c.legal_name).contains(word, autoescape=True)
        )
    rows = db.execute(query.order_by(subcontractors.c.legal_name)).mappings()
    return [SubcontractorMatch(**row) for row in rows]


@router.get("/api/subcontractors/{subcontractor_id}", operation_id="get_subcontractor")
def get_subcontractor(
    subcontractor_id: str, db: Database, scope: Scoped
) -> Subcontractor:
    """Get a subcontractor with its record, its projects and its cases in our queue."""
    query = select(subcontractors).where(
        subcontractors.c.subcontractor_id == subcontractor_id, subcontractors_in(scope)
    )
    record = db.execute(query).mappings().first()
    if record is None:
        message = SUBCONTRACTOR_NOT_FOUND.format(subcontractor_id=subcontractor_id)
        raise HTTPException(404, message)
    on = (
        select(projects)
        .join(engagements, engagements.c.project_id == projects.c.project_id)
        .where(engagements.c.subcontractor_id == subcontractor_id, projects_in(scope))
        .order_by(projects.c.project_id)
    )
    in_the_queue = case_view.where(
        cases.c.subcontractor_id == subcontractor_id,
        cases.c.evaluation_id.is_(None),
        cases_in(scope),
    ).order_by(cases.c.case_id)
    return Subcontractor(
        **record,
        projects=[Project(**row) for row in db.execute(on).mappings()],
        cases=[to_summary(row) for row in db.execute(in_the_queue).mappings()],
    )
