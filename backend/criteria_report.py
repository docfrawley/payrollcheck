"""The success criteria in docs/SPEC.md as the Copilot reports them, every figure
worked out in code: the first four from the current version's latest finished
whole development-set evaluation, with success_criteria.py; the fifth, that no
case reaches Accepted without a reviewer's sign-off, from our records in the
reviewer's scope; and the sixth and seventh as outside what the Copilot can check
of itself."""

from sqlalchemy import Connection, RowMapping, func, select

from backend import spending
from backend import success_criteria as agreed
from backend.database import cases, runs
from backend.lookups import (
    allowed_models,
    current_version_number,
    set_size,
    version_row,
)
from backend.models import (
    CriterionReport,
    EvaluationMeasured,
    EvaluationSet,
    LabelledSet,
    RunKind,
    RunStatus,
    Status,
    SuccessCriteria,
)
from backend.money import dollars
from backend.scope import Scope, queue_cases_in
from backend.scoreboard import decoys_of, expected_labels, score

# Each criterion by its number, as docs/SPEC.md lists them.
NAMES = (
    "Seeded errors caught, with every shortfall right",
    "Hidden-instruction payrolls flagged",
    "False exceptions on the development set",
    "The mid-project rate increase and the later determination",
    "No case Accepted without a reviewer's sign-off",
    "The Copilot answers its six questions",
    "Deployed on AWS AgentCore",
)
FROM_EVALUATION = "Evaluation {number}, of version {version} on the development set"
NEEDS = (
    "Criteria 1 to 4 need a finished evaluation of version {version} on the whole "
    "development set, {size} cases, {cost}"
)
COST = "about {amount} of model calls"
NO_COST_YET = "whose cost can't be estimated until a run on its model has finished"
NOT_YET = "No finished development-set evaluation of the current version"
SIGNED_OFF = "Every Accepted case in your projects names its reviewer and the day"
UNSIGNED = "{count} Accepted without a sign-off"
FROM_RECORDS = "Our records of the cases in your projects"
OUTSIDE = "Outside what the Copilot can check of itself"
# Why each criterion it can't check is outside it, by number.
OUTSIDE_WHY = {
    6: "It would be grading its own answers: the live acceptance checks measure it",
    7: "Its deployment isn't in our records",
}


def success_criteria(db: Connection, scope: Scope) -> SuccessCriteria:
    """The seven criteria with their figures, in a fixed number of queries."""
    version = current_version_number(db)
    row = latest_evaluation(db, version)
    return SuccessCriteria(
        current_version=version,
        evaluation=None
        if row is None
        else EvaluationMeasured(
            run_id=row["run_id"],
            number=row["number"],
            version=row["version"],
            finished_at=row["finished_at"],
        ),
        needs=None if row is not None else needs(db, version),
        criteria=[
            *measured(db, row),
            signed_off(db, scope),
            *(
                CriterionReport(
                    number=number,
                    name=NAMES[number - 1],
                    target=None,
                    figure=OUTSIDE,
                    met=None,
                    source=why,
                )
                for number, why in OUTSIDE_WHY.items()
            ),
        ],
    )


def needs(db: Connection, version: int) -> str:
    """The evaluation criteria 1 to 4 need, with what it would likely cost, as a
    round's evaluations are estimated."""
    size = set_size(db, EvaluationSet.DEVELOPMENT)
    models = {model.model: model for model in allowed_models(db)}
    model = models[version_row(db, version)["model"]]
    per_case = spending.cost_per_case(db, model, model)
    cost = COST.format(amount=dollars(size * per_case)) if per_case else NO_COST_YET
    return NEEDS.format(version=version, size=size, cost=cost)


def latest_evaluation(db: Connection, version: int) -> RowMapping | None:
    """The version's latest finished evaluation of the whole development set."""
    query = (
        select(runs)
        .where(
            runs.c.kind == RunKind.EVALUATION,
            runs.c.evaluation_set == EvaluationSet.DEVELOPMENT,
            runs.c.status == RunStatus.FINISHED,
            runs.c.version == version,
        )
        .order_by(runs.c.number.desc())
        .limit(1)
    )
    return db.execute(query).mappings().first()


def measured(db: Connection, row: RowMapping | None) -> list[CriterionReport]:
    """Criteria 1 to 4 from the evaluation, or saying which they need."""
    if row is None:
        return [
            CriterionReport(
                number=number,
                name=NAMES[number - 1],
                target=None,
                figure=None,
                met=None,
                source=NOT_YET,
            )
            for number in range(1, 5)
        ]
    decoys = decoys_of(db, LabelledSet.DEVELOPMENT)
    scored = agreed.success_criteria(score(db, row, expected_labels(db)), decoys)
    source = FROM_EVALUATION.format(number=row["number"], version=row["version"])
    return [
        CriterionReport(
            number=number,
            name=NAMES[number - 1],
            target=criterion.title,
            figure=criterion.figure,
            met=criterion.met,
            source=source,
        )
        for number, criterion in enumerate(scored, start=1)
    ]


def signed_off(db: Connection, scope: Scope) -> CriterionReport:
    """Criterion 5: every Accepted case in scope has a reviewer and a sign-off
    date; the figure is how many don't."""
    query = select(func.count()).where(
        cases.c.status == Status.ACCEPTED,
        queue_cases_in(scope),
        cases.c.reviewed_by.is_(None) | cases.c.reviewed_on.is_(None),
    )
    unsigned = db.execute(query).scalar_one()
    return CriterionReport(
        number=5,
        name=NAMES[4],
        target=SIGNED_OFF,
        figure=UNSIGNED.format(count=unsigned),
        met=unsigned == 0,
        source=FROM_RECORDS,
    )
