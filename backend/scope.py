"""Scope: the projects a person may see and act on, and the filters every query of
cases and projects applies. A reviewer's scope is the projects they're assigned to,
and the compliance manager's every one of our projects; a held-out project is in
no person's. The agent's key works every case, an evaluation's copies included, so
its scope is everything. An evaluation's copy belongs to the Scoreboard, which every
reviewer sees, so every scope holds the copies."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy import ColumnElement, Connection, select, true

from backend.database import (
    cases,
    engagements,
    project_reviewers,
    projects,
    subcontractors,
)
from backend.dependencies import (
    Caller,
    Database,
    SignedIn,
)
from backend.models import Reviewer, Role


@dataclass(frozen=True)
class Scope:
    """The projects a caller may see, or None for every project there is."""

    projects: frozenset[str] | None


# The agent's scope.
EVERYTHING = Scope(projects=None)


def scope_of(db: Connection, reviewer: Reviewer) -> Scope:
    """The projects a person may see and act on: their assignments, or every one of
    our projects for the compliance manager."""
    query = select(projects.c.project_id).where(projects.c.held_out.is_(False))
    if reviewer.role != Role.COMPLIANCE_MANAGER:
        query = query.join(
            project_reviewers, project_reviewers.c.project_id == projects.c.project_id
        ).where(project_reviewers.c.reviewer_id == reviewer.reviewer_id)
    return Scope(projects=frozenset(db.execute(query).scalars()))


def projects_in(scope: Scope) -> ColumnElement[bool]:
    """Whether a project is in the scope."""
    if scope.projects is None:
        return true()
    return projects.c.project_id.in_(scope.projects)


def cases_in(scope: Scope) -> ColumnElement[bool]:
    """Whether a case is in the scope: on a project in it, or an evaluation's copy."""
    if scope.projects is None:
        return true()
    return cases.c.evaluation_id.is_not(None) | cases.c.project_id.in_(scope.projects)


def subcontractors_in(scope: Scope) -> ColumnElement[bool]:
    """Whether a subcontractor is in the scope: not held out, and on a project in
    it."""
    engaged = (
        select(engagements.c.subcontractor_id)
        .join(projects, projects.c.project_id == engagements.c.project_id)
        .where(projects_in(scope))
    )
    return subcontractors.c.held_out.is_(False) & subcontractors.c.subcontractor_id.in_(
        engaged
    )


def scoped(reviewer: SignedIn, db: Database) -> Scope:
    """The signed-in reviewer's scope."""
    return scope_of(db, reviewer)


def scoped_or_agent(caller: Caller, db: Database) -> Scope:
    """Everything for the agent, or the signed-in reviewer's scope."""
    return EVERYTHING if caller is None else scope_of(db, caller)


# The scope of a route a signed-in reviewer calls, and of a read the agent shares.
Scoped = Annotated[Scope, Depends(scoped)]
ScopedOrAgent = Annotated[Scope, Depends(scoped_or_agent)]
