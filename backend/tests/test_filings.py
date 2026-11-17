"""Filings are worked out from engagement windows, never a stored list, with
missing and late as of the business date."""

from sqlalchemy import insert, select

from backend.database import cases, engagements, engine, submissions
from backend.filings import DUE_DAYS
from backend.tests.copilot_reads import LAST_WEEK, filings
from backend.tests.rows import change
from backend.tests.settings_requests import change_settings
from context.payroll_files import FILES
from context.sources import FILING_RULES

WEEK_12 = {"kind": "between", "first": "2026-11-22", "last": "2026-11-22"}


def paid(case_id, wage_payment_date, received_on):
    change(
        submissions,
        submissions.c.case_id == case_id,
        submissions.c.submission_no == 1,
        wage_payment_date=wage_payment_date,
        received_on=received_on,
    )


def late_ids(found):
    return [f["case_id"] for f in found["late"]]


def test_the_backends_due_days_are_the_filing_rules():
    assert FILES[FILING_RULES]["due_days"] == DUE_DAYS


def test_eleven_days_after_the_wage_payment_date_is_late_and_ten_isnt(dashboard):
    paid("PC-1201", "2026-11-12", "2026-11-23")
    found = filings(dashboard, LAST_WEEK).json()
    assert late_ids(found) == ["PC-1201", "PC-1208"]
    assert found["late"][0]["days_after_payment"] == 11
    paid("PC-1201", "2026-11-13", "2026-11-23")
    found = filings(dashboard, LAST_WEEK).json()
    assert late_ids(found) == ["PC-1208"]
    assert "PC-1201" in found["on_time"]


def test_a_correction_received_late_doesnt_make_a_filing_late(dashboard):
    with engine().begin() as db:
        first = (
            db.execute(select(submissions).where(submissions.c.case_id == "PC-1201"))
            .mappings()
            .one()
        )
        db.execute(
            insert(submissions).values(
                {**first, "submission_no": 2, "received_on": "2026-12-20"}
            )
        )
    change(cases, cases.c.case_id == "PC-1201", latest_submission_no=2)
    found = filings(dashboard, LAST_WEEK).json()
    assert "PC-1201" in found["on_time"]
    assert "PC-1201" not in late_ids(found)


def test_a_missing_filing_is_late_once_past_its_week_ending_and_the_due_days(
    dashboard,
):
    change_settings(dashboard, business_date="2026-12-02")
    [missing] = filings(dashboard, WEEK_12).json()["missing"]
    assert (missing["deadline"], missing["late"]) == ("2026-12-02", False)
    change_settings(dashboard, business_date="2026-12-03")
    [missing] = filings(dashboard, WEEK_12).json()["missing"]
    assert missing["late"] is True


def test_a_week_ending_after_the_business_date_isnt_missing(dashboard):
    change_settings(dashboard, business_date="2026-11-20")
    found = filings(dashboard, WEEK_12).json()
    assert found["missing"] == []
    assert found["business_date"] == "2026-11-20"


def test_the_expected_filings_come_from_the_engagement_windows(dashboard):
    change(
        engagements,
        engagements.c.subcontractor_id == "SUB-06",
        engagements.c.project_id == "PRJ-02",
        last_week_ending="2026-11-15",
    )
    assert filings(dashboard, LAST_WEEK).json()["missing"] == []
