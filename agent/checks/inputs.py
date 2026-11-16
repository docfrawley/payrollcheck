"""Everything the check tools read, as plain data: the latest submission's
certification and lines, each line's requirements as its craft and as the worker's
established one, each apprentice's level on each work date, last week's
classifications, the subcontractor's record and engagement window, the
registration on each work date, and the filing rules."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from context.wage_rules import RateTable


@dataclass(frozen=True)
class Certification:
    contractor_name: str
    fein: str
    registration_no: str
    project_id: str
    payroll_no: int
    week_ending: date
    wage_payment_date: date
    signed_by: str
    signed_on: date | None
    no_work_week: bool
    payroll_notes: str


@dataclass(frozen=True)
class Line:
    """One worker's week as the payroll states it, money in cents."""

    worker_id: str
    worker_name: str
    classification: str
    hours: tuple[Decimal, ...]
    total_hours: Decimal
    base_rate: int
    fringe_rate: int
    fringe_cash: int
    overtime_hours: Decimal
    gross: int
    line_notes: str

    @property
    def fringe_paid(self) -> int:
        """Fringe paid to plans and in cash, which both count toward the fringe."""
        return self.fringe_rate + self.fringe_cash


@dataclass(frozen=True)
class DayRate:
    """What a day's work requires, apprentice percentages applied, and the
    determination row it came from."""

    determination_id: str
    effective: date
    wage: int
    fringe: int

    @property
    def total(self) -> int:
        return self.wage + self.fringe


@dataclass(frozen=True)
class Requirement:
    """What a line's work days require paid as one craft and classification, with
    the craft's rules for splitting its hours."""

    craft: str
    classification: str
    name: str
    rates: dict[date, DayRate]
    table: RateTable

    def citation(self) -> str:
        """The determination and the rows the work days' rates come from."""
        rows: dict[str, list[str]] = {}
        for _, rate in sorted(self.rates.items()):
            dated = rows.setdefault(rate.determination_id, [])
            if rate.effective.isoformat() not in dated:
                dated.append(rate.effective.isoformat())
        return "; ".join(
            f"Rate determination {found}, {self.text()}, "
            f"{'rows' if len(days) > 1 else 'row'} effective {' and '.join(days)}"
            for found, days in rows.items()
        )

    def text(self) -> str:
        return f"{self.name} {self.classification.title()}"


@dataclass(frozen=True)
class LineInputs:
    """A line with what its work requires: as it's classified (none for a
    classification the rate determinations don't have) and as the worker's
    established craft (none for a worker the app doesn't know), the apprentice's
    level on each work date, and last week's classification."""

    line_no: int
    line: Line
    days: tuple[tuple[date, Decimal], ...]
    claimed: Requirement | None
    established: Requirement | None
    levels: dict[date, int | None]
    last_week: str | None

    @property
    def worked(self) -> list[date]:
        return [day for day, hours in self.days if hours]

    @property
    def misclassified(self) -> bool:
        """Paid as another craft than the worker's established one, which pays
        less on a work day."""
        claimed, established = self.claimed, self.established
        return (
            claimed is not None
            and established is not None
            and claimed.craft != established.craft
            and any(
                claimed.rates[day].total < established.rates[day].total
                for day in self.worked
            )
        )

    @property
    def unregistered(self) -> bool:
        """Paid as an apprentice on a work day they weren't a registered one."""
        return any(level is None for level in self.levels.values())


@dataclass(frozen=True)
class Registration:
    """The subcontractor's registration on a work date, with the record it rests
    on."""

    active: bool
    citation: str


@dataclass(frozen=True)
class FilingRule:
    name: str
    cites: str

    def citation(self) -> str:
        return f"Filing rules, {self.name}: {self.cites}"


@dataclass(frozen=True)
class CheckInputs:
    case_id: str
    project_id: str
    week_ending: date
    received_on: date
    certification: Certification
    lines: tuple[LineInputs, ...]
    legal_name: str
    fein: str
    registration_no: str
    first_week_ending: date
    registration: dict[date, Registration]
    due_days: int
    filing_rules: dict[str, FilingRule]


def week_days(week_ending: date) -> list[date]:
    """Monday to Sunday, ending on the week ending."""
    return [week_ending - timedelta(days=6 - day) for day in range(7)]
