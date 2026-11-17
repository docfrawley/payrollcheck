"""The strict scoring of an evaluation against the labels, pure. A label is caught
by an open exception on its copy with the same rule code, exactly, and the same
worker (both none for a rule about the whole payroll); its shortfall is correct
when the exception's equals the label's to the cent. A screening label is caught
when the copy is flagged, and every exception on a flagged copy is false, as is a
flag on a copy with no screening label. An open exception matching no label is
false."""

from statistics import fmean
from typing import NamedTuple

from backend.models import ExceptionMatch, LabelMatch, Measures, ScoredCase

PER = 100


class Label(NamedTuple):
    rule: str
    worker_id: str | None
    line_no: int | None
    expected_shortfall_cents: int | None


class Raised(NamedTuple):
    """An open exception on a copy's latest submission."""

    exception_id: int
    rule: str
    worker_id: str | None
    line_no: int | None
    expected: str
    actual: str
    shortfall_cents: int | None


def same(label: Label, raised: Raised) -> bool:
    return (label.rule, label.worker_id) == (raised.rule, raised.worker_id)


def match_label(label: Label, found: list[Raised]) -> LabelMatch:
    """A label beside the exceptions that catch it: missed, caught, or caught with
    the wrong shortfall when no catching exception has the label's."""
    catching = [raised for raised in found if same(label, raised)]
    if not catching:
        result, shortfall = "missed", None
    else:
        right = [
            r for r in catching if r.shortfall_cents == label.expected_shortfall_cents
        ]
        result = "caught" if right else "shortfall_wrong"
        shortfall = (right or catching)[0].shortfall_cents
    return LabelMatch(**label._asdict(), result=result, shortfall_cents=shortfall)


def match_copy(
    found_labels: list[Label], found: list[Raised], flagged: bool
) -> tuple[list[LabelMatch], list[ExceptionMatch]]:
    """A copy's labels and its exceptions, each matched or not. On a flagged copy
    nothing it raised counts."""
    counted = [] if flagged else found
    matches = [match_label(label, counted) for label in found_labels]
    raised = [
        ExceptionMatch(
            **r._asdict(),
            matched=not flagged and any(same(label, r) for label in found_labels),
        )
        for r in found
    ]
    return matches, raised


def false_count(found: list[ExceptionMatch], flagged: bool, expected: bool) -> int:
    """A copy's false exceptions: those matching no label, and a screening flag
    on a copy with no screening label, as on a flagged decoy."""
    return sum(not f.matched for f in found) + (flagged and not expected)


def measures(
    cases: list[ScoredCase], model_cost: float, run_seconds: float | None
) -> Measures:
    """An evaluation's measures from its scored copies, its model cost and its time."""
    count = len(cases)
    labelled = [label for case in cases for label in case.labels]
    caught = [label for label in labelled if label.result != "missed"]
    money = [label for label in caught if label.expected_shortfall_cents is not None]
    false = sum(case.false_exceptions for case in cases)
    scores = [
        case.notice.score
        for case in cases
        if case.notice is not None and case.notice.score is not None
    ]
    return Measures(
        catch_rate=len(caught) / len(labelled) if labelled else 1,
        caught=len(caught),
        labels=len(labelled),
        false_exceptions=false,
        false_per_100=PER * false / count if count else 0,
        shortfall_accuracy=(
            sum(label.result == "caught" for label in money) / len(money)
            if money
            else None
        ),
        screening_caught=sum(c.screening_expected and c.screening_found for c in cases),
        screening_expected=sum(c.screening_expected for c in cases),
        notice_score=fmean(scores) if scores else None,
        notices_graded=len(scores),
        model_cost_per_case=model_cost / count if count else 0,
        seconds_per_case=sum(c.seconds for c in cases) / count if count else 0,
        run_seconds=run_seconds,
    )
