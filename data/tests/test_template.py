"""Every committed payroll is in the template, and the template reads back what it
wrote."""

import csv
import io
import re

import pytest

from data.payroll_world.template import (
    CERTIFICATION,
    COLUMNS,
    cents,
    read_payroll,
    write_payroll,
)
from data.tests.development_set import CASES, PAYROLL_FILES

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


def test_the_template_reads_back_every_payroll_it_writes():
    for case in CASES:
        for submission in case.submissions:
            payroll = submission.payroll
            assert read_payroll(write_payroll(payroll)) == payroll


def test_a_no_work_week_payroll_is_one_row_with_no_worker():
    [no_work] = [c for c in CASES if not c.submissions[0].payroll.lines]
    text = write_payroll(no_work.submissions[0].payroll)
    _, [row] = rows(text)
    assert row["no_work_week"] == "true"
    assert row["worker_id"] == row["gross"] == ""
