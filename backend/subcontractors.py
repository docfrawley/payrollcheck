"""The backend's operations on subcontractors, for the Copilot: finding them by name,
and one subcontractor with their policies and cases, without their contact details or
date of birth."""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from backend.database import case_view, cases, policies, subcontractors
from backend.dependencies import Database, SignedInReviewer
from backend.lookups import subcontractor_record
from backend.models import Policy, PreviousCase, Subcontractor, SubcontractorMatch
from backend.views import to_summary

router = APIRouter()

# A name to look for, with something in it besides spaces.
Name = Annotated[
    str, Query(pattern=r"\S", description="Words in the subcontractor's name")
]


@router.get(
    "/api/subcontractors",
    operation_id="find_subcontractors",
    dependencies=[SignedInReviewer],
)
def find_subcontractors(name: Name, db: Database) -> list[SubcontractorMatch]:
    """Find the subcontractors whose name holds every word given, ignoring case."""
    query = select(subcontractors.c.subcontractor_id, subcontractors.c.name)
    for word in name.lower().split():
        query = query.where(
            func.lower(subcontractors.c.name).contains(word, autoescape=True)
        )
    rows = db.execute(query.order_by(subcontractors.c.name)).mappings()
    return [SubcontractorMatch(**row) for row in rows]


@router.get(
    "/api/subcontractors/{subcontractor_id}",
    operation_id="get_subcontractor",
    dependencies=[SignedInReviewer],
)
def get_subcontractor(subcontractor_id: str, db: Database) -> Subcontractor:
    """Get a subcontractor with their policies, earlier cases and cases in our queue."""
    record = subcontractor_record(db, subcontractor_id)
    theirs = select(policies.c.record).where(
        policies.c.record["subcontractor_id"].as_string() == subcontractor_id
    )
    their_policies = [Policy(**policy) for policy in db.execute(theirs).scalars()]
    in_the_queue = case_view.where(
        cases.c.subcontractor_id == subcontractor_id, cases.c.evaluation_id.is_(None)
    ).order_by(cases.c.case_id)
    return Subcontractor(
        subcontractor_id=subcontractor_id,
        name=record["name"],
        subcontractor_since=record["subcontractor_since"],
        policies=their_policies,
        earlier_cases=[PreviousCase(**c) for c in record["previous_cases"]],
        cases_in_the_queue=[
            to_summary(row) for row in db.execute(in_the_queue).mappings()
        ],
    )
