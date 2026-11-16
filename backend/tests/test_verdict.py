"""The business's rule that keeps or rolls back a new version, with measures worked
out by hand: the catch rate as a difference, cost and time as fractions. Until
stage 5 it needs no grade."""

import pytest

from backend.models import Measures, Settings
from backend.tests.settings_requests import STARTING
from backend.verdict import keep_or_roll_back

SETTINGS = Settings(**STARTING, number=1, changed_by=None, changed_at="2026-10-04")


def scores(catch_rate, cost, seconds):
    return Measures(
        catch_rate=catch_rate,
        caught=0,
        labels=0,
        false_exceptions=0,
        false_per_100=0,
        shortfall_accuracy=None,
        screening_caught=0,
        screening_expected=0,
        model_cost_per_case=cost,
        seconds_per_case=seconds,
        run_seconds=60,
    )


OLD = scores(0.93, 0.0010, 20)


@pytest.mark.parametrize(
    ("new", "verdict", "reason"),
    [
        (scores(0.99, 0.0019, 24), "kept", "catch_rate improved"),
        (scores(0.99, 0.0021, 24), "rolled_back", "cost_per_case got worse"),
        (scores(0.93, 0.0008, 20), "kept", "cost_per_case improved"),
        (scores(0.93, 0.0010, 26), "rolled_back", "seconds_per_case got worse"),
        (
            scores(0.97, 0.0010, 20),
            "rolled_back",
            "no score improved by more than the noise",
        ),
        (
            scores(0.90, 0.0008, 20),
            "rolled_back",
            "it missed the objectives on catch_rate",
        ),
        (None, "rolled_back", "it has no scores"),
    ],
)
def test_the_rule(new, verdict, reason):
    assert keep_or_roll_back(new, OLD, SETTINGS) == (verdict, reason)


def test_a_catch_rate_that_fell_by_more_than_its_tolerance_is_rolled_back():
    old = scores(1.0, 0.0010, 20)
    assert keep_or_roll_back(scores(0.94, 0.0005, 20), old, SETTINGS) == (
        "rolled_back",
        "catch_rate got worse",
    )


def test_with_no_held_out_scores_to_compare_nothing_improved():
    assert keep_or_roll_back(scores(0.99, 0.001, 20), None, SETTINGS) == (
        "rolled_back",
        "no score improved by more than the noise",
    )
