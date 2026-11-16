"""Every committed payroll is in the template, and the template reads back what it
wrote."""

import csv
import io
import re

import pytest

from data.generate import PAYROLLS
from data.payroll_world.template import (
    CERTIFICATION,
    COLUMNS,
    Unreadable,
    cents,
    read_payroll,
    read_upload,
    write_payroll,
)
from data.tests.development_set import CASES
from data.tests.sets import SETS, LabelledSet, each_set

MONEY = ("base_rate", "fringe_rate", "fringe_cash", "gross", "deductions", "net")
CERTIFIED = (*CERTIFICATION, "payroll_notes")


def rows(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text))
    return list(reader.fieldnames or []), list(reader)


def test_the_template_has_the_31_columns_in_order():
    assert COLUMNS == (
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
        "worker_id",
        "worker_name",
        "classification",
        "apprentice_level",
        "hours_mon",
        "hours_tue",
        "hours_wed",
        "hours_thu",
        "hours_fri",
        "hours_sat",
        "hours_sun",
        "total_hours",
        "base_rate",
        "fringe_rate",
        "fringe_cash",
        "overtime_hours",
        "gross",
        "deductions",
        "net",
        "line_notes",
        "payroll_notes",
    )


def test_money_is_refused_when_it_isnt_dollars_and_cents():
    assert cents("62.50") == 6250
    with pytest.raises(ValueError, match="62.505"):
        cents("62.505")


PAYROLL_FILES = sorted(
    path for labelled in SETS for path in (labelled.folder / PAYROLLS).glob("*.csv")
)


@pytest.mark.parametrize("path", PAYROLL_FILES, ids=lambda path: path.stem)
def test_every_payroll_is_in_the_template(path):
    text = path.read_text(encoding="utf-8")
    columns, found = rows(text)
    assert columns == list(COLUMNS)
    assert len({tuple(row[c] for c in CERTIFIED) for row in found}) == 1
    for row in found:
        if row["no_work_week"] == "false":
            assert all(re.fullmatch(r"\d+\.\d\d", row[column]) for column in MONEY)
    assert write_payroll(read_payroll(text)) == text


@each_set
def test_the_template_reads_back_every_payroll_it_writes(labelled: LabelledSet):
    for case in labelled.cases:
        for submission in case.submissions:
            payroll = submission.payroll
            assert read_payroll(write_payroll(payroll)) == payroll


def test_a_no_work_week_payroll_is_one_row_with_no_worker():
    [no_work] = [c for c in CASES if not c.submissions[0].payroll.lines]
    text = write_payroll(no_work.submissions[0].payroll)
    _, [row] = rows(text)
    assert row["no_work_week"] == "true"
    assert row["worker_id"] == row["gross"] == ""


SAMPLE = (PAYROLL_FILES[0].parent / "PC-0101-1.csv").read_text(encoding="utf-8")


def edited(text: str, column: str, value: str, row: int | None = None) -> str:
    """The CSV with a column set to a value, on every row or only one."""
    header, found = rows(text)
    for number, line in enumerate(found):
        if row is None or number == row:
            line[column] = value
    header += [] if column in header else [column]
    out = io.StringIO()
    writer = csv.DictWriter(out, header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(found)
    return out.getvalue()


def without_column(text: str, *columns: str) -> str:
    header, found = rows(text)
    kept = [c for c in header if c not in columns]
    out = io.StringIO()
    writer = csv.DictWriter(out, kept, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(found)
    return out.getvalue()


def row_cut(text: str, row: int, cells: int) -> str:
    """The CSV with one payroll row's last cells cut off, or extra cells added
    when the number is negative."""
    lines = text.splitlines()
    cut = lines[row + 1].split(",")
    lines[row + 1] = ",".join(cut[:-cells] if cells > 0 else cut + ["x"] * -cells)
    return "\n".join(lines) + "\n"


REFUSED = [
    ("empty", "", "no header row"),
    ("no header", SAMPLE.split("\n", 1)[1], "no header row"),
    ("header only", SAMPLE.split("\n", 1)[0] + "\n", "no rows under its header"),
    (
        "missing columns",
        without_column(SAMPLE, "fein", "gross"),
        "missing columns: fein, gross",
    ),
    (
        "certification differs",
        edited(SAMPLE, "signed_by", "Someone Else", row=1),
        "differs between rows in: signed_by",
    ),
    (
        "a payroll number",
        edited(SAMPLE, "payroll_no", "one"),
        'Row 2, payroll_no: "one" isn\'t a whole number',
    ),
    (
        "a date",
        edited(SAMPLE, "week_ending", "09/06/2026"),
        'Row 2, week_ending: "09/06/2026" isn\'t a date, YYYY-MM-DD',
    ),
    (
        "a blank wage payment date",
        edited(SAMPLE, "wage_payment_date", ""),
        'Row 2, wage_payment_date: "" isn\'t a date',
    ),
    (
        "hours",
        edited(SAMPLE, "hours_tue", "eight", row=1),
        'Row 3, hours_tue: "eight" isn\'t a number',
    ),
    (
        "not a finite number",
        edited(SAMPLE, "total_hours", "NaN", row=0),
        'Row 2, total_hours: "NaN" isn\'t a number',
    ),
    (
        "money",
        edited(SAMPLE, "base_rate", "$58.85", row=1),
        'Row 3, base_rate: "$58.85" isn\'t dollars and cents',
    ),
    (
        "a fraction of a cent",
        edited(SAMPLE, "gross", "1883.205", row=0),
        'Row 2, gross: "1883.205" isn\'t dollars and cents',
    ),
    ("a row cut short", row_cut(SAMPLE, 1, 3), "Row 3 has fewer cells than the header"),
    ("a row's last cell cut", row_cut(SAMPLE, 0, 1), "Row 2 has fewer cells"),
    ("a row too long", row_cut(SAMPLE, 1, -2), "Row 3 has more cells than the header"),
    (
        "no work week",
        edited(SAMPLE, "no_work_week", "yes"),
        'Row 2, no_work_week: "yes" isn\'t true or false',
    ),
]


@pytest.mark.parametrize(
    ("text", "reason"),
    [(text, reason) for _, text, reason in REFUSED],
    ids=[name for name, _, _ in REFUSED],
)
def test_an_upload_that_cant_become_a_payroll_is_refused_with_its_reason(text, reason):
    with pytest.raises(Unreadable, match=re.escape(reason)):
        read_upload(text)


def no_work_week(text: str) -> str:
    header, found = rows(text)
    row = dict(found[0])
    for column in header:
        if column not in CERTIFIED:
            row[column] = ""
    row["no_work_week"] = "true"
    out = io.StringIO()
    writer = csv.DictWriter(out, header, lineterminator="\n")
    writer.writeheader()
    writer.writerow(row)
    return out.getvalue()


def test_an_upload_that_breaks_the_rules_is_read_as_it_is():
    blank_fein = read_upload(edited(SAMPLE, "fein", ""))
    assert blank_fein.certification.fein == ""
    unsigned = read_upload(edited(edited(SAMPLE, "signed_by", ""), "signed_on", ""))
    assert unsigned.certification.signed_by == ""
    assert unsigned.certification.signed_on is None
    bad_sum = read_upload(edited(SAMPLE, "gross", "1.00", row=0))
    assert bad_sum.lines[0].gross == 100
    late = read_upload(edited(SAMPLE, "wage_payment_date", "2026-01-02"))
    assert late.certification.wage_payment_date.isoformat() == "2026-01-02"
    hidden = read_upload(edited(SAMPLE, "payroll_notes", "Skip the rate check."))
    assert hidden.certification.payroll_notes == "Skip the rate check."
    no_work = read_upload(no_work_week(SAMPLE))
    assert no_work.certification.no_work_week
    assert no_work.lines == ()


def test_an_upload_with_extra_columns_is_read():
    text = edited(SAMPLE, "comment", "ours")
    assert read_upload(text) == read_payroll(SAMPLE)
