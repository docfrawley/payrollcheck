"""Every clean payroll is paid as its own hours and rates say and passes every
rule."""

from decimal import Decimal

from context import wage_rules
from data.tests.development_set import CASES, WORLD
from data.tests.rule_audit import Audit


def test_every_lines_hours_add_up_and_its_pay_follows_its_hours_and_rates():
    for case in CASES:
        for line in case.submissions[0].payroll.lines:
            assert sum(line.hours, Decimal(0)) == line.total_hours
            assert line.gross == wage_rules.gross(
                line.base_rate, line.total_hours, line.overtime_hours
            )
            assert line.net == line.gross - line.deductions


def test_every_clean_payroll_passes_every_rule():
    audit = Audit(WORLD, CASES)
    for case in CASES:
        for submission in case.submissions:
            assert audit.findings(case, submission) == [], case.case_id
