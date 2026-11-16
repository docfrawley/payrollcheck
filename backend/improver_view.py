"""What the improver reads in a round, in one read: the current version and its
scores, the development set's mistakes and weakest notices from its latest
evaluation there, the reviewers' corrections since the last round finished, the
earlier rounds, the settings, the rule, the spending and what the payroll agent may
use. From the held-out set it holds the scores alone. Each list is capped, the most
telling first, with its total."""

from sqlalchemy import Connection, RowMapping, select

from backend import verdict
from backend.database import rounds
from backend.grading import open_exceptions_in
from backend.lookups import (
    allowed_models,
    current_version_number,
    settings_number,
    version_row,
)
from backend.models import (
    CaseResults,
    EarlierRound,
    EvaluationSet,
    ImproverView,
    Listed,
    PayrollAgentVersion,
    RoundStatus,
    ScoredCase,
    ScoredEvaluation,
    WeakNotice,
)
from backend.notices import drafts_of, edited_between
from backend.overrides import overrides_between
from backend.parameters import PARAMETERS
from backend.round_state import spending_of, stored_measures, tried_version
from backend.scoreboard import (
    Expected,
    expected_labels,
    round_evaluations,
    score,
    version_scores,
)

# How much of each list the improver sees (decision 7 of the plan).
MOST_MISTAKES = 30
MOST_WEAK_NOTICES = 5
MOST_OVERRIDES = 40
MOST_NOTICE_EDITS = 10


def went_wrong(case: ScoredCase) -> bool:
    """A copy with a miss, a wrong shortfall, a false exception or a wrong
    screening."""
    return (
        case.misses > 0
        or case.false_exceptions > 0
        or any(label.result == "shortfall_wrong" for label in case.labels)
        or case.screening_expected != case.screening_found
    )


def to_results(case: ScoredCase) -> CaseResults:
    """A copy as the improver reads it: under its original's id, each label it
    missed or got the shortfall of wrong beside the exception that caught it, and
    each exception that matched no label."""
    return CaseResults(
        case_id=case.copy_of,
        missed=[label for label in case.labels if label.result != "caught"],
        false_exceptions=[found for found in case.exceptions if not found.matched],
        screening_expected=case.screening_expected,
        screening_found=case.screening_found,
    )


def mistakes(evaluation: ScoredEvaluation) -> Listed[CaseResults]:
    """The development copies the version got wrong: misses, wrong shortfalls and
    false exceptions first, then screenings alone, each kind by case id."""
    wrong = [to_results(case) for case in evaluation.cases if went_wrong(case)]
    ordered = sorted(
        wrong,
        key=lambda case: (not (case.missed or case.false_exceptions), case.case_id),
    )
    return Listed[CaseResults](total=len(ordered), shown=ordered[:MOST_MISTAKES])


def weakest_notices(db: Connection, evaluation: ScoredEvaluation) -> Listed[WeakNotice]:
    """The development copies' notices the judge scored lowest, each with its
    exceptions and the four points. A notice it couldn't grade isn't among them."""
    graded = [
        (case.case_id, case.copy_of, case.notice)
        for case in evaluation.cases
        if case.notice is not None and case.notice.score is not None
    ]
    lowest = sorted(graded, key=lambda each: (each[2].score, each[1]))
    shown = lowest[:MOST_WEAK_NOTICES]
    exceptions = open_exceptions_in(db, evaluation.run_id) if shown else {}
    drafts = drafts_of(db, [case_id for case_id, _, _ in shown])
    return Listed[WeakNotice](
        total=len(graded),
        shown=[
            WeakNotice(
                case_id=copy_of,
                notice=drafts.get(case_id),
                exceptions=exceptions.get(case_id, []),
                grade=notice,
            )
            for case_id, copy_of, notice in shown
        ],
    )


def corrections_since(db: Connection, row: RowMapping) -> str | None:
    """The start of the newest earlier round that finished, from which this round
    reads the reviewers' corrections, or none before any. A stopped round doesn't
    count, so what it never used is read by the next (decision 5)."""
    query = (
        select(rounds.c.started_at)
        .where(rounds.c.number < row["number"], rounds.c.status == RoundStatus.FINISHED)
        .order_by(rounds.c.number.desc())
        .limit(1)
    )
    return db.execute(query).scalar_one_or_none()


def earlier_round(db: Connection, row: RowMapping) -> EarlierRound:
    """What an earlier round tried and how it came out."""
    version = tried_version(db, row["round_id"])
    tried = dict(version) if version else {}
    return EarlierRound(
        round=row["number"],
        recipe_version=row["recipe"],
        version=tried.get("number"),
        model=tried.get("model"),
        reasoning_effort=tried.get("reasoning_effort"),
        reason=tried.get("reason"),
        held_out_before=stored_measures(row["held_out_before"]),
        held_out_after=stored_measures(row["held_out_after"]),
        verdict=tried.get("verdict"),
        why=tried.get("verdict_reason"),
    )


def latest_development(
    db: Connection, version: int, expected: Expected
) -> ScoredEvaluation | None:
    """A version's latest round evaluation counted as the development set's,
    scored."""
    latest = round_evaluations(db, version)[EvaluationSet.DEVELOPMENT][-1:]
    return score(db, latest[0], expected) if latest else None


def improver_view(db: Connection, row: RowMapping) -> ImproverView:
    """What the improver reads in a round, as the lab's read_results gives it, with
    the two signals: the development set's mistakes and the reviewers'
    corrections. The window of corrections ends at the round's own start, so the
    view is the same however often the improver reads it."""
    current = version_row(db, current_version_number(db))
    settings = settings_number(db, row["settings"])
    expected = expected_labels(db)
    development = latest_development(db, current["number"], expected)
    since = corrections_since(db, row)
    start, end = since or "", row["started_at"]
    earlier = select(rounds).where(rounds.c.number < row["number"])
    overridden, overrides = overrides_between(db, start, end, MOST_OVERRIDES)
    edited, edits = edited_between(db, start, end, MOST_NOTICE_EDITS)
    return ImproverView(
        current_version=PayrollAgentVersion(**current),
        scores=version_scores(db, current["number"], expected),
        development_mistakes=(
            mistakes(development) if development else Listed(total=0, shown=[])
        ),
        weakest_notices=(
            weakest_notices(db, development)
            if development
            else Listed(total=0, shown=[])
        ),
        corrections_since=since,
        overrides=Listed(total=overridden, shown=overrides),
        notice_edits=Listed(total=edited, shown=edits),
        earlier_rounds=[
            earlier_round(db, earlier_row)
            for earlier_row in db.execute(earlier.order_by(rounds.c.number)).mappings()
        ],
        objectives_on_the_held_out_set=settings.objectives,
        noise=settings.noise,
        tolerance=settings.tolerance,
        rule=verdict.RULE,
        spending=spending_of(db, row),
        models_allowed=allowed_models(db),
        parameters_allowed=PARAMETERS,
    )


def cited_cases(view: ImproverView) -> set[str]:
    """Every case id the view holds, which a proposal may cite."""
    return {
        *(case.case_id for case in view.development_mistakes.shown),
        *(notice.case_id for notice in view.weakest_notices.shown),
        *(override.case_id for override in view.overrides.shown),
        *(edit.case_id for edit in view.notice_edits.shown),
    }
