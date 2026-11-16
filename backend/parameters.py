"""The check tools' tunable parameters: the catalogue of what a version may set,
each with its bounds, version 1's values, and the refusal of a set of parameters
that doesn't keep to it. The business sets the bounds; the improver proposes
values inside them."""

from typing import Any

from fastapi import HTTPException

from backend.models import ParameterAllowed, ParameterValue

PARAMETERS = [
    ParameterAllowed(
        name="rounding_tolerance_cents",
        label="Rounding tolerance",
        description="A line's shortfall or arithmetic difference at or under this "
        "is no finding",
        unit="cents",
        lowest=0,
        highest=100,
        first=0,
    ),
]
FIRST_PARAMETERS = {parameter.name: parameter.first for parameter in PARAMETERS}


def values_of(parameters: dict[str, Any]) -> list[ParameterValue]:
    """A version's parameters in the catalogue's order, each with its label."""
    return [
        ParameterValue(**allowed.labelled(), value=parameters[allowed.name])
        for allowed in PARAMETERS
    ]


def refuse_out_of_bounds(parameters: dict[str, Any]) -> None:
    """Raise a 422 for a set of parameters that doesn't keep to the catalogue:
    every parameter in it, each a whole number inside its bounds, and no other."""
    unknown = sorted(set(parameters) - {allowed.name for allowed in PARAMETERS})
    if unknown:
        raise HTTPException(422, f"There is no parameter {', '.join(unknown)}.")
    for allowed in PARAMETERS:
        if allowed.name not in parameters:
            raise HTTPException(422, f"{allowed.name} is missing.")
        value = parameters[allowed.name]
        whole = isinstance(value, int) and not isinstance(value, bool)
        if not whole or not allowed.lowest <= value <= allowed.highest:
            raise HTTPException(
                422,
                f"{allowed.name} must be a whole number of {allowed.unit} from "
                f"{allowed.lowest} to {allowed.highest}, not {value}.",
            )
