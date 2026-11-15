"""Our CSV template for a certified payroll: one row per worker-week line, the
certification repeated on every row. Money is dollars and cents, hours are decimals
and dates are ISO. A No Work Week payroll is one row with the certification filled
in, the worker columns blank and no_work_week true. The generator writes every
payroll with it, and the app's intake reads them with it."""

import csv
import io
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

CERTIFICATION = (
    "contractor_name",
    "fein",
    "registration_no",
    "project_id",
    "payroll_no",
    "week_ending",
    "wage_payment_date",
    "signed_by",
    "signed_on",
    "no_work_week",
)
DAILY_HOURS = (
    "hours_mon",
    "hours_tue",
    "hours_wed",
    "hours_thu",
    "hours_fri",
    "hours_sat",
    "hours_sun",
)
LINE = (
    "worker_id",
    "worker_name",
    "classification",
    "apprentice_level",
    *DAILY_HOURS,
    "total_hours",
    "base_rate",
    "fringe_rate",
    "fringe_cash",
    "overtime_hours",
    "gross",
    "deductions",
    "net",
    "line_notes",
)
COLUMNS: tuple[str, ...] = (*CERTIFICATION, *LINE, "payroll_notes")
TRUE = "true"
FALSE = "false"


@dataclass(frozen=True)
class Certification:
    """The MW-562's certification: who files, for which project and week, and who
    signed it. A blank value is an empty string, or None for a date."""

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
    """One worker's week on the payroll, with the hours of each day from Monday,
    money in cents."""

    worker_id: str
    worker_name: str
    classification: str
    apprentice_level: int | None
    hours: tuple[Decimal, ...]
    total_hours: Decimal
    base_rate: int
    fringe_rate: int
    fringe_cash: int
    overtime_hours: Decimal
    gross: int
    deductions: int
    net: int
    line_notes: str


@dataclass(frozen=True)
class Payroll:
    certification: Certification
    lines: tuple[Line, ...]

    def line_of(self, worker_id: str) -> Line:
        [found] = [line for line in self.lines if line.worker_id == worker_id]
        return found

    def with_line(self, changed: Line) -> "Payroll":
        """The payroll with a worker's line changed."""
        lines = tuple(
            changed if ln.worker_id == changed.worker_id else ln for ln in self.lines
        )
        return replace(self, lines=lines)

    def without(self, worker_id: str) -> "Payroll":
        return replace(
            self, lines=tuple(ln for ln in self.lines if ln.worker_id != worker_id)
        )


def dollars(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


def cents(text: str) -> int:
    """Dollars and cents as cents, refusing a fraction of a cent."""
    amount = Decimal(text) * 100
    if amount != amount.to_integral_value():
        raise ValueError(f"{text} isn't dollars and cents")
    return int(amount)


def hours_text(hours: Decimal) -> str:
    return f"{hours:.2f}"


def date_text(day: date | None) -> str:
    return day.isoformat() if day else ""


def certification_row(found: Certification) -> dict[str, str]:
    return {
        "contractor_name": found.contractor_name,
        "fein": found.fein,
        "registration_no": found.registration_no,
        "project_id": found.project_id,
        "payroll_no": str(found.payroll_no),
        "week_ending": date_text(found.week_ending),
        "wage_payment_date": date_text(found.wage_payment_date),
        "signed_by": found.signed_by,
        "signed_on": date_text(found.signed_on),
        "no_work_week": TRUE if found.no_work_week else FALSE,
        "payroll_notes": found.payroll_notes,
    }


def line_row(line: Line) -> dict[str, str]:
    level = line.apprentice_level
    return {
        "worker_id": line.worker_id,
        "worker_name": line.worker_name,
        "classification": line.classification,
        "apprentice_level": "" if level is None else str(level),
        **{
            column: hours_text(h)
            for column, h in zip(DAILY_HOURS, line.hours, strict=True)
        },
        "total_hours": hours_text(line.total_hours),
        "base_rate": dollars(line.base_rate),
        "fringe_rate": dollars(line.fringe_rate),
        "fringe_cash": dollars(line.fringe_cash),
        "overtime_hours": hours_text(line.overtime_hours),
        "gross": dollars(line.gross),
        "deductions": dollars(line.deductions),
        "net": dollars(line.net),
        "line_notes": line.line_notes,
    }


def write_payroll(payroll: Payroll) -> str:
    """A payroll as the template's CSV."""
    certification = certification_row(payroll.certification)
    blank = dict.fromkeys(LINE, "")
    rows = [certification | line_row(line) for line in payroll.lines] or [
        certification | blank
    ]
    text = io.StringIO()
    writer = csv.DictWriter(text, COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return text.getvalue()


def read_certification(row: dict[str, str]) -> Certification:
    return Certification(
        row["contractor_name"],
        row["fein"],
        row["registration_no"],
        row["project_id"],
        int(row["payroll_no"]),
        date.fromisoformat(row["week_ending"]),
        date.fromisoformat(row["wage_payment_date"]),
        row["signed_by"],
        date.fromisoformat(row["signed_on"]) if row["signed_on"] else None,
        row["no_work_week"] == TRUE,
        row["payroll_notes"],
    )


def read_line(row: dict[str, str]) -> Line:
    level = row["apprentice_level"]
    return Line(
        row["worker_id"],
        row["worker_name"],
        row["classification"],
        int(level) if level else None,
        tuple(Decimal(row[column]) for column in DAILY_HOURS),
        Decimal(row["total_hours"]),
        cents(row["base_rate"]),
        cents(row["fringe_rate"]),
        cents(row["fringe_cash"]),
        Decimal(row["overtime_hours"]),
        cents(row["gross"]),
        cents(row["deductions"]),
        cents(row["net"]),
        row["line_notes"],
    )


def read_payroll(text: str) -> Payroll:
    """A payroll from the template's CSV, as the generator wrote it."""
    rows = list(csv.DictReader(io.StringIO(text)))
    certification = read_certification(rows[0])
    if certification.no_work_week:
        return Payroll(certification, ())
    return Payroll(certification, tuple(read_line(row) for row in rows))
