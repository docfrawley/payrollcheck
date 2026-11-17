"""Exposure counts each case's latest submission only: superseded exceptions never,
dismissed ones not at all, and outstanding only on cases Awaiting review or
Returned to sub."""

from backend.database import cases, exceptions
from backend.tests.copilot_reads import exposure
from backend.tests.rows import change

# The money exceptions open after seeding on Marcus's projects.
OPEN_MONEY = ["PC-0311", "PC-0601", "PC-1009"]


def test_only_latest_submissions_count(dashboard):
    found = exposure(dashboard).json()
    assert found["case_ids"] == OPEN_MONEY
    # PC-0212 was corrected: its first submission's $64.00 is superseded.
    assert "PC-0212" not in found["case_ids"]
    assert found["flagged_cents"] == 6000 + 15000 + 29375 + 7200 + 10000 + 9875


def test_an_open_exception_on_an_earlier_submission_isnt_counted(dashboard):
    # As if PC-1009 had a correction whose report found nothing.
    change(cases, cases.c.case_id == "PC-1009", latest_submission_no=2)
    found = exposure(dashboard, subcontractor_id="SUB-01").json()
    assert found["case_ids"] == ["PC-0601"]


def test_an_open_exception_on_a_case_returned_to_sub_is_outstanding(dashboard):
    found = exposure(dashboard, subcontractor_id="SUB-01").json()
    returned = [e for e in found["exceptions"] if e["status"] == "returned_to_sub"]
    assert len(returned) == 3
    assert all(e["outstanding"] for e in returned)
    assert found["outstanding_cents"] == found["flagged_cents"] == 7200 + 19875


def test_a_dismissed_exception_is_left_out(dashboard):
    change(
        exceptions,
        exceptions.c.case_id == "PC-1009",
        exceptions.c.rule == "rate.base_short",
        status="dismissed",
    )
    found = exposure(dashboard, subcontractor_id="SUB-01").json()
    assert (found["flagged_cents"], found["flagged"]) == (9875 + 7200, "$170.75")


def test_outstanding_is_only_on_cases_awaiting_review_or_returned(dashboard):
    change(cases, cases.c.case_id == "PC-0601", status="awaiting_review")
    change(cases, cases.c.case_id == "PC-1009", status="in_progress")
    found = exposure(dashboard, subcontractor_id="SUB-01").json()
    assert found["flagged_cents"] == 7200 + 10000 + 9875
    assert (found["outstanding_cents"], found["outstanding"]) == (7200, "$72.00")
    assert [(e["case_id"], e["outstanding"]) for e in found["exceptions"]] == [
        ("PC-0601", True),
        ("PC-1009", False),
        ("PC-1009", False),
    ]


def test_an_exception_without_a_shortfall_isnt_counted(dashboard):
    # PC-0302's one open exception is a late filing, which carries no money.
    found = exposure(dashboard, project_id="PRJ-01").json()
    assert "PC-0302" not in found["case_ids"]
    assert found["case_ids"] == ["PC-0601"]


def test_the_breakdown_by_rule_adds_up_to_the_totals(dashboard):
    found = exposure(dashboard).json()
    rules = {r["rule"]: r for r in found["by_rule"]}
    assert set(rules) == {"rate.base_short", "rate.fringe_short", "overtime.underpaid"}
    assert rules["rate.base_short"]["case_ids"] == OPEN_MONEY
    assert rules["overtime.underpaid"]["flagged"] == "$293.75"
    assert sum(r["flagged_cents"] for r in rules.values()) == found["flagged_cents"]
    assert (
        sum(r["outstanding_cents"] for r in rules.values())
        == (found["outstanding_cents"])
    )
    assert found["flagged"] == "$774.50"
