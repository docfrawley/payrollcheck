"""The Copilot's reads, and its one write, under /api/copilot/, for a signed-in
reviewer in their scope: the queue's cases found by filters, a case in full and
its open exceptions, exposure, filings, classification changes and projects found
by name, the success criteria, and the send-back notice it drafts and saves for
the reviewer. They reach the queue's cases, never an evaluation's copy. The case
page's reads are the dashboard's; the Copilot's are these, which pass every
answer that can hold what a flagged case's subcontractor wrote through
withheld.py. The rest hold none: their names and ids come from our records."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import Connection, select

from backend import notice_drafts, notices, withheld
from backend.case_search import find_cases as search
from backend.classification_changes import classification_changes as changes_in
from backend.criteria_report import success_criteria
from backend.database import projects
from backend.dependencies import Database, SignedIn
from backend.exposure import exposure
from backend.filings import filings
from backend.lookups import find_queue_case, project_row, subcontractor_row
from backend.models import (
    Case,
    CaseExceptions,
    CaseFilters,
    ClassificationChanges,
    ClassificationChangesRequest,
    Exposure,
    ExposureRequest,
    Filings,
    FilingsRequest,
    FoundCases,
    NoticeDrafted,
    ProjectMatch,
    SuccessCriteria,
)
from backend.names import Name, holding_every_word
from backend.open_exceptions import case_exceptions
from backend.reviewing import NOTICED, hold_for_review, in_review
from backend.scope import Scope, Scoped, projects_in
from backend.views import case_in_full

router = APIRouter(prefix="/api/copilot")


def check_filters(
    db: Connection,
    scope: Scope,
    project_id: str | None,
    subcontractor_id: str | None = None,
) -> None:
    """Raise a 404 for a project or subcontractor filter outside the scope."""
    if project_id is not None:
        project_row(db, project_id, scope)
    if subcontractor_id is not None:
        subcontractor_row(db, subcontractor_id, scope)


@router.post("/cases", operation_id="find_cases")
def find_cases(request: CaseFilters, db: Database, scope: Scoped) -> FoundCases:
    """Find the cases in the queue that match every filter given, null for any."""
    check_filters(db, scope, request.project_id, request.subcontractor_id)
    return search(db, request, scope)


@router.get("/cases/{case_id}", operation_id="read_case")
def read_case(case_id: str, db: Database, scope: Scoped) -> Case:
    """Read a case in full, as the Copilot may see it."""
    find_queue_case(db, case_id, scope)
    return withheld.case(case_in_full(db, case_id, scope))


@router.get("/cases/{case_id}/exceptions", operation_id="get_exceptions")
def get_exceptions(case_id: str, db: Database, scope: Scoped) -> CaseExceptions:
    """Get the exceptions open on a case's latest submission, with their citations."""
    found = case_exceptions(db, find_queue_case(db, case_id, scope))
    return withheld.exceptions(found)


@router.post("/exposure", operation_id="exposure_summary")
def exposure_summary(request: ExposureRequest, db: Database, scope: Scoped) -> Exposure:
    """Sum the flagged and outstanding underpayment, null for any filter."""
    check_filters(db, scope, request.project_id, request.subcontractor_id)
    return withheld.exposure(exposure(db, request, scope))


@router.post("/filings", operation_id="filings_status")
def filings_status(request: FilingsRequest, db: Database, scope: Scoped) -> Filings:
    """List the expected filings of a period that are late, missing or on time."""
    check_filters(db, scope, request.project_id)
    return filings(db, request, scope)


@router.post("/classification-changes", operation_id="classification_changes")
def classification_changes(
    request: ClassificationChangesRequest, db: Database, scope: Scoped
) -> ClassificationChanges:
    """List the workers whose classification changed from the week before."""
    check_filters(db, scope, request.project_id)
    return withheld.changes(changes_in(db, request, scope))


@router.get("/projects", operation_id="find_projects")
def find_projects(name: Name, db: Database, scope: Scoped) -> list[ProjectMatch]:
    """Find the projects whose name holds every word given, ignoring case."""
    query = select(projects.c.project_id, projects.c.name, projects.c.county).where(
        projects_in(scope)
    )
    query = holding_every_word(query, projects.c.name, name)
    rows = db.execute(query.order_by(projects.c.project_id)).mappings()
    return [ProjectMatch(**row) for row in rows]


SEND_FROM = "the case page"
NOTHING_OPEN = "{case_id} has no open exception to put in a notice"


@router.post("/cases/{case_id}/notice-draft", operation_id="draft_notice")
def draft_notice(
    case_id: str, reviewer: SignedIn, db: Database, scope: Scoped
) -> NoticeDrafted:
    """Draft the case's send-back notice from its open exceptions, and save it."""
    case = in_review(db, case_id, scope, "given a notice", NOTICED)
    hold_for_review(db, case, NOTICED)
    found = case_exceptions(db, case)
    if not found.exceptions:
        raise HTTPException(409, NOTHING_OPEN.format(case_id=case_id))
    text = notice_drafts.draft(found, case["project_name"])
    drafted_by = notices.save_draft(db, case, text, reviewer)
    # The model reads the notice as it reads the exceptions.
    shown = notice_drafts.draft(withheld.exceptions(found), case["project_name"])
    return NoticeDrafted(
        case_id=case_id, drafted_by=drafted_by, draft=shown, send_from=SEND_FROM
    )


@router.get("/success-criteria", operation_id="check_success_criteria")
def check_success_criteria(db: Database, scope: Scoped) -> SuccessCriteria:
    """Check the business's seven success criteria, each figure worked out in code."""
    return success_criteria(db, scope)
