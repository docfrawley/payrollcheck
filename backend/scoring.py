"""The lab's measures of the agent's work against the handlers' decisions: whether an
answer is right, what a mistake costs, and an evaluation's measures."""

from statistics import fmean
from typing import NamedTuple

from backend.models import DecisionKind, Measures, ScoredCase

WRONGFUL_DECLINE = 1500
NEEDLESS_REFERRAL = 50
# A payout within a dollar of the handler's is right.
PAYOUT_TOLERANCE = 1


class Answer(NamedTuple):
    """A decision on a case and its payout, the agent's or a handler's."""

    decision: DecisionKind
    payout: float


def answer_of(decision: DecisionKind | None, payout: float | None) -> Answer:
    """Return the agent's answer on a case, with a case it didn't decide counted
    as a referral."""
    if decision is None:
        return Answer(DecisionKind.REFER, 0)
    return Answer(decision, payout or 0)


def is_right(answer: Answer, expected: Answer) -> bool:
    """Say whether the decision matches the handler's and the payout is within a
    dollar."""
    return (
        answer.decision == expected.decision
        and abs(answer.payout - expected.payout) <= PAYOUT_TOLERANCE
    )


def mistake_cost(answer: Answer, expected: Answer) -> float:
    """Return what the agent's answer costs UnderCover against the handler's: a
    wrongful decline, a wrongful approval's payout whether or not it was paid, a
    needless referral, or the difference on a right approval."""
    if answer.decision == expected.decision:
        if answer.decision == DecisionKind.APPROVE:
            return abs(answer.payout - expected.payout)
        return 0
    if answer.decision == DecisionKind.DECLINE:
        return WRONGFUL_DECLINE
    if answer.decision == DecisionKind.APPROVE:
        return answer.payout
    return NEEDLESS_REFERRAL


def average_grade(cases: list[ScoredCase]) -> float | None:
    """Return the judge's average grade over the cases it graded, or nothing when
    it graded none."""
    scores = [c.grade.score for c in cases if c.grade]
    return fmean(scores) if scores else None


def measures(
    cases: list[ScoredCase], model_cost: float, run_seconds: float | None
) -> Measures:
    """Score an evaluation from its cases, its model cost and its time."""
    count = len(cases)
    agreed = [
        answer_of(c.decision, c.payout).decision == c.handler_decision for c in cases
    ]
    referred = [
        answer_of(c.decision, c.payout).decision == DecisionKind.REFER for c in cases
    ]
    return Measures(
        decision_accuracy=sum(agreed) / count,
        accuracy=sum(c.right for c in cases) / count,
        cost_of_mistakes=sum(c.mistake_cost for c in cases),
        straight_through=sum(not r for r in referred) / count,
        grade=average_grade(cases),
        model_cost_per_case=model_cost / count,
        seconds_per_case=sum(c.seconds for c in cases) / count,
        run_seconds=run_seconds,
    )
