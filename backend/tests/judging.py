"""The judge's answers in the tests, in place of OpenRouter's Decisions endpoint."""

from typing import Any

JUDGE_URL = "https://judge.test"
POINTS = (
    "covers_every_exception",
    "amounts_match",
    "plain_language",
    "no_legal_interpretation",
)


def answer(
    covers: float = 0.9,
    amounts: float = 0.8,
    plain: float = 0.7,
    no_legal: float = 1.0,
    cost: float = 0.00002,
) -> dict[str, Any]:
    """An answer as Jev gives it, a score of 0.85 by default."""
    chances = dict(zip(POINTS, (covers, amounts, plain, no_legal), strict=True))
    return {
        "model": "typesafe/jev-1.13",
        "answers": {
            point: {"type": "noul", "noul": chance} for point, chance in chances.items()
        },
        "usage": {"input_tokens": 400, "output_tokens": 4, "cost": cost},
    }
