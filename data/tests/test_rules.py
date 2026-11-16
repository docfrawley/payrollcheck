"""Every rule code and kind of decoy has its corruption or its shape, and nothing
else has one."""

from data.payroll_world.corruptions import LINE_CORRUPTIONS, PAYROLL_CORRUPTIONS
from data.payroll_world.decoys import SHAPES
from data.payroll_world.rules import CASE_RULES, LINE_DECOYS, LINE_RULES, PAYROLL_DECOYS


def test_every_rule_has_its_corruption():
    assert set(LINE_CORRUPTIONS) == set(LINE_RULES)
    assert set(PAYROLL_CORRUPTIONS) == set(CASE_RULES)


def test_every_kind_of_decoy_has_its_shape():
    assert set(SHAPES) == set(LINE_DECOYS + PAYROLL_DECOYS)
