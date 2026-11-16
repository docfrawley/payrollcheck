"""The catalogue of the check tools' tunable parameters, and its bounds."""

import pytest
from fastapi import HTTPException

from backend.parameters import FIRST_PARAMETERS, refuse_out_of_bounds


@pytest.mark.parametrize("cents", [0, 100])
def test_a_tolerance_inside_its_bounds_is_taken(cents):
    refuse_out_of_bounds({"rounding_tolerance_cents": cents})


@pytest.mark.parametrize(
    ("parameters", "why"),
    [
        (
            {"rounding_tolerance_cents": -1},
            "rounding_tolerance_cents must be a whole number of cents from 0 to "
            "100, not -1.",
        ),
        (
            {"rounding_tolerance_cents": 101},
            "rounding_tolerance_cents must be a whole number of cents from 0 to "
            "100, not 101.",
        ),
        (
            {"rounding_tolerance_cents": 2.5},
            "rounding_tolerance_cents must be a whole number of cents from 0 to "
            "100, not 2.5.",
        ),
        (
            {"rounding_tolerance_cents": True},
            "rounding_tolerance_cents must be a whole number of cents from 0 to "
            "100, not True.",
        ),
        (
            {"rounding_tolerance_cents": 0, "overtime_factor": 2, "days": 10},
            "There is no parameter days, overtime_factor.",
        ),
        ({}, "rounding_tolerance_cents is missing."),
    ],
    ids=["below", "above", "a fraction", "not a number", "unknown", "missing"],
)
def test_parameters_outside_the_catalogue_are_refused(parameters, why):
    with pytest.raises(HTTPException) as refused:
        refuse_out_of_bounds(parameters)
    assert (refused.value.status_code, refused.value.detail) == (422, why)


def test_version_1_has_the_catalogues_first_values():
    assert FIRST_PARAMETERS == {"rounding_tolerance_cents": 0}
