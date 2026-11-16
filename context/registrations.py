"""What a registration says on a date, for a contractor's public works
registration and an apprentice's: whether a contractor's was active, and the
period that says so, and an apprentice's level. The context layer answers with
these, and the generator pays and labels by them."""

from datetime import date

Period = tuple[date, date]


def period_on(periods: list[Period], day: date) -> Period | None:
    """The period a contractor's registration was in on a date, or else the latest
    that began before it, or none before its first."""
    begun = [period for period in periods if period[0] <= day]
    return max(begun, default=None)


def active_on(periods: list[Period], day: date) -> bool:
    period = period_on(periods, day)
    return period is not None and day <= period[1]


def level_on(levels: list[tuple[int, date]], day: date) -> int | None:
    """An apprentice's level on a date: the latest reached by then, or none before
    they were registered."""
    reached = [(start, level) for level, start in levels if start <= day]
    return max(reached)[1] if reached else None
