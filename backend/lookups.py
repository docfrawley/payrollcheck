"""Finding a case, the workers on its latest submission's lines, a project, a
subcontractor, a run, a version, the settings and the models allowed, and the
messages for what isn't found, which more than one of the backend's modules need.
A case, a project or a subcontractor outside the caller's scope isn't found, with
the same message as one that doesn't exist."""

from fastapi import HTTPException
from sqlalchemy import Connection, RowMapping, func, select

from backend.database import (
    case_view,
    cases,
    labelled_cases,
    models_allowed,
    projects,
    rounds,
    runs,
    settings,
    subcontractors,
    submissions,
    versions,
)
from backend.models import (
    LABELLED_SET,
    EvaluationSet,
    ModelAllowed,
    Settings,
    Verdict,
)
from backend.scope import Scope, cases_in, projects_in, subcontractors_in

RUN_NOT_FOUND = "Run {run_id} not found"
CASE_NOT_FOUND = "Case {case_id} not found"
VERSION_NOT_FOUND = "Version {number} not found"
PROJECT_NOT_FOUND = "Project {project_id} not found"
SUBCONTRACTOR_NOT_FOUND = "Subcontractor {subcontractor_id} not found"


def find_case(db: Connection, case_id: str, scope: Scope) -> RowMapping:
    """Return one case's row in the scope, or raise a 404."""
    query = case_view.where(cases.c.case_id == case_id, cases_in(scope))
    row = db.execute(query).mappings().first()
    if row is None:
        raise HTTPException(404, CASE_NOT_FOUND.format(case_id=case_id))
    return row


def find_queue_case(db: Connection, case_id: str, scope: Scope) -> RowMapping:
    """Return one case's row in the queue and the scope, or raise a 404: an
    evaluation's copy, which the Copilot never reads, isn't found."""
    query = case_view.where(
        cases.c.case_id == case_id, cases.c.evaluation_id.is_(None), cases_in(scope)
    )
    row = db.execute(query).mappings().first()
    if row is None:
        raise HTTPException(404, CASE_NOT_FOUND.format(case_id=case_id))
    return row


def workers_by_line(db: Connection, case: RowMapping) -> list[str]:
    """The worker id on each line of a case's latest submission, in line order."""
    lines = db.execute(
        select(submissions.c.lines).where(
            submissions.c.case_id == case["case_id"],
            submissions.c.submission_no == case["latest_submission_no"],
        )
    ).scalar_one()
    return [line["worker_id"] for line in lines]


def project_row(db: Connection, project_id: str, scope: Scope) -> RowMapping:
    """Return one project's row in the scope, or raise a 404."""
    query = select(projects).where(
        projects.c.project_id == project_id, projects_in(scope)
    )
    row = db.execute(query).mappings().first()
    if row is None:
        raise HTTPException(404, PROJECT_NOT_FOUND.format(project_id=project_id))
    return row


def subcontractor_row(
    db: Connection, subcontractor_id: str, scope: Scope
) -> RowMapping:
    """Return one subcontractor's row in the scope, or raise a 404."""
    query = select(subcontractors).where(
        subcontractors.c.subcontractor_id == subcontractor_id,
        subcontractors_in(scope),
    )
    row = db.execute(query).mappings().first()
    if row is None:
        message = SUBCONTRACTOR_NOT_FOUND.format(subcontractor_id=subcontractor_id)
        raise HTTPException(404, message)
    return row


def run_row(db: Connection, run_id: str) -> RowMapping:
    """Return one run's row, or raise a 404."""
    row = db.execute(select(runs).where(runs.c.run_id == run_id)).mappings().first()
    if row is None:
        raise HTTPException(404, RUN_NOT_FOUND.format(run_id=run_id))
    return row


def round_numbers(db: Connection, round_ids: list[str | None]) -> dict[str, int]:
    """Return the numbers of the rounds with these ids, by id, in one query."""
    query = select(rounds.c.round_id, rounds.c.number).where(
        rounds.c.round_id.in_(round_ids)
    )
    return {round_id: number for round_id, number in db.execute(query)}


def round_number(db: Connection, round_id: str | None) -> int | None:
    """Return the number of the round with this id, or none for no round."""
    if round_id is None:
        return None
    return round_numbers(db, [round_id])[round_id]


def version_row(db: Connection, number: int) -> RowMapping:
    """Return one version of the payroll agent's configuration, or raise a 404."""
    query = select(versions).where(versions.c.number == number)
    row = db.execute(query).mappings().first()
    if row is None:
        raise HTTPException(404, VERSION_NOT_FOUND.format(number=number))
    return row


def current_version_number(db: Connection) -> int:
    """Return the current version: the newest one the business's rule kept, which
    is version 1 until a round keeps another."""
    query = select(func.max(versions.c.number)).where(
        versions.c.verdict == Verdict.KEPT
    )
    return db.execute(query).scalar_one()


def current_settings(db: Connection) -> Settings:
    """Return the settings in force: the newest change."""
    newest = select(func.max(settings.c.number)).scalar_subquery()
    query = select(settings).where(settings.c.number == newest)
    return Settings(**db.execute(query).mappings().one())


def allowed_models(db: Connection) -> list[ModelAllowed]:
    """Return the models the payroll agent may use, with their reasoning efforts and
    prices."""
    query = select(models_allowed).order_by(models_allowed.c.position)
    return [ModelAllowed(**row) for row in db.execute(query).mappings()]


def settings_number(db: Connection, number: int) -> Settings:
    """Return the settings as one change left them, such as a round's."""
    query = select(settings).where(settings.c.number == number)
    return Settings(**db.execute(query).mappings().one())


def set_size(db: Connection, evaluation_set: EvaluationSet) -> int:
    """How many cases a labelled set holds."""
    query = select(func.count()).where(
        labelled_cases.c.labelled_set == LABELLED_SET[evaluation_set]
    )
    return db.execute(query).scalar_one()
