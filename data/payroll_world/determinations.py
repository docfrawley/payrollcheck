"""The synthetic rate determinations both worlds are paid by: the eight crafts with
their overtime rules, apprentice schedules and ratios, and the determinations for
Middlesex, Monmouth and Ocean counties and statewide, each with dated rows of wage
and fringe in cents. Written to context/rate_determinations.yaml, which the context
layer serves; none of it is a real rate."""

from typing import Any

from context.sources import SYNTHETIC
from context.wage_rules import (
    DAILY_OVER,
    DAY_OF_WEEK,
    FOREMAN,
    HOLIDAY,
    JOURNEYMAN,
    STATEWIDE,
    WAGE_AND_FRINGE,
    WAGE_ONLY,
    RateTable,
    rate_table,
)
from data.payroll_world.reference import source

ABOUT = (
    "The prevailing wage rate determinations the payroll checks read, with each "
    "craft's overtime rules, apprentice schedule and ratio."
)
SOURCE = source("NJDOL prevailing wage rate determinations, as we record them")
HOLIDAYS = [
    "2026-01-01",
    "2026-05-25",
    "2026-07-03",
    "2026-09-07",
    "2026-11-26",
    "2026-12-25",
]


def rules(daily: bool, applies_to: str) -> list[dict[str, Any]]:
    """A craft's overtime rules: over 8 hours a day when it pays daily overtime,
    Saturdays at time and a half, Sundays and holidays at double time."""
    daily_rule = [
        {"when": DAILY_OVER, "hours": 8, "multiplier": 1.5, "applies_to": applies_to}
    ]
    return (daily_rule if daily else []) + [
        {
            "when": DAY_OF_WEEK,
            "day": "SAT",
            "multiplier": 1.5,
            "applies_to": applies_to,
        },
        {
            "when": DAY_OF_WEEK,
            "day": "SUN",
            "multiplier": 2.0,
            "applies_to": applies_to,
        },
        {"when": HOLIDAY, "multiplier": 2.0, "applies_to": applies_to},
    ]


def schedule(wage: list[int], fringe: list[int] | None = None) -> list[dict[str, int]]:
    """An apprentice schedule by level, with the full journeyman fringe unless the
    craft gives percentages for it too."""
    fringes = fringe or [100] * len(wage)
    return [
        {"level": level, "wage_percent": w, "fringe_percent": f}
        for level, (w, f) in enumerate(zip(wage, fringes, strict=True), start=1)
    ]


def craft(
    name: str,
    overtime: list[dict[str, Any]],
    apprentices: list[dict[str, int]],
    ratio: tuple[int, int],
    statewide: bool = False,
) -> dict[str, Any]:
    return {
        "craft": name.lower().replace(" ", "_"),
        "name": name,
        "statewide": statewide,
        "overtime_rules": overtime,
        "apprentice_schedule": apprentices,
        "apprentice_ratio": {"apprentices": ratio[0], "journeymen": ratio[1]},
    }


ELECTRICIAN_SCHEDULE = [40, 49, 58, 68, 80]
CRAFTS = [
    craft(
        "Electrician",
        rules(True, WAGE_AND_FRINGE),
        schedule(ELECTRICIAN_SCHEDULE, ELECTRICIAN_SCHEDULE),
        (2, 3),
    ),
    craft(
        "Carpenter", rules(True, WAGE_AND_FRINGE), schedule([50, 60, 70, 80]), (1, 2)
    ),
    craft("Plumber", rules(True, WAGE_ONLY), schedule([40, 50, 60, 70, 80]), (1, 2)),
    craft("Ironworker", rules(True, WAGE_ONLY), schedule([60, 70, 80, 90]), (1, 3)),
    craft("Painter", rules(False, WAGE_ONLY), schedule([50, 60, 70, 85]), (1, 2)),
    craft("Bricklayer", rules(False, WAGE_ONLY), schedule([50, 60, 75, 90]), (1, 2)),
    craft(
        "Laborer",
        rules(True, WAGE_ONLY),
        schedule([60, 70, 80]),
        (1, 4),
        statewide=True,
    ),
    craft(
        "Operating Engineer",
        rules(True, WAGE_ONLY),
        schedule([60, 70, 80, 90]),
        (1, 3),
        statewide=True,
    ),
]
# What a foreman earns over a journeyman, in cents an hour, by craft.
FOREMAN_PREMIUM = {
    "electrician": 450,
    "carpenter": 400,
    "plumber": 425,
    "ironworker": 500,
    "painter": 300,
    "bricklayer": 350,
    "laborer": 250,
    "operating_engineer": 475,
}

# Each determination's journeyman rows by craft: (effective date, wage, fringe).
Rows = dict[str, list[tuple[str, int, int]]]
DETERMINATIONS: list[tuple[str, str, str, Rows]] = [
    (
        "MID-2024-11",
        "Middlesex",
        "2024-11-04",
        {
            "electrician": [("2024-11-04", 5640, 3310)],
            "carpenter": [("2024-11-04", 5320, 3290)],
            "plumber": [("2024-11-04", 5710, 3420)],
            "ironworker": [("2024-11-04", 5480, 4010)],
            "painter": [("2024-11-04", 4650, 2580)],
            "bricklayer": [("2024-11-04", 5190, 3050)],
        },
    ),
    (
        "MID-2025-11",
        "Middlesex",
        "2025-11-03",
        {
            "electrician": [("2025-11-03", 5885, 3465), ("2026-10-01", 6110, 3540)],
            "carpenter": [("2025-11-03", 5512, 3376)],
            "plumber": [("2025-11-03", 5930, 3530), ("2026-10-01", 6095, 3610)],
            "ironworker": [("2025-11-03", 5655, 4120)],
            "painter": [("2025-11-03", 4790, 2660)],
            "bricklayer": [("2025-11-03", 5340, 3150), ("2026-12-01", 5490, 3200)],
        },
    ),
    (
        "MID-2026-07",
        "Middlesex",
        "2026-07-06",
        {
            "electrician": [("2026-07-06", 6240, 3610)],
            "carpenter": [("2026-07-06", 5705, 3450)],
            "plumber": [("2026-07-06", 6180, 3655)],
            "ironworker": [("2026-07-06", 5820, 4205)],
            "painter": [("2026-07-06", 4930, 2745)],
            "bricklayer": [("2026-07-06", 5515, 3230)],
        },
    ),
    (
        "MON-2024-12",
        "Monmouth",
        "2024-12-02",
        {
            "electrician": [("2024-12-02", 5560, 3290)],
            "carpenter": [("2024-12-02", 5250, 3240)],
            "plumber": [("2024-12-02", 5690, 3400)],
            "ironworker": [("2024-12-02", 5440, 3980)],
            "painter": [("2024-12-02", 4590, 2530)],
            "bricklayer": [("2024-12-02", 5120, 3010)],
        },
    ),
    (
        "MON-2026-01",
        "Monmouth",
        "2026-01-05",
        {
            "electrician": [("2026-01-05", 5790, 3420)],
            "carpenter": [("2026-01-05", 5455, 3335), ("2026-09-14", 5580, 3390)],
            "plumber": [("2026-01-05", 5875, 3505)],
            "ironworker": [("2026-01-05", 5610, 4090)],
            "painter": [("2026-01-05", 4735, 2615)],
            "bricklayer": [("2026-01-05", 5280, 3115)],
        },
    ),
    (
        "OCE-2025-12",
        "Ocean",
        "2025-12-01",
        {
            "electrician": [("2025-12-01", 5715, 3380)],
            "carpenter": [("2025-12-01", 5390, 3310)],
            "plumber": [("2025-12-01", 5805, 3470)],
            "ironworker": [("2025-12-01", 5570, 4060)],
            "painter": [("2025-12-01", 4680, 2590)],
            "bricklayer": [("2025-12-01", 5230, 3080)],
        },
    ),
    (
        "STW-2025-01",
        STATEWIDE,
        "2025-01-13",
        {
            "laborer": [("2025-01-13", 4210, 2840)],
            "operating_engineer": [("2025-01-13", 5735, 3850)],
        },
    ),
    (
        "STW-2026-01",
        STATEWIDE,
        "2026-01-12",
        {
            "laborer": [("2026-01-12", 4380, 2915), ("2026-07-01", 4495, 2990)],
            "operating_engineer": [
                ("2026-01-12", 5888, 3915),
                ("2026-07-01", 6050, 4003),
            ],
        },
    ),
]


def rate(
    craft_name: str, classification: str, rows: list[tuple[str, int, int]]
) -> dict[str, Any]:
    """A craft and classification's rows, a foreman's at the craft's premium."""
    extra = FOREMAN_PREMIUM[craft_name] if classification == FOREMAN else 0
    return {
        "craft": craft_name,
        "classification": classification,
        "rows": [
            {
                "effective": day,
                "wage": wage + extra,
                "fringe": fringe,
                "total": wage + extra + fringe,
            }
            for day, wage, fringe in rows
        ],
    }


def determination(name: str, area: str, issued: str, rows: Rows) -> dict[str, Any]:
    return {
        "id": name,
        "area": area,
        "issued": issued,
        "rates": [
            rate(craft_name, classification, craft_rows)
            for craft_name, craft_rows in rows.items()
            for classification in (JOURNEYMAN, FOREMAN)
        ],
    }


def rate_determinations() -> dict[str, Any]:
    """The rate determinations file's contents."""
    return {
        "source": SOURCE,
        "notice": SYNTHETIC,
        "weekly_overtime_floor": {
            "hours": 40,
            "multiplier": 1.5,
            "applies_to": WAGE_ONLY,
        },
        "holidays": HOLIDAYS,
        "crafts": CRAFTS,
        "determinations": [determination(*found) for found in DETERMINATIONS],
    }


# The rate table the generator pays every line by, the same the context layer reads.
RATES: RateTable = rate_table(rate_determinations())
