"""The one rate logic: which rate determination and row apply to a day's work, how
a week's hours split into straight time and premium time, an apprentice's rate, and
what a payroll line is short. Pure functions on plain data, with the standard
library alone, so the context layer, the generator and the check tools compute
every rate and shortfall the same way. Money is in integer cents; hours and
multipliers are Decimals."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

STATEWIDE = "STATEWIDE"
DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
JOURNEYMAN = "journeyman"
FOREMAN = "foreman"
APPRENTICE = "apprentice"
WAGE_ONLY = "wage"
DAILY_OVER = "daily_over"
DAY_OF_WEEK = "day_of_week"
HOLIDAY = "holiday"
WAGE_AND_FRINGE = "wage_and_fringe"
STRAIGHT = Decimal(1)
# A payroll pays its overtime hours at time and a half.
PAID_OVERTIME = Decimal("1.5")


def to_cents(amount: Decimal) -> int:
    """An amount in cents rounded to a whole cent, half up: the one rounding rule."""
    return int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Row:
    """One dated row of a rate: the wage and fringe per hour from its date."""

    effective: date
    wage: int
    fringe: int

    @property
    def total(self) -> int:
        return self.wage + self.fringe


@dataclass(frozen=True)
class Determination:
    """A rate determination for a county or statewide, with its rows by craft and
    classification, oldest first."""

    id: str
    area: str
    issued: date
    rows: dict[tuple[str, str], tuple[Row, ...]]


@dataclass(frozen=True, order=True)
class Premium:
    """A rate of pay for an hour: its wage multiplier and its fringe multiplier,
    ordered so the higher premium is the greater."""

    wage: Decimal
    fringe: Decimal


@dataclass(frozen=True)
class OvertimeRule:
    """One overtime rule of a craft: when it applies and the premium it pays. A
    daily rule (`daily_over`) applies to the hours over its threshold in a day, and
    a day rule (`day_of_week` or `holiday`) to all the day's hours."""

    when: str
    premium: Premium
    hours: Decimal | None = None
    day: str | None = None


@dataclass(frozen=True)
class WeeklyFloor:
    """The state's overtime floor: straight hours over its threshold in a week."""

    hours: Decimal
    premium: Premium


@dataclass(frozen=True)
class Level:
    """A level of a craft's apprentice schedule, as percentages of the journeyman
    wage and fringe."""

    level: int
    wage_percent: int
    fringe_percent: int


@dataclass(frozen=True)
class Craft:
    """A craft's rules: whether its rates are statewide, its overtime rules, its
    apprentice schedule and how many apprentices it allows for its journeymen."""

    craft: str
    name: str
    statewide: bool
    overtime_rules: tuple[OvertimeRule, ...]
    apprentice_schedule: dict[int, Level]
    ratio_apprentices: int
    ratio_journeymen: int


@dataclass(frozen=True)
class RateTable:
    """Every determination with the crafts' rules, the holidays and the state's
    weekly overtime floor."""

    crafts: dict[str, Craft]
    determinations: tuple[Determination, ...]
    holidays: frozenset[date]
    weekly_floor: WeeklyFloor


@dataclass(frozen=True)
class Work:
    """What a line's rate depends on, beside the day: the craft and classification
    it is paid as, the project's county and award date, and an apprentice's level,
    which only an apprentice has."""

    craft: str
    classification: str
    county: str
    award_date: date
    apprentice_level: int | None = None


@dataclass(frozen=True)
class Rate:
    """The rate a day's work requires, apprentice percentages applied, and the
    determination and row it came from."""

    determination: Determination
    row: Row
    wage: int
    fringe: int


@dataclass(frozen=True)
class Hours:
    """Some hours of one day at one premium."""

    day: date
    hours: Decimal
    premium: Premium


def premium(rule: dict[str, Any]) -> Premium:
    multiplier = Decimal(str(rule["multiplier"]))
    fringe = multiplier if rule["applies_to"] == WAGE_AND_FRINGE else STRAIGHT
    return Premium(multiplier, fringe)


def overtime_rule(rule: dict[str, Any]) -> OvertimeRule:
    hours = rule.get("hours")
    return OvertimeRule(
        rule["when"],
        premium(rule),
        None if hours is None else Decimal(str(hours)),
        rule.get("day"),
    )


def craft_rules(craft: dict[str, Any]) -> Craft:
    return Craft(
        craft["craft"],
        craft["name"],
        craft["statewide"],
        tuple(overtime_rule(rule) for rule in craft["overtime_rules"]),
        {
            level["level"]: Level(
                level["level"], level["wage_percent"], level["fringe_percent"]
            )
            for level in craft["apprentice_schedule"]
        },
        craft["apprentice_ratio"]["apprentices"],
        craft["apprentice_ratio"]["journeymen"],
    )


def determination(found: dict[str, Any]) -> Determination:
    return Determination(
        found["id"],
        found["area"],
        date.fromisoformat(found["issued"]),
        {
            (rate["craft"], rate["classification"]): tuple(
                Row(date.fromisoformat(row["effective"]), row["wage"], row["fringe"])
                for row in rate["rows"]
            )
            for rate in found["rates"]
        },
    )


def rate_table(data: dict[str, Any]) -> RateTable:
    """The rate table from the rate determinations file's contents."""
    return RateTable(
        {craft["craft"]: craft_rules(craft) for craft in data["crafts"]},
        tuple(determination(found) for found in data["determinations"]),
        frozenset(date.fromisoformat(day) for day in data["holidays"]),
        WeeklyFloor(
            Decimal(str(data["weekly_overtime_floor"]["hours"])),
            premium(data["weekly_overtime_floor"]),
        ),
    )


def area_of(table: RateTable, craft: str, county: str) -> str:
    """Where a craft's rates come from: the county, or statewide."""
    return STATEWIDE if table.crafts[craft].statewide else county


def determination_in_force(
    table: RateTable, area: str, award_date: date
) -> Determination | None:
    """The area's determination in force on the award date: the latest issued on or
    before it. One issued later never applies."""
    issued = [
        found
        for found in table.determinations
        if found.area == area and found.issued <= award_date
    ]
    return max(issued, key=lambda found: found.issued, default=None)


def row_on(rows: tuple[Row, ...], work_date: date) -> Row | None:
    """The latest row dated on or before the work date."""
    dated = [row for row in rows if row.effective <= work_date]
    return max(dated, key=lambda row: row.effective, default=None)


def apprentice_rate(craft: Craft, row: Row, level: int) -> tuple[int, int]:
    """An apprentice's wage and fringe at their level, as percentages of the
    journeyman row, each rounded to the cent."""
    schedule = craft.apprentice_schedule[level]
    return (
        to_cents(Decimal(row.wage * schedule.wage_percent) / 100),
        to_cents(Decimal(row.fringe * schedule.fringe_percent) / 100),
    )


def required_rate(table: RateTable, work: Work, work_date: date) -> Rate:
    """The rate a day's work requires: the award-date determination's latest row
    dated on or before the work date. An apprentice's is a percentage of the
    journeyman row, by their level."""
    area = area_of(table, work.craft, work.county)
    found = determination_in_force(table, area, work.award_date)
    if found is None:
        raise LookupError(f"No {area} determination was in force on {work.award_date}")
    apprentice = work.classification == APPRENTICE
    classification = JOURNEYMAN if apprentice else work.classification
    row = row_on(found.rows[work.craft, classification], work_date)
    if row is None:
        raise LookupError(
            f"{found.id} has no {work.craft} rate on or before {work_date}"
        )
    if apprentice:
        if work.apprentice_level is None:
            raise LookupError(f"An {work.craft} apprentice needs a level")
        wage, fringe = apprentice_rate(
            table.crafts[work.craft], row, work.apprentice_level
        )
        return Rate(found, row, wage, fringe)
    return Rate(found, row, row.wage, row.fringe)


def day_premium(table: RateTable, craft: Craft, day: date) -> Premium:
    """The premium for all of a day's hours: the highest of the craft's rules for
    the day of the week and holidays, or straight time."""
    premiums = [Premium(STRAIGHT, STRAIGHT)]
    for rule in craft.overtime_rules:
        if (rule.when == DAY_OF_WEEK and rule.day == DAYS[day.weekday()]) or (
            rule.when == HOLIDAY and day in table.holidays
        ):
            premiums.append(rule.premium)
    return max(premiums)


def daily_split(
    table: RateTable, craft: Craft, day: date, hours: Decimal
) -> list[Hours]:
    """A day's hours at the day's premium, each band over one of the craft's daily
    thresholds at the highest of that and the daily rules it is over."""
    premium_now = day_premium(table, craft, day)
    thresholds = sorted(
        (rule.hours, rule.premium)
        for rule in craft.overtime_rules
        if rule.when == DAILY_OVER and rule.hours is not None
    )
    split, start = [], Decimal(0)
    for threshold, rule_premium in thresholds:
        if hours <= threshold:
            break
        split.append(Hours(day, threshold - start, premium_now))
        start, premium_now = threshold, max(premium_now, rule_premium)
    return [*split, Hours(day, hours - start, premium_now)]


def weekly_floor(table: RateTable, split: list[Hours]) -> list[Hours]:
    """The state's floor: straight hours over its weekly threshold, counted day by
    day, are paid at its premium."""
    floor = table.weekly_floor
    straight_so_far = Decimal(0)
    floored = []
    for part in split:
        if part.premium.wage > STRAIGHT:
            floored.append(part)
            continue
        under = max(Decimal(0), min(part.hours, floor.hours - straight_so_far))
        straight_so_far += part.hours
        if under:
            floored.append(Hours(part.day, under, part.premium))
        if part.hours > under:
            floored.append(Hours(part.day, part.hours - under, floor.premium))
    return floored


def premium_split(
    table: RateTable, craft: str, days: list[tuple[date, Decimal]]
) -> list[Hours]:
    """A week's hours, day by day, split into straight time and premium time by the
    craft's overtime rules, with the weekly floor as a fallback. Each hour takes the
    highest premium any rule gives it."""
    rules = table.crafts[craft]
    split = [
        part
        for day, hours in days
        if hours
        for part in daily_split(table, rules, day, hours)
    ]
    return weekly_floor(table, split)


def premium_hours(split: list[Hours]) -> Decimal:
    """The hours owed a premium: what a payroll's overtime hours should be."""
    return sum(
        (part.hours for part in split if part.premium.wage > STRAIGHT), Decimal(0)
    )


def gross(base: int, total_hours: Decimal, overtime_hours: Decimal) -> int:
    """A line's gross wages: every hour at the base rate, plus the premium on its
    overtime hours."""
    return to_cents(base * total_hours + base * (PAID_OVERTIME - 1) * overtime_hours)


def base_shortfall(split: list[Hours], required: dict[date, int], base: int) -> int:
    """What a base rate under the required wage leaves unpaid, at each hour's
    premium."""
    return to_cents(
        sum(
            (
                part.hours * part.premium.wage * max(0, required[part.day] - base)
                for part in split
            ),
            Decimal(0),
        )
    )


def fringe_shortfall(split: list[Hours], required: dict[date, int], paid: int) -> int:
    """What fringe paid under the required fringe leaves unpaid, plan and cash
    together, multiplied for premium hours where the craft's overtime applies to
    fringe."""
    return to_cents(
        sum(
            (
                part.hours * part.premium.fringe * max(0, required[part.day] - paid)
                for part in split
            ),
            Decimal(0),
        )
    )


def overtime_shortfall(
    split: list[Hours], overtime_hours: Decimal, base: int, fringe: int
) -> int:
    """The premium owed on hours the payroll didn't pay as overtime, at the line's
    own rates. Its overtime hours are credited to the premium hours in order, each at
    time and a half, on the fringe too where the craft's overtime applies to it."""
    unpaid = overtime_hours
    short = Decimal(0)
    for part in split:
        if part.premium.wage == STRAIGHT:
            continue
        credited = min(part.hours, unpaid)
        unpaid -= credited
        paid = Premium(
            min(part.premium.wage, PAID_OVERTIME),
            min(part.premium.fringe, PAID_OVERTIME),
        )
        short += credited * (
            owed_premium(part.premium, base, fringe) - owed_premium(paid, base, fringe)
        )
        short += (part.hours - credited) * owed_premium(part.premium, base, fringe)
    return to_cents(short)


def owed_premium(paid: Premium, base: int, fringe: int) -> Decimal:
    """The premium over straight time for an hour, on the wage and the fringe."""
    return (paid.wage - 1) * base + (paid.fringe - 1) * fringe


def ratio_allows(
    table: RateTable, craft: str, apprentices: int, journeymen: int
) -> bool:
    """Whether a craft's ratio allows this many apprentices for its journeymen, who
    include its foremen."""
    rules = table.crafts[craft]
    return apprentices * rules.ratio_journeymen <= journeymen * rules.ratio_apprentices
