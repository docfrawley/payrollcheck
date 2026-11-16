"""Our CSV template for a certified payroll: one row per worker-week line, the
certification repeated on every row. Money is dollars and cents, hours are decimals
and dates are ISO. A No Work Week payroll is one row with the certification filled
in, the worker columns blank and no_work_week true. The generator writes every
payroll with it, and the app's intake reads them with it, refusing a file that
can't become a payroll. A payroll's JSON record is how the app keeps it."""

import csv
import io
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

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
# The columns that hold free text, which no rule reads as a value.
FREE_TEXT = (
    "contractor_name",
    "signed_by",
    "worker_name",
    "line_notes",
    "payroll_notes",
)
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


class Unreadable(ValueError):
    """A file that can't become a payroll, with the reason."""


# How a cell is read, and what it must be when it can't be.
Reads = tuple[Callable[[str], Any], str]
NUMBER: Reads = (Decimal, "a number")
WHOLE: Reads = (int, "a whole number")
DAY: Reads = (date.fromisoformat, "a date, YYYY-MM-DD")
YES_OR_NO: Reads = (lambda text: {TRUE: True, FALSE: False}[text], f"{TRUE} or {FALSE}")
AMOUNT: Reads = (cents, "dollars and cents")


def optional(reads: Reads) -> Reads:
    """A cell that may be blank, read as None."""
    parse, what = reads
    return (lambda text: parse(text) if text else None, what)


def parsed(row: dict[str, str], row_no: int, column: str, reads: Reads) -> Any:
    """A cell read, or refused naming its row and column. A number that isn't
    finite, such as NaN, is refused too."""
    parse, what = reads
    text = row[column]
    try:
        value = parse(text)
    except (ValueError, ArithmeticError, KeyError) as error:
        raise Unreadable(f'Row {row_no}, {column}: "{text}" isn\'t {what}') from error
    if isinstance(value, Decimal) and not value.is_finite():
        raise Unreadable(f'Row {row_no}, {column}: "{text}" isn\'t {what}')
    return value


def read_certification(row: dict[str, str], row_no: int) -> Certification:
    def read(column: str, reads: Reads) -> Any:
        return parsed(row, row_no, column, reads)

    return Certification(
        row["contractor_name"],
        row["fein"],
        row["registration_no"],
        row["project_id"],
        read("payroll_no", WHOLE),
        read("week_ending", DAY),
        read("wage_payment_date", DAY),
        row["signed_by"],
        read("signed_on", optional(DAY)),
        read("no_work_week", YES_OR_NO),
        row["payroll_notes"],
    )


def read_line(row: dict[str, str], row_no: int) -> Line:
    def read(column: str, reads: Reads) -> Any:
        return parsed(row, row_no, column, reads)

    return Line(
        row["worker_id"],
        row["worker_name"],
        row["classification"],
        read("apprentice_level", optional(WHOLE)),
        tuple(read(column, NUMBER) for column in DAILY_HOURS),
        read("total_hours", NUMBER),
        read("base_rate", AMOUNT),
        read("fringe_rate", AMOUNT),
        read("fringe_cash", AMOUNT),
        read("overtime_hours", NUMBER),
        read("gross", AMOUNT),
        read("deductions", AMOUNT),
        read("net", AMOUNT),
        row["line_notes"],
    )


def check_header(reader: csv.DictReader) -> None:
    header = list(reader.fieldnames or [])
    if not set(header) & set(COLUMNS):
        raise Unreadable(
            "The file has no header row: its first row must name the template's columns"
        )
    missing = [column for column in COLUMNS if column not in header]
    if missing:
        raise Unreadable(f"The file is missing columns: {', '.join(missing)}")


def read_upload(text: str) -> Payroll:
    """A payroll from the template's CSV, or Unreadable with the reason when the
    file can't become one. Anything else it says is read as it is, however wrong."""
    reader = csv.DictReader(io.StringIO(text))
    check_header(reader)
    rows = list(reader)
    if not rows:
        raise Unreadable("The file has no rows under its header")
    # The header is the spreadsheet's row 1, so the first payroll row is row 2.
    for row_no, row in enumerate(rows, start=2):
        if None in row.values():
            raise Unreadable(f"Row {row_no} has fewer cells than the header")
        if None in row:
            raise Unreadable(f"Row {row_no} has more cells than the header")
    differ = [
        c for c in (*CERTIFICATION, "payroll_notes") if len({r[c] for r in rows}) > 1
    ]
    if differ:
        raise Unreadable(
            f"The certification differs between rows in: {', '.join(differ)}"
        )
    certification = read_certification(rows[0], 2)
    if certification.no_work_week:
        return Payroll(certification, ())
    return Payroll(
        certification,
        tuple(read_line(row, n) for n, row in enumerate(rows, start=2)),
    )


def read_payroll(text: str) -> Payroll:
    """A payroll from the template's CSV, as the generator wrote it."""
    return read_upload(text)


def certification_record(found: Certification) -> dict[str, Any]:
    return {
        "contractor_name": found.contractor_name,
        "fein": found.fein,
        "registration_no": found.registration_no,
        "project_id": found.project_id,
        "payroll_no": found.payroll_no,
        "week_ending": found.week_ending.isoformat(),
        "wage_payment_date": found.wage_payment_date.isoformat(),
        "signed_by": found.signed_by,
        "signed_on": found.signed_on.isoformat() if found.signed_on else None,
        "no_work_week": found.no_work_week,
        "payroll_notes": found.payroll_notes,
    }


def line_record(line: Line) -> dict[str, Any]:
    return {
        "worker_id": line.worker_id,
        "worker_name": line.worker_name,
        "classification": line.classification,
        "apprentice_level": line.apprentice_level,
        "hours": [hours_text(h) for h in line.hours],
        "total_hours": hours_text(line.total_hours),
        "base_rate": line.base_rate,
        "fringe_rate": line.fringe_rate,
        "fringe_cash": line.fringe_cash,
        "overtime_hours": hours_text(line.overtime_hours),
        "gross": line.gross,
        "deductions": line.deductions,
        "net": line.net,
        "line_notes": line.line_notes,
    }


def payroll_record(payroll: Payroll) -> dict[str, Any]:
    """A payroll as the app keeps it, in JSON: money in cents, hours exact as
    strings, dates ISO."""
    return {
        "certification": certification_record(payroll.certification),
        "lines": [line_record(line) for line in payroll.lines],
    }
