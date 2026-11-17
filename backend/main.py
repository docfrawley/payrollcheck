"""The PayrollCheck backend: the app, and the operations on cases and reviewers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from mangum import Mangum
from sqlalchemy import Connection, RowMapping, func, insert, select, update

from backend import agent_api, dashboard, notices, outbox, overrides
from backend.business_date import business_date
from backend.business_date import router as business_date_router
from backend.candidates import keep_findings
from backend.configuration import router as configuration
from backend.copilot import router as copilot
from backend.copilot_reads import router as copilot_reads
from backend.database import (
    case_view,
    cases,
    engine,
    exceptions,
    is_seeded,
    model_calls,
    now,
    stamp,
    steps,
    work_times,
)
from backend.dependencies import (
    AgentKey,
    Database,
    ReviewerOrAgent,
    SignedIn,
    SignedInReviewer,
)
from backend.history import payroll_history
from backend.improvement import router as improvement
from backend.lookups import find_case, run_row
from backend.models import (
    Candidate,
    Case,
    CaseSummary,
    CheckFindingsRequest,
    ExceptionReport,
    ExceptionStatus,
    FailureRequest,
    ModelCall,
    ModelCallRequest,
    NewException,
    NewStep,
    NoticeRequest,
    OverrideRequest,
    PayrollHistory,
    Reviewer,
    RuleEntry,
    ScreeningFlagRequest,
    StartRequest,
    Status,
    Step,
    StepRequest,
    WorkTime,
    WorkTimeRequest,
)
from backend.overrides import Overriding
from backend.projects import router as projects
from backend.reports import record_report
from backend.round_state import round_row, why_no_case_starts
from backend.rule_codes import RULES
from backend.runs import router as runs
from backend.scope import EVERYTHING, Scope, Scoped, ScopedOrAgent, cases_in
from backend.seeding import seed
from backend.steps import add_step
from backend.subcontractors import router as subcontractors_router
from backend.views import case_in_full, to_summary

ATTEMPTS = 2
NOT_STARTED = "Case {case_id} has not been started"
NOT_IN_PROGRESS = "Case {case_id} is not in progress"
NOT_RECEIVED = "Case {case_id} is not Received"
NOT_AWAITING_REVIEW = "Case {case_id} is not awaiting review"
A_COPY = "Case {case_id} is a copy in an evaluation and can't be {answered}"
STILL_OPEN = (
    "Case {case_id} has {count} open {exceptions}, so it can't be signed off: "
    "dismiss each with a reason, or send it back to its subcontractor"
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Seed the database on startup if it has no tables yet."""
    if not is_seeded(engine()):
        seed(engine())
    yield


app = FastAPI(title="PayrollCheck", lifespan=lifespan)
app.include_router(runs)
app.include_router(configuration)
app.include_router(improvement)
app.include_router(copilot)
app.include_router(projects)
app.include_router(subcontractors_router)
app.include_router(business_date_router)
app.include_router(copilot_reads)


def move_case(
    db: Connection, case_id: str, old: Status, new: Status, **columns: Any
) -> bool:
    """Move a case from one status to another, setting any other columns given, and
    say whether it moved: only the first of two requests at the same moment finds
    it in the old status."""
    moved = db.execute(
        update(cases)
        .where(cases.c.case_id == case_id, cases.c.status == old)
        .values(status=new, **columns)
    )
    return moved.rowcount == 1


def in_progress(db: Connection, case_id: str) -> RowMapping:
    """A case's row if it is in progress, for the agent, or raise a 404 or a 409."""
    case = find_case(db, case_id, EVERYTHING)
    if case["status"] != Status.IN_PROGRESS:
        raise HTTPException(409, NOT_IN_PROGRESS.format(case_id=case_id))
    return case


def move_on(db: Connection, case_id: str, new: Status, **columns: Any) -> None:
    """Move a case in progress on, or raise a 409 when another request moved it
    first, which rolls back everything this request did."""
    if not move_case(db, case_id, Status.IN_PROGRESS, new, **columns):
        raise HTTPException(409, NOT_IN_PROGRESS.format(case_id=case_id))


def awaiting_review(
    db: Connection, case_id: str, scope: Scope, answered: str
) -> RowMapping:
    """A case a reviewer can answer: its row, or raise a 404, or a 409 for an
    evaluation's copy, which nobody answers, or a case not awaiting review."""
    case = find_case(db, case_id, scope)
    if case["evaluation_id"] is not None:
        raise HTTPException(409, A_COPY.format(case_id=case_id, answered=answered))
    if case["status"] != Status.AWAITING_REVIEW:
        raise HTTPException(409, NOT_AWAITING_REVIEW.format(case_id=case_id))
    return case


def hold_for_review(db: Connection, case_id: str) -> None:
    """Hold a case awaiting review while a reviewer overrides its exceptions or
    edits its notice, by taking its row's lock with a conditional update, or raise
    a 409. A sign-off takes the same lock first, so the two never interleave:
    whichever comes second finds what the first one did."""
    held = move_case(db, case_id, Status.AWAITING_REVIEW, Status.AWAITING_REVIEW)
    if not held:
        raise HTTPException(409, NOT_AWAITING_REVIEW.format(case_id=case_id))


def decide(db: Connection, case_id: str, outcome: Status, reviewer: Reviewer) -> None:
    """Move a case awaiting review to the reviewer's outcome, for the first of two
    answers at the same moment, or raise a 409. The move takes the case's row's
    lock, so whatever the answer reads after it sees every override and every edit
    of the notice made before it."""
    decided = move_case(
        db,
        case_id,
        Status.AWAITING_REVIEW,
        outcome,
        reviewed_by=reviewer.reviewer_id,
        reviewed_on=business_date(db).isoformat(),
    )
    if not decided:
        raise HTTPException(409, NOT_AWAITING_REVIEW.format(case_id=case_id))


def started_thread(db: Connection, case_id: str) -> str:
    """Return the thread of a case that has been started, or raise a 404 or a 409."""
    thread_id = find_case(db, case_id, EVERYTHING)["thread_id"]
    if thread_id is None:
        raise HTTPException(409, NOT_STARTED.format(case_id=case_id))
    return thread_id


def refuse_a_round_that_cant_go_on(db: Connection, run_id: str) -> None:
    """Raise a 409 when an evaluation belongs to a round that was stopped or has
    spent its limit, so no new case starts in it."""
    round_id = run_row(db, run_id)["round_id"]
    if round_id is None:
        return
    reason = why_no_case_starts(db, round_row(db, round_id))
    if reason:
        raise HTTPException(409, reason)


def check_run(db: Connection, run_id: str | None) -> None:
    """Check that the run named, if any, exists, or raise a 404."""
    if run_id is not None:
        run_row(db, run_id)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/cases", operation_id="list_cases")
def list_cases(db: Database, scope: ScopedOrAgent) -> list[CaseSummary]:
    """List the cases in the queue in scope, in id order, leaving out the copies."""
    query = case_view.where(cases.c.evaluation_id.is_(None), cases_in(scope))
    rows = db.execute(query.order_by(cases.c.case_id)).mappings()
    return [to_summary(row) for row in rows]


@app.get("/api/cases/{case_id}", operation_id="get_case")
def get_case(case_id: str, db: Database, scope: ScopedOrAgent) -> Case:
    """Get a case in full: its submissions, workers, exceptions, findings and notice."""
    return case_in_full(db, case_id, scope)


@app.get("/api/cases/{case_id}/history", operation_id="get_payroll_history")
def get_payroll_history(
    case_id: str, db: Database, scope: ScopedOrAgent
) -> PayrollHistory:
    """Get the earlier weeks' payrolls of record of the case's subcontractor."""
    return payroll_history(db, find_case(db, case_id, scope))


@app.get(
    "/api/agent/openapi.json",
    operation_id="get_agent_api",
    dependencies=[ReviewerOrAgent],
)
def get_agent_api() -> dict[str, Any]:
    """Get the OpenAPI document of the payroll agent's operations, for the Gateway."""
    return agent_api.document(app)


@app.get("/api/me", operation_id="get_signed_in_reviewer")
def get_signed_in_reviewer(reviewer: SignedIn) -> Reviewer:
    """Get the reviewer signed in, with what they may do."""
    return reviewer


@app.post(
    "/api/cases/{case_id}/start", operation_id="start_case", dependencies=[AgentKey]
)
def start_case(case_id: str, request: StartRequest, db: Database) -> Case:
    """Start work on a Received case, which moves it to In progress, only once."""
    case = find_case(db, case_id, EVERYTHING)
    if case["evaluation_id"]:
        refuse_a_round_that_cant_go_on(db, case["evaluation_id"])
    started = move_case(
        db,
        case_id,
        Status.RECEIVED,
        Status.IN_PROGRESS,
        thread_id=request.thread_id,
        attempts=cases.c.attempts + 1,
    )
    if not started:
        raise HTTPException(409, NOT_RECEIVED.format(case_id=case_id))
    return case_in_full(db, case_id, EVERYTHING)


@app.post(
    "/api/cases/{case_id}/steps", operation_id="record_step", dependencies=[AgentKey]
)
def record_step(case_id: str, request: StepRequest, db: Database) -> Step:
    """Record one step of the agent's work on a case."""
    thread_id = started_thread(db, case_id)
    return add_step(db, case_id, thread_id, NewStep(**request.model_dump()))


@app.post(
    "/api/cases/{case_id}/model-calls",
    operation_id="record_model_call",
    dependencies=[AgentKey],
)
def record_model_call(
    case_id: str, request: ModelCallRequest, db: Database
) -> ModelCall:
    """Record the tokens and the cost of one model call on a started case."""
    thread_id = started_thread(db, case_id)
    check_run(db, request.run_id)
    query = (
        insert(model_calls)
        .values(
            case_id=case_id,
            thread_id=thread_id,
            **request.model_dump(),
            created_at=now(),
        )
        .returning(model_calls)
    )
    return ModelCall(**db.execute(query).mappings().one())


@app.post(
    "/api/cases/{case_id}/work-times",
    operation_id="record_work_time",
    dependencies=[AgentKey],
)
def record_work_time(case_id: str, request: WorkTimeRequest, db: Database) -> WorkTime:
    """Record one spell of the agent's work on a started case, ending now."""
    thread_id = started_thread(db, case_id)
    check_run(db, request.run_id)
    started = datetime.now(UTC) - timedelta(seconds=request.seconds)
    query = (
        insert(work_times)
        .values(
            case_id=case_id,
            thread_id=thread_id,
            run_id=request.run_id,
            started_at=stamp(started),
            seconds=request.seconds,
        )
        .returning(work_times)
    )
    return WorkTime(**db.execute(query).mappings().one())


@app.get("/api/cases/{case_id}/steps", operation_id="list_steps")
def list_steps(case_id: str, db: Database, scope: Scoped) -> list[Step]:
    """List the steps of the agent's work on a case, in order."""
    find_case(db, case_id, scope)
    query = select(steps).where(steps.c.case_id == case_id).order_by(steps.c.step_id)
    return [Step(**row) for row in db.execute(query).mappings()]


@app.post(
    "/api/cases/{case_id}/candidates",
    operation_id="record_check_findings",
    dependencies=[AgentKey],
)
def record_check_findings(
    case_id: str, request: CheckFindingsRequest, db: Database
) -> list[Candidate]:
    """Keep a check tool's findings as this attempt's candidates, with their ids."""
    return keep_findings(db, in_progress(db, case_id), request)


@app.post(
    "/api/cases/{case_id}/screening-flag",
    operation_id="record_screening_flag",
    dependencies=[AgentKey],
)
def record_screening_flag(
    case_id: str, request: ScreeningFlagRequest, db: Database
) -> Case:
    """Flag a case the screening found an instruction in, for a reviewer to work."""
    in_progress(db, case_id)
    move_on(
        db,
        case_id,
        Status.AWAITING_REVIEW,
        screening_flag=True,
        screening_reason=request.reason,
    )
    return case_in_full(db, case_id, EVERYTHING)


@app.post(
    "/api/cases/{case_id}/report",
    operation_id="record_exception_report",
    dependencies=[AgentKey],
)
def record_exception_report(
    case_id: str, request: ExceptionReport, db: Database
) -> Case:
    """Record the exception report and its draft notice; every shortfall a check's."""
    case = in_progress(db, case_id)
    move_on(db, case_id, Status.AWAITING_REVIEW)
    record_report(db, case, request)
    return case_in_full(db, case_id, EVERYTHING)


@app.post(
    "/api/cases/{case_id}/failure", operation_id="fail_case", dependencies=[AgentKey]
)
def fail_case(case_id: str, request: FailureRequest, db: Database) -> Case:
    """Put a failed case back in the queue, or for a reviewer after two attempts."""
    case = in_progress(db, case_id)
    if case["attempts"] >= ATTEMPTS:
        move_on(db, case_id, Status.AWAITING_REVIEW, agent_failed=True)
    else:
        move_on(db, case_id, Status.RECEIVED)
    error = NewStep(kind="error", content=request.reason, sources=[])
    add_step(db, case_id, case["thread_id"], error)
    return case_in_full(db, case_id, EVERYTHING)


@app.post("/api/cases/{case_id}/sign-off", operation_id="sign_off_case")
def sign_off_case(
    case_id: str, reviewer: SignedIn, scope: Scoped, db: Database
) -> Case:
    """Sign off a case awaiting review with no open exceptions, which accepts it."""
    case = awaiting_review(db, case_id, scope, "signed off")
    decide(db, case_id, Status.ACCEPTED, reviewer)
    query = select(func.count()).where(
        exceptions.c.case_id == case_id,
        exceptions.c.submission_no == case["latest_submission_no"],
        exceptions.c.status == ExceptionStatus.OPEN,
    )
    still_open = db.execute(query).scalar_one()
    if still_open:
        # Raised after the move, which this request's rollback undoes.
        exceptions_ = "exception" if still_open == 1 else "exceptions"
        message = STILL_OPEN.format(
            case_id=case_id, count=still_open, exceptions=exceptions_
        )
        raise HTTPException(409, message)
    return case_in_full(db, case_id, scope)


@app.post("/api/cases/{case_id}/send-back", operation_id="send_back_case")
def send_back_case(
    case_id: str, reviewer: SignedIn, scope: Scoped, db: Database
) -> Case:
    """Send a case back to its subcontractor with its notice, through the outbox."""
    case = awaiting_review(db, case_id, scope, "sent back")
    decide(db, case_id, Status.RETURNED_TO_SUB, reviewer)
    # Read after the move, which holds the case, so no edit lands in between; a
    # refusal undoes the move with the rest of the request.
    body = notices.notice_to_send(db, case)
    sent_at = now()
    notices.mark_sent(db, case, reviewer, sent_at)
    outbox.send(db, case, body, reviewer, sent_at)
    return case_in_full(db, case_id, scope)


@app.put("/api/cases/{case_id}/notice", operation_id="save_notice")
def save_notice(
    case_id: str,
    request: NoticeRequest,
    reviewer: SignedIn,
    scope: Scoped,
    db: Database,
) -> Case:
    """Save the reviewer's edit of the latest submission's notice, without sending."""
    case = awaiting_review(db, case_id, scope, "edited")
    hold_for_review(db, case_id)
    notices.save_notice(db, case, request.text, reviewer)
    return case_in_full(db, case_id, scope)


@app.get("/api/rules", operation_id="list_rules", dependencies=[SignedInReviewer])
def list_rules() -> list[RuleEntry]:
    """List the rule catalogue: each rule's check, severity, money and where found."""
    return [
        RuleEntry.model_validate(rule._asdict() | {"rule": code})
        for code, rule in RULES.items()
    ]


OVERRIDDEN = "overridden"


def overriding(
    case_id: str, reviewer: SignedIn, scope: Scoped, db: Database
) -> Overriding:
    """Who overrides the exceptions of a case awaiting review, holding the case for
    the request, or a 404 or a 409 for a case they can't override: one not
    awaiting review, or an evaluation's copy."""
    case = awaiting_review(db, case_id, scope, OVERRIDDEN)
    hold_for_review(db, case_id)
    return Overriding(case=case, reviewer=reviewer, scope=scope)


Overrides = Annotated[Overriding, Depends(overriding)]


@app.post(
    "/api/cases/{case_id}/exceptions/{exception_id}/dismissal",
    operation_id="dismiss_exception",
)
def dismiss_exception(
    case_id: str,
    exception_id: int,
    request: OverrideRequest,
    by: Overrides,
    db: Database,
) -> Case:
    """Dismiss an open exception of the latest submission, with why, as an override."""
    overrides.dismiss(db, by, exception_id, request.reason)
    return case_in_full(db, case_id, by.scope)


@app.post(
    "/api/cases/{case_id}/exceptions/{exception_id}/restoration",
    operation_id="restore_exception",
)
def restore_exception(
    case_id: str,
    exception_id: int,
    request: OverrideRequest,
    by: Overrides,
    db: Database,
) -> Case:
    """Reopen a dismissed exception of the latest submission, with why."""
    overrides.restore(db, by, exception_id, request.reason)
    return case_in_full(db, case_id, by.scope)


@app.post("/api/cases/{case_id}/exceptions", operation_id="add_exception")
def add_exception(
    case_id: str, request: NewException, by: Overrides, db: Database
) -> Case:
    """Add an exception the agent missed to the latest submission, with why."""
    overrides.add(db, by, request)
    return case_in_full(db, case_id, by.scope)


# After every route, so the dashboard's build only answers what no route does.
app.router.routes.append(dashboard.mount)

# AWS Lambda's entry point. Nothing seeds the database there.
handler = Mangum(app, lifespan="off")
