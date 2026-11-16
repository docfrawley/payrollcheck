"""The backend's operations on runs: the dispatches and evaluations the agent works.
A reviewer starts one under /api/dispatches or /api/evaluations, which the app
creates and asks the agent to work; the agent records its work under /api/runs,
and the dashboard reads the runs."""

import uuid
from collections.abc import Callable
from functools import partial
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import Connection, RowMapping, delete, func, insert, select, update

from backend import agent_service, spending
from backend.agent_work import clear_the_way
from backend.asking import commit_and_ask
from backend.copies import make_copies
from backend.database import (
    cases,
    labelled_cases,
    now,
    run_cases,
    runs,
)
from backend.dependencies import AgentKey, Database, ReviewerOrAgent, SignedInReviewer
from backend.lookups import (
    CASE_NOT_FOUND,
    RUN_NOT_FOUND,
    allowed_models,
    current_version_number,
    round_number,
    run_row,
    settings_number,
    version_row,
)
from backend.models import (
    LABELLED_SET,
    DispatchSummary,
    Evaluation,
    EvaluationSet,
    FailureRequest,
    RoundStatus,
    Run,
    RunCasesRequest,
    RunKind,
    RunStarted,
    RunStatus,
    ScoredEvaluation,
    StartDispatchRequest,
    StartEvaluationRequest,
    Status,
)
from backend.money import dollars
from backend.round_state import (
    EVALUATIONS,
    evaluations_of,
    left_to_spend,
    open_round,
    round_row,
    stop,
    tried_version,
    why_no_case_starts,
)
from backend.scoreboard import (
    cases_of,
    expected_labels,
    model_cost_of,
    score,
    score_all,
    seconds_between,
    to_run_case,
)
from backend.stops import stop_runs

FIRST_EVALUATIONS_CUT_SHORT = "The spending limit cut short its first evaluations"
NOT_RUNNING = "Run {run_id} is not running"
# Cases a dispatch left that the next one picks up.
UNFINISHED = {Status.IN_PROGRESS, Status.RECEIVED}

router = APIRouter()


def find_run(db: Connection, run_id: str) -> Run:
    """Return one run with its cases, its model cost and its time, or raise a 404."""
    row = run_row(db, run_id)
    return Run(
        **row,
        model_cost=model_cost_of(db, run_id),
        seconds=seconds_between(row["started_at"], row["finished_at"]),
        round_number=round_number(db, row["round_id"]),
        cases=[to_run_case(case) for case in cases_of(db, run_id)],
    )


def running_run(db: Connection, run_id: str) -> RowMapping:
    """Return a run's row if it is still running, or raise a 404 or a 409."""
    row = run_row(db, run_id)
    if row["status"] != RunStatus.RUNNING:
        raise HTTPException(409, NOT_RUNNING.format(run_id=run_id))
    return row


def summarize(rows: list[RowMapping]) -> DispatchSummary:
    """Say what a dispatch left, from its cases as they stand, counting each case
    once: Awaiting review with exceptions or clean, flagged by the screening or
    failed by the agent, and those the next dispatch picks up."""

    def which(keep: Callable[[RowMapping], bool]) -> list[str]:
        return [row["case_id"] for row in rows if keep(row)]

    def reviewing(row: RowMapping) -> bool:
        return row["status"] not in UNFINISHED and not (
            row["screening_flag"] or row["agent_failed"]
        )

    return DispatchSummary(
        with_exceptions=which(lambda r: reviewing(r) and r["open_exceptions"] > 0),
        clean=which(lambda r: reviewing(r) and r["open_exceptions"] == 0),
        flagged=which(lambda r: r["screening_flag"]),
        agent_failed=which(lambda r: r["agent_failed"]),
        unfinished=which(lambda r: r["status"] in UNFINISHED),
    )


def new_run(
    db: Connection, kind: RunKind, fields: dict[str, Any], version: RowMapping
) -> RowMapping:
    """Record a new run, running, on a version of the payroll agent with its model
    and reasoning effort, and return its row."""
    run_id = str(uuid.uuid4())
    db.execute(
        insert(runs).values(
            run_id=run_id,
            kind=kind,
            **fields,
            version=version["number"],
            model=version["model"],
            reasoning_effort=version["reasoning_effort"],
            status=RunStatus.RUNNING,
            started_at=now(),
            heard_at=now(),
        )
    )
    return run_row(db, run_id)


def put_cases(db: Connection, run_id: str, case_ids: list[str]) -> None:
    """Record a run's cases in order, in place of any recorded before."""
    db.execute(delete(run_cases).where(run_cases.c.run_id == run_id))
    if case_ids:
        db.execute(
            insert(run_cases),
            [
                {"run_id": run_id, "position": position, "case_id": case_id}
                for position, case_id in enumerate(case_ids)
            ],
        )


def evaluation_of(db: Connection, fields: dict[str, Any], version: RowMapping) -> Run:
    """Record a new evaluation on a version, with a Received copy of each case."""
    row = new_run(db, RunKind.EVALUATION, fields, version)
    put_cases(db, row["run_id"], make_copies(db, row))
    return find_run(db, row["run_id"])


def set_size(db: Connection, evaluation_set: EvaluationSet) -> int:
    """How many cases a labelled set holds."""
    query = select(func.count()).where(
        labelled_cases.c.labelled_set == LABELLED_SET[evaluation_set]
    )
    return db.execute(query).scalar_one()


def next_evaluation(
    db: Connection, row: RowMapping
) -> tuple[RowMapping, EvaluationSet]:
    """Return the version a round's next evaluation is of, and its set: the
    round's starting version on the sets of its first evaluations, then its
    version under test once on the evaluation set and twice on the held-out set,
    until the verdict. Raise a 409 for any other, so a version's scores never
    change after its verdict."""
    tried = tried_version(db, row["round_id"])
    if tried is not None and tried["verdict"] is not None:
        raise HTTPException(409, f"Version {tried['number']} already has its verdict")
    version = tried or version_row(db, row["starting_version"])
    sets = EVALUATIONS if tried else row["first_evaluations"]
    done = len(evaluations_of(db, row["round_id"], version["number"]))
    if done >= len(sets):
        raise HTTPException(
            409,
            f"Round {row['number']} has run every evaluation version "
            f"{version['number']} needs",
        )
    return version, sets[done]


def refuse_what_the_round_cant_afford(
    db: Connection, row: RowMapping, version: RowMapping
) -> None:
    """Raise a 409 when the evaluations a version still needs are likely to cost
    more than what's left of the round's limit, so the first of the three checks
    all three."""
    done = len(evaluations_of(db, row["round_id"], version["number"]))
    cases_left = sum(set_size(db, s) for s in EVALUATIONS[done:])
    models = {model.model: model for model in allowed_models(db)}
    current = version_row(db, current_version_number(db))
    per_case = spending.cost_per_case(
        db, models[version["model"]], models[current["model"]]
    )
    estimate, left = cases_left * per_case, left_to_spend(db, row)
    if estimate > left:
        raise HTTPException(
            409,
            f"The evaluations could cost about {dollars(estimate)}, and "
            f"{dollars(left)} of the round's limit is left",
        )


def why_cut_short(db: Connection, row: RowMapping) -> str | None:
    """Say why a round's evaluation was cut short, if it was: its round was
    stopped, or spent its limit before every copy started."""
    if row["round_id"] is None:
        return None
    round_ = round_row(db, row["round_id"])
    why = why_no_case_starts(db, round_)
    unstarted = any(
        case["status"] == Status.RECEIVED for case in cases_of(db, row["run_id"])
    )
    cut = round_["status"] != RoundStatus.OPEN or unstarted
    return why if why and cut else None


def end_cut_short(db: Connection, row: RowMapping, because: str) -> None:
    """Stop an evaluation its round cut short, with why, and the round with it
    when the limit cut short its first evaluations, before its improver runs. The
    round is stopped before its runs, as every stop does, so two stops at the
    same moment wait for each other rather than deadlock."""
    round_ = round_row(db, row["round_id"])
    if row["version"] == round_["starting_version"]:
        stop(db, round_, None, FIRST_EVALUATIONS_CUT_SHORT)
    stop_runs(db, because, runs.c.run_id == row["run_id"])


def mark_finished(db: Connection, run_id: str, summary: dict[str, Any] | None) -> None:
    """Mark a running run finished, with a dispatch's summary. A run stopped
    meanwhile stays stopped, and nothing done to finish it is kept."""
    done = db.execute(
        update(runs)
        .where(runs.c.run_id == run_id, runs.c.status == RunStatus.RUNNING)
        .values(status=RunStatus.FINISHED, finished_at=now(), summary=summary)
    )
    if done.rowcount == 0:
        db.rollback()


def evaluation_row(db: Connection, run_id: str) -> RowMapping:
    """Return an evaluation's row, or raise a 404."""
    row = run_row(db, run_id)
    if row["kind"] != RunKind.EVALUATION:
        raise HTTPException(404, RUN_NOT_FOUND.format(run_id=run_id))
    return row


@router.post(
    "/api/runs/rounds/{round_id}/evaluations",
    operation_id="create_round_evaluation",
    dependencies=[AgentKey],
)
def create_round_evaluation(round_id: str, db: Database) -> Run:
    """Record a round's next whole-set evaluation, on the set it needs next."""
    row = open_round(db, round_id)
    version, evaluation_set = next_evaluation(db, row)
    if version["number"] != row["starting_version"]:
        refuse_what_the_round_cant_afford(db, row, version)
    fields = {
        "evaluation_set": evaluation_set,
        "agents": settings_number(db, row["settings"]).agents,
        "round_id": round_id,
    }
    return evaluation_of(db, fields, version)


@router.put(
    "/api/runs/{run_id}/cases",
    operation_id="record_run_cases",
    dependencies=[AgentKey],
)
def record_run_cases(run_id: str, request: RunCasesRequest, db: Database) -> Run:
    """Record the cases a running dispatch works, in order."""
    if running_run(db, run_id)["kind"] != RunKind.DISPATCH:
        raise HTTPException(409, f"Run {run_id} is not a dispatch")
    known = select(cases.c.case_id).where(cases.c.case_id.in_(request.case_ids))
    missing = set(request.case_ids) - set(db.execute(known).scalars())
    if missing:
        raise HTTPException(404, CASE_NOT_FOUND.format(case_id=min(missing)))
    put_cases(db, run_id, request.case_ids)
    return find_run(db, run_id)


@router.post(
    "/api/runs/{run_id}/finish", operation_id="finish_run", dependencies=[AgentKey]
)
def finish_run(run_id: str, db: Database) -> Run:
    """Finish a run: a dispatch gets its summary, an evaluation its finish or a stop."""
    row = run_row(db, run_id)
    if row["status"] == RunStatus.STOPPED:
        return find_run(db, run_id)
    if row["status"] != RunStatus.RUNNING:
        raise HTTPException(409, NOT_RUNNING.format(run_id=run_id))
    if row["kind"] == RunKind.DISPATCH:
        mark_finished(db, run_id, summarize(cases_of(db, run_id)).model_dump())
    elif because := why_cut_short(db, row):
        end_cut_short(db, row, because)
    else:
        mark_finished(db, run_id, None)
    return find_run(db, run_id)


@router.get(
    "/api/runs/{run_id}", operation_id="get_run", dependencies=[ReviewerOrAgent]
)
def get_run(run_id: str, db: Database) -> Run:
    """Get a run with its cases, for the agent to work it or a reviewer to follow it."""
    return find_run(db, run_id)


@router.post(
    "/api/runs/{run_id}/heartbeat",
    operation_id="record_run_heartbeat",
    dependencies=[AgentKey],
)
def record_run_heartbeat(run_id: str, db: Database) -> Run:
    """Record that the agent is still working a run."""
    run_row(db, run_id)
    db.execute(update(runs).where(runs.c.run_id == run_id).values(heard_at=now()))
    return find_run(db, run_id)


@router.post(
    "/api/runs/{run_id}/failure", operation_id="fail_run", dependencies=[AgentKey]
)
def fail_run(run_id: str, request: FailureRequest, db: Database) -> Run:
    """Stop a run whose work failed, with what went wrong, if it's still running."""
    run_row(db, run_id)
    stop_runs(db, request.reason, runs.c.run_id == run_id)
    return find_run(db, run_id)


def ask_to_work(db: Connection, run_id: str) -> None:
    """Ask the agent to work a run the app created, which is stopped with the
    reason when the agent didn't take it."""
    commit_and_ask(
        db,
        partial(agent_service.work_run, run_id),
        lambda reason: stop_runs(db, reason, runs.c.run_id == run_id),
    )


@router.get(
    "/api/dispatches/latest",
    operation_id="get_latest_dispatch",
    dependencies=[SignedInReviewer],
)
def get_latest_dispatch(db: Database) -> Run | None:
    """Get the newest dispatch with its cases, cost, time and summary, or nothing."""
    query = (
        select(runs.c.run_id)
        .where(runs.c.kind == RunKind.DISPATCH)
        .order_by(runs.c.number.desc())
        .limit(1)
    )
    run_id = db.execute(query).scalar_one_or_none()
    return None if run_id is None else find_run(db, run_id)


@router.post(
    "/api/dispatches",
    operation_id="start_dispatch",
    status_code=202,
    dependencies=[SignedInReviewer],
)
def start_dispatch(request: StartDispatchRequest, db: Database) -> RunStarted:
    """Start a dispatch with up to N payroll agents at once, which the agent works."""
    clear_the_way(db)
    current = version_row(db, current_version_number(db))
    row = new_run(db, RunKind.DISPATCH, request.model_dump(), current)
    ask_to_work(db, row["run_id"])
    return RunStarted(run_id=row["run_id"], number=row["number"])


@router.get(
    "/api/evaluations", operation_id="list_evaluations", dependencies=[SignedInReviewer]
)
def list_evaluations(db: Database) -> list[Evaluation]:
    """List every evaluation, newest first, with its measures."""
    query = (
        select(runs)
        .where(runs.c.kind == RunKind.EVALUATION)
        .order_by(runs.c.number.desc())
    )
    rows = list(db.execute(query).mappings())
    return [
        Evaluation(**scored.model_dump(exclude={"cases"}))
        for scored in score_all(db, rows, expected_labels(db))
    ]


@router.get(
    "/api/evaluations/{run_id}",
    operation_id="get_evaluation",
    dependencies=[SignedInReviewer],
)
def get_evaluation(run_id: str, db: Database) -> ScoredEvaluation:
    """Get one evaluation with its measures and its copies beside their labels."""
    return score(db, evaluation_row(db, run_id), expected_labels(db))


@router.post(
    "/api/evaluations",
    operation_id="start_evaluation",
    status_code=202,
    dependencies=[SignedInReviewer],
)
def start_evaluation(request: StartEvaluationRequest, db: Database) -> RunStarted:
    """Start an evaluation with up to N payroll agents at once for the agent to work."""
    clear_the_way(db)
    current = version_row(db, current_version_number(db))
    run = evaluation_of(db, request.model_dump(), current)
    ask_to_work(db, run.run_id)
    return RunStarted(run_id=run.run_id, number=run.number)
