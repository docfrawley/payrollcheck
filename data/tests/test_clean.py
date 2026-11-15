"""Every clean line is paid as its own hours and rates say."""

from decimal import Decimal

from context import wage_rules
from data.tests.sets import LabelledSet, each_set


@each_set
def test_every_clean_line_adds_up_and_is_paid_as_its_own_hours_and_rates_say(
    labelled: LabelledSet,
):
    labels = labelled.seeded.labels
    arithmetic = {(x.case_id, x.worker_id) for x in labels if "arithmetic" in x.rule}
    for case in labelled.cases:
        for submission in case.submissions:
            for line in submission.payroll.lines:
                seeded = (case.case_id, line.worker_id) in arithmetic
                if seeded and submission.number == 1:
                    continue
                assert sum(line.hours, Decimal(0)) == line.total_hours
                assert line.gross == wage_rules.gross(
                    line.base_rate, line.total_hours, line.overtime_hours
                )
                assert line.net == line.gross - line.deductions
