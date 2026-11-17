"""The business's rule that keeps or rolls back a new version of the payroll agent, as
the lab's compare and keep_or_roll_back: from the new version's held-out scores, the
current version's and the round's settings."""

from typing import Literal, NamedTuple

from backend.models import Measures, Settings, Verdict


class Measure(NamedTuple):
    """A measure the rule weighs: its name in the settings, where it is in the
    scores, whether higher is better, whether it's compared as a fraction of the
    old value rather than a difference, and its objective, if it has one."""

    name: str
    score: str
    higher_is_better: bool
    as_fraction: bool
    objective: Literal["floor", "ceiling"] | None


MEASURES = [
    Measure("catch_rate", "catch_rate", True, False, "floor"),
    Measure("false_per_100", "false_per_100", False, False, "ceiling"),
    Measure("shortfall_accuracy", "shortfall_accuracy", True, False, "floor"),
    Measure("notice_score", "notice_score", True, False, "floor"),
    Measure("cost_per_case", "model_cost_per_case", False, True, None),
    Measure("seconds_per_case", "seconds_per_case", False, True, None),
]
RULE = (
    "A new version is kept when it meets the objectives on the held-out set, at "
    "least one measure improves by more than its noise and none gets worse by more "
    "than its tolerance. The catch rate, shortfall accuracy and notice score are "
    "better higher, and must be at least their objectives; false exceptions per "
    "100 payrolls are better lower, and must be at most theirs. These four are "
    "compared as differences in their own units, and cost and time per case, "
    "better lower, as fractions of the old value. A version with no value for a "
    "measure the current version has, such as no notice score, is rolled back; a "
    "measure only the new version has must meet its objective but isn't compared; "
    "a measure neither has is left out."
)


# The places the rule compares to, so a score that ties with a noise, a tolerance
# or an objective, such as an average of two runs, ties rather than missing by a
# rounding error.
PRECISION = 9

# Why a version was rolled back without the rule being applied to its scores.
EVALUATIONS_STOPPED = "its evaluations were stopped"
CANT_AFFORD = "the round couldn't afford to evaluate it"
NOT_EVALUATED = "the improver didn't evaluate it"
STOPPED_BEFORE_VERDICT = "the round was stopped before its verdict"


class Decided(NamedTuple):
    """Whether to keep a version, and why, in the lab's words."""

    verdict: Verdict
    reason: str


def value(scores: Measures | None, measure: Measure) -> float | None:
    """One measure of a version's scores, or nothing without scores."""
    return getattr(scores, measure.score) if scores else None


def misses_objective(after: float, measure: Measure, settings: Settings) -> bool:
    """Say whether a value falls short of the measure's objective, if it has one."""
    if measure.objective is None:
        return False
    objective = getattr(settings.objectives, measure.name)
    after = round(after, PRECISION)
    return after < objective if measure.objective == "floor" else after > objective


def changed(
    after: float, before: float, measure: Measure, settings: Settings
) -> tuple[bool, bool]:
    """Say whether a measure got better by more than its noise, and whether it got
    worse by more than its tolerance."""
    noise = getattr(settings.noise, measure.name)
    tolerance = getattr(settings.tolerance, measure.name)
    if measure.as_fraction:
        noise, tolerance = before * noise, before * tolerance
    gain = after - before if measure.higher_is_better else before - after
    gain, noise, tolerance = (round(x, PRECISION) for x in (gain, noise, tolerance))
    return gain > noise, gain < -tolerance


def compare(
    new: Measures, old: Measures | None, settings: Settings
) -> tuple[list[str], list[str]]:
    """Return the measures that got better by more than the noise, and those that
    got worse by more than the tolerance, of those both versions have."""
    better, worse = [], []
    for measure in MEASURES:
        after, before = value(new, measure), value(old, measure)
        if after is None or before is None:
            continue
        improved, worsened = changed(after, before, measure, settings)
        if improved:
            better.append(measure.name)
        if worsened:
            worse.append(measure.name)
    return better, worse


def keep_or_roll_back(
    new: Measures | None, old: Measures | None, settings: Settings
) -> Decided:
    """Keep a version that has every measure the current version has, meets the
    objectives, improves at least one measure by more than its noise and worsens
    none by more than its tolerance."""
    if new is None:
        return Decided(Verdict.ROLLED_BACK, "it has no scores")
    lacking = [
        m.name for m in MEASURES if value(new, m) is None and value(old, m) is not None
    ]
    if lacking:
        return Decided(Verdict.ROLLED_BACK, f"it has no {', '.join(lacking)}")
    missed = [
        m.name
        for m in MEASURES
        if (after := value(new, m)) is not None and misses_objective(after, m, settings)
    ]
    if missed:
        return Decided(
            Verdict.ROLLED_BACK, f"it missed the objectives on {', '.join(missed)}"
        )
    better, worse = compare(new, old, settings)
    if worse:
        return Decided(Verdict.ROLLED_BACK, f"{', '.join(worse)} got worse")
    if not better:
        return Decided(Verdict.ROLLED_BACK, "no score improved by more than the noise")
    return Decided(Verdict.KEPT, f"{', '.join(better)} improved")
