"""Every clean line is paid as its own hours and rates say."""

from decimal import Decimal

from context import wage_rules
from data.tests.development_set import CASES, SEEDED

LABELS = SEEDED.labels


def test_every_clean_line_adds_up_and_is_paid_as_its_own_hours_and_rates_say():
    arithmetic = {
        (label.case_id, label.worker_id)
        for label in LABELS
        if "arithmetic" in label.rule
    }
    for case in CASES:
        for submission in case.submissions:
            for line in submission.payroll.lines:
                if (
                    case.case_id,
                    line.worker_id,
                ) in arithmetic and submission.number == 1:
                    continue
                assert sum(line.hours, Decimal(0)) == line.total_hours
                assert line.gross == wage_rules.gross(
                    line.base_rate, line.total_hours, line.overtime_hours
                )
                assert line.net == line.gross - line.deductions
