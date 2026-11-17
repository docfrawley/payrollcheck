"""The business's rule that keeps or rolls back a new version, with measures worked
out by hand: the catch rate, false exceptions per 100 payrolls, shortfall accuracy
and the notice score as differences, cost and time as fractions."""

from statistics import fmean

import pytest

from backend.models import Measures, Settings
from backend.tests.settings_requests import STARTING
from backend.verdict import keep_or_roll_back

SETTINGS = Settings(**STARTING, number=1, changed_by=None, changed_at="2026-10-04")


def scores(**given):
    """A version's held-out scores: the current version's below, with the measures
    given changed."""
    measures = {
        "catch_rate": 0.93,
        "caught": 0,
        "labels": 0,
        "false_exceptions": 0,
        "false_per_100": 2.0,
        "shortfall_accuracy": 1.0,
        "screening_caught": 0,
        "screening_expected": 0,
        "notice_score": 0.85,
        "notices_graded": 10,
        "model_cost_per_case": 0.0010,
        "seconds_per_case": 20,
        "run_seconds": 60,
    }
    return Measures(**measures | given)


OLD = scores()


@pytest.mark.parametrize(
    ("new", "verdict", "reason"),
    [
        (scores(catch_rate=0.99), "kept", "catch_rate improved"),
        (scores(false_per_100=0.9), "kept", "false_per_100 improved"),
        (
            scores(false_per_100=1.0),
            "rolled_back",
            "no score improved by more than the noise",
        ),
        (
            scores(catch_rate=0.99, false_per_100=3.1),
            "rolled_back",
            "it missed the objectives on false_per_100",
        ),
        (
            scores(catch_rate=0.99, false_per_100=2.5),
            "kept",
            "catch_rate improved",
        ),
        (scores(notice_score=0.96), "kept", "notice_score improved"),
        (
            scores(catch_rate=0.99, notice_score=0.82),
            "kept",
            "catch_rate improved",
        ),
        (
            scores(catch_rate=0.99, model_cost_per_case=0.0019),
            "kept",
            "catch_rate improved",
        ),
        (
            scores(catch_rate=0.99, model_cost_per_case=0.0021),
            "rolled_back",
            "cost_per_case got worse",
        ),
        (scores(model_cost_per_case=0.0008), "kept", "cost_per_case improved"),
        (
            scores(catch_rate=0.99, seconds_per_case=26),
            "rolled_back",
            "seconds_per_case got worse",
        ),
        (
            scores(catch_rate=0.97),
            "rolled_back",
            "no score improved by more than the noise",
        ),
        (
            scores(catch_rate=0.90, model_cost_per_case=0.0008),
            "rolled_back",
            "it missed the objectives on catch_rate",
        ),
        (
            scores(catch_rate=0.99, shortfall_accuracy=0.98),
            "rolled_back",
            "it missed the objectives on shortfall_accuracy",
        ),
        (
            scores(catch_rate=0.99, notice_score=0.79),
            "rolled_back",
            "it missed the objectives on notice_score",
        ),
        (
            scores(catch_rate=0.99, notice_score=None, notices_graded=0),
            "rolled_back",
            "it has no notice_score",
        ),
        (None, "rolled_back", "it has no scores"),
    ],
)
def test_the_rule(new, verdict, reason):
    assert keep_or_roll_back(new, OLD, SETTINGS) == (verdict, reason)


def test_false_exceptions_that_rise_by_more_than_the_tolerance_roll_it_back():
    old = scores(false_per_100=0.5)
    assert keep_or_roll_back(
        scores(catch_rate=0.99, false_per_100=1.6), old, SETTINGS
    ) == ("rolled_back", "false_per_100 got worse")
    assert keep_or_roll_back(
        scores(catch_rate=0.99, false_per_100=1.4), old, SETTINGS
    ) == ("kept", "catch_rate improved")


def test_any_fall_in_shortfall_accuracy_rolls_it_back_and_any_rise_improves():
    settings = SETTINGS.model_copy(
        update={
            "objectives": SETTINGS.objectives.model_copy(
                update={"shortfall_accuracy": 0.9}
            )
        }
    )
    old = scores(shortfall_accuracy=0.98)
    assert keep_or_roll_back(
        scores(catch_rate=0.99, shortfall_accuracy=0.97), old, settings
    ) == ("rolled_back", "shortfall_accuracy got worse")
    assert keep_or_roll_back(scores(shortfall_accuracy=0.99), old, settings) == (
        "kept",
        "shortfall_accuracy improved",
    )


def test_a_catch_rate_that_fell_by_more_than_its_tolerance_is_rolled_back():
    old = scores(catch_rate=1.0)
    assert keep_or_roll_back(
        scores(catch_rate=0.94, model_cost_per_case=0.0005), old, SETTINGS
    ) == ("rolled_back", "catch_rate got worse")


def test_a_measure_neither_version_has_is_left_out():
    old = scores(notice_score=None, notices_graded=0)
    new = scores(catch_rate=0.99, notice_score=None, notices_graded=0)
    assert keep_or_roll_back(new, old, SETTINGS) == ("kept", "catch_rate improved")


def test_a_measure_only_the_new_version_has_meets_its_objective_uncompared():
    old = scores(notice_score=None, notices_graded=0)
    assert keep_or_roll_back(
        scores(catch_rate=0.99, notice_score=0.5), old, SETTINGS
    ) == ("rolled_back", "it missed the objectives on notice_score")
    assert keep_or_roll_back(scores(notice_score=0.99), old, SETTINGS) == (
        "rolled_back",
        "no score improved by more than the noise",
    )


def test_with_no_held_out_scores_to_compare_nothing_improved():
    assert keep_or_roll_back(scores(catch_rate=0.99), None, SETTINGS) == (
        "rolled_back",
        "no score improved by more than the noise",
    )


def test_a_fall_of_exactly_the_tolerance_isnt_worse():
    # 1.00 - 0.95 is a hair over 0.05 in binary.
    assert keep_or_roll_back(
        scores(catch_rate=0.95, model_cost_per_case=0.0005),
        scores(catch_rate=1.0),
        SETTINGS,
    ) == ("kept", "cost_per_case improved")


def test_a_rise_of_exactly_the_noise_isnt_an_improvement():
    assert keep_or_roll_back(
        scores(catch_rate=0.98), scores(catch_rate=0.93), SETTINGS
    ) == ("rolled_back", "no score improved by more than the noise")


def test_an_average_exactly_at_the_objective_meets_it():
    # 45 of 50 and 47 of 50 average to 0.92, which reads 0.9199999999999999.
    average = fmean([45 / 50, 47 / 50])
    assert average < 0.92
    assert keep_or_roll_back(
        scores(catch_rate=average, model_cost_per_case=0.0005),
        scores(catch_rate=0.92),
        SETTINGS,
    ) == ("kept", "cost_per_case improved")


def test_a_cost_from_nothing_is_worse_however_small():
    old = scores(model_cost_per_case=0)
    assert keep_or_roll_back(
        scores(catch_rate=0.99, model_cost_per_case=0), old, SETTINGS
    ) == ("kept", "catch_rate improved")
    assert keep_or_roll_back(
        scores(catch_rate=0.99, model_cost_per_case=0.0001), old, SETTINGS
    ) == ("rolled_back", "cost_per_case got worse")


def test_a_version_with_no_shortfall_accuracy_where_the_current_has_one():
    assert keep_or_roll_back(
        scores(catch_rate=0.99, shortfall_accuracy=None), OLD, SETTINGS
    ) == ("rolled_back", "it has no shortfall_accuracy")
