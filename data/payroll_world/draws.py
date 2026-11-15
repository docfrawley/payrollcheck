"""The generator's random draws: each from a source of its own, seeded by the
world's seed and what it's for, so a draw never depends on the order things are
drawn in and the same seed always draws the same."""

import random


def draw(seed: int, *key: object) -> random.Random:
    key_text = ":".join(str(part) for part in (seed, *key))
    return random.Random(key_text)  # noqa: S311 - synthetic data, drawn from a fixed seed


def digits(source: random.Random, count: int) -> str:
    return "".join(str(source.randrange(10)) for _ in range(count))
