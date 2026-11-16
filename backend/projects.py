"""The projects: the list a reviewer sees, a project with its subcontractors and
their engagement windows, and the project's subcontractors as the payroll agent
reads them. No list holds a held-out record."""

from fastapi import APIRouter
from sqlalchemy import Connection, select

from backend.database import engagements, projects, subcontractors
from backend.dependencies import Database, ReviewerOrAgent, SignedInReviewer
from backend.lookups import project_row
from backend.models import Engagement, Project, ProjectInFull

router = APIRouter()


def engagements_of(db: Connection, project_id: str) -> list[Engagement]:
    query = (
        select(subcontractors, engagements)
        .join(
            engagements,
            engagements.c.subcontractor_id == subcontractors.c.subcontractor_id,
        )
        .where(engagements.c.project_id == project_id)
        .order_by(engagements.c.pair)
    )
    return [Engagement(**row) for row in db.execute(query).mappings()]


@router.get(
    "/api/projects", operation_id="list_projects", dependencies=[SignedInReviewer]
)
def list_projects(db: Database) -> list[Project]:
    """List our projects, in id order."""
    query = select(projects).where(projects.c.held_out.is_(False))
    rows = db.execute(query.order_by(projects.c.project_id)).mappings()
    return [Project(**row) for row in rows]


@router.get(
    "/api/projects/{project_id}",
    operation_id="get_project",
    dependencies=[ReviewerOrAgent],
)
def get_project(project_id: str, db: Database) -> ProjectInFull:
    """Get a project: its county, contract, award date and subcontractors."""
    row = project_row(db, project_id)
    return ProjectInFull(**row, subcontractors=engagements_of(db, project_id))


@router.get(
    "/api/projects/{project_id}/subcontractors",
    operation_id="list_subcontractors",
    dependencies=[ReviewerOrAgent],
)
def list_subcontractors(project_id: str, db: Database) -> list[Engagement]:
    """List a project's subcontractors with their records and engagement windows."""
    project_row(db, project_id)
    return engagements_of(db, project_id)
