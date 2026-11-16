"""The strict scoring on hand-made exceptions: a rule in the same family isn't a
catch, a shortfall a cent out is caught but wrong, a flagged decoy is false and so
is every exception on a flagged copy, with measures worked out by hand."""

import pytest

from backend import scoring
from backend.models import NoticeGradeRecord, NoticeResult, ScoredCase, Status
from backend.scoring import Label, Raised

SHORT = Label("rate.base_short", "W-001", 1, 3200)
LATE = Label("timeliness.late", None, None, None)


def raised(
    rule: str = "rate.base_short",
    worker: str | None = "W-001",
    shortfall: int | None = 3200,
    number: int = 1,
) -> Raised:
    return Raised(number, rule, worker, 1, shortfall)


def results(labels, found, flagged=False):
    matches, exceptions = scoring.match_copy(labels, found, flagged)
    return [m.result for m in matches], [e.matched for e in exceptions]


def test_a_label_is_caught_by_its_rule_and_worker_to_the_cent():
    assert results([SHORT], [raised()]) == (["caught"], [True])


def test_another_rule_in_the_same_family_is_not_a_catch():
    found = [raised(rule="rate.fringe_short")]
    assert results([SHORT], found) == (["missed"], [False])


def test_another_worker_is_not_a_catch_and_the_line_isnt_compared():
    assert results([SHORT], [raised(worker="W-002")]) == (["missed"], [False])
    other_line = Raised(1, "rate.base_short", "W-001", 7, 3200)
    assert results([SHORT], [other_line]) == (["caught"], [True])


def test_a_shortfall_a_cent_out_is_caught_but_wrong():
    assert results([SHORT], [raised(shortfall=3201)]) == (["shortfall_wrong"], [True])


def test_a_rule_about_the_payroll_matches_with_no_worker():
    assert results([LATE], [raised("timeliness.late", None, None)]) == (
        ["caught"],
        [True],
    )


def test_an_exception_on_a_decoy_is_false():
    assert results([], [raised()]) == ([], [False])


def test_every_exception_on_a_flagged_copy_is_false():
    assert results([SHORT], [raised()], flagged=True) == (["missed"], [False])


def scored(labels, found, flagged=False, screening=False, notice=None):
    matches, exceptions = scoring.match_copy(labels, found, flagged)
    return ScoredCase(
        case_id="PC-0101-E1",
        project_id="PRJ-01",
        project_name="Lincoln School renovation",
        subcontractor_id="SUB-01",
        subcontractor_name="Garden State Electric LLC",
        week_ending="2026-09-06",
        status=Status.AWAITING_REVIEW,
        screening_flag=flagged,
        agent_failed=False,
        open_exceptions=len(found),
        shortfall_cents=0,
        started_at=None,
        seconds=10.0,
        model_cost=0,
        copy_of="PC-0101",
        labels=matches,
        exceptions=exceptions,
        screening_expected=screening,
        screening_found=flagged,
        misses=sum(m.result == "missed" for m in matches),
        false_exceptions=scoring.false_count(exceptions, flagged, screening),
        notice=notice,
    )


def graded(score, result=NoticeResult.GRADED):
    """A notice's grade: its score, with the four points left out of the sums."""
    return NoticeGradeRecord(
        result=result,
        score=score,
        covers_every_exception=None,
        amounts_match=None,
        plain_language=None,
        no_legal_interpretation=None,
        cost=0,
    )


def test_an_evaluations_measures_as_worked_out_by_hand():
    cases = [
        scored([SHORT, LATE], [raised(), raised("timeliness.late", None, None, 2)]),
        scored([SHORT], [raised(shortfall=3100)]),
        scored([LATE], []),
        scored([], [raised()], flagged=True, screening=True),
        scored([], [raised(rule="arithmetic.gross")]),
        scored([], [], screening=True),
        scored([], [], flagged=True),
        scored([], [], flagged=True),
    ]
    measures = scoring.measures(cases, model_cost=0.08, run_seconds=30.0)
    # 3 of the 4 exception labels caught, one of the two money labels with the
    # wrong shortfall. The flagged copy's exception, the gross exception and the
    # flags on the two decoys are false: 4 of 8 payrolls. The screening missed
    # one of its two flags, which the catch rate doesn't count.
    assert (measures.caught, measures.labels, measures.catch_rate) == (3, 4, 0.75)
    assert measures.shortfall_accuracy == 0.5
    assert (measures.false_exceptions, measures.false_per_100) == (4, 50.0)
    assert (measures.screening_caught, measures.screening_expected) == (1, 2)
    assert measures.model_cost_per_case == 0.01
    assert (measures.seconds_per_case, measures.run_seconds) == (10.0, 30.0)


def test_with_no_money_caught_the_shortfall_accuracy_is_none():
    measures = scoring.measures([scored([LATE], [])], 0, None)
    assert (measures.catch_rate, measures.shortfall_accuracy) == (0.0, None)


def test_a_flagged_decoy_is_a_false_exception():
    decoy = scored([], [], flagged=True, screening=False)
    expected = scored([], [], flagged=True, screening=True)
    assert (decoy.false_exceptions, expected.false_exceptions) == (1, 0)
    measures = scoring.measures([decoy, expected], 0, None)
    assert (measures.screening_caught, measures.screening_expected) == (1, 1)
    assert measures.false_exceptions == 1


def test_the_notice_score_averages_the_graded_notices_and_none_counts_zero():
    cases = [
        scored([SHORT], [raised()], notice=graded(0.9)),
        scored([SHORT], [raised()], notice=graded(0.5)),
        scored(
            [LATE],
            [raised("timeliness.late", None, None, 2)],
            notice=graded(0.0, NoticeResult.NO_NOTICE),
        ),
        scored([SHORT], [raised()], notice=graded(None, NoticeResult.NOT_GRADED)),
        scored([], []),
    ]
    measures = scoring.measures(cases, 0, None)
    # The ungraded notice is left out, and the copy with nothing open needs none.
    assert measures.notices_graded == 3
    assert measures.notice_score == pytest.approx((0.9 + 0.5 + 0.0) / 3)


def test_with_no_notice_graded_there_is_no_notice_score():
    measures = scoring.measures(
        [scored([SHORT], [raised()], notice=graded(None, NoticeResult.NOT_GRADED))],
        0,
        None,
    )
    assert (measures.notice_score, measures.notices_graded) == (None, 0)
