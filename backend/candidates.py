"""A check tool's candidate findings, kept for the case's current attempt on its
thread, each with its severity from the rule catalogue, and the check recorded as
a step on the case."""

from sqlalchemy import Connection, RowMapping, delete, insert, select

from backend.database import candidates, check_runs
from backend.models import Candidate, CheckFindingsRequest, FindingRecord, NewStep
from backend.money import dollars
from backend.rule_codes import RULES
from backend.steps import add_step

NOTHING_FOUND = "Nothing found"


def finding_line(found: FindingRecord) -> str:
    """One finding as a check's step lists it."""
    where = f" {found.worker_id} line {found.line_no}" if found.worker_id else ""
    short = (
        f", {dollars(found.shortfall_cents / 100)} short"
        if found.shortfall_cents is not None
        else ""
    )
    return (
        f"- {found.rule}{where}{short}: expected {found.expected}, "
        f"found {found.actual}. {found.citation}"
    )


def describe(request: CheckFindingsRequest) -> str:
    """A check's step: what it found, or that it found nothing."""
    if not request.findings:
        return f"{request.check}: {NOTHING_FOUND}"
    lines = [finding_line(found) for found in request.findings]
    return "\n".join([f"{request.check}: {len(lines)} found", *lines])


def keep_findings(
    db: Connection, case: RowMapping, request: CheckFindingsRequest
) -> list[Candidate]:
    """Keep a check's findings as the attempt's candidates, in place of any it
    found before on the same thread, as when a stopped attempt runs it again."""
    case_id, thread_id = case["case_id"], case["thread_id"]
    of_this_check = (
        candidates.c.case_id == case_id,
        candidates.c.thread_id == thread_id,
        candidates.c.check == request.check,
    )
    db.execute(delete(candidates).where(*of_this_check))
    db.execute(
        delete(check_runs).where(
            check_runs.c.case_id == case_id,
            check_runs.c.thread_id == thread_id,
            check_runs.c.check == request.check,
        )
    )
    db.execute(
        insert(check_runs).values(
            case_id=case_id, thread_id=thread_id, check=request.check
        )
    )
    if request.findings:
        db.execute(
            insert(candidates),
            [
                {
                    "case_id": case_id,
                    "thread_id": thread_id,
                    "submission_no": case["latest_submission_no"],
                    "check": request.check,
                    "severity": RULES[found.rule].severity,
                    **found.model_dump(),
                }
                for found in request.findings
            ],
        )
    add_step(
        db,
        case_id,
        thread_id,
        NewStep(kind="check", content=describe(request), sources=[]),
    )
    query = select(candidates).where(*of_this_check).order_by(candidates.c.candidate_id)
    return [Candidate(**row) for row in db.execute(query).mappings()]


def attempts_candidates(db: Connection, case: RowMapping) -> dict[int, RowMapping]:
    """The candidates of the case's current attempt, by id."""
    query = select(candidates).where(
        candidates.c.case_id == case["case_id"],
        candidates.c.thread_id == case["thread_id"],
    )
    return {row["candidate_id"]: row for row in db.execute(query).mappings()}
