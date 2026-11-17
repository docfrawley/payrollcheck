"""A worker's classification change from the week before, with its note, the
worker's established craft and the open exception on the line."""

from sqlalchemy import insert, select

from backend.database import engine, exceptions, submissions
from backend.tests.copilot_reads import LAST_WEEK, classification_changes
from backend.tests.rows import change

FIRST_WEEK = {"kind": "between", "first": "2026-09-06", "last": "2026-09-06"}
SECOND_WEEK = {"kind": "between", "first": "2026-09-13", "last": "2026-09-13"}


def changes(client, period=LAST_WEEK):
    return classification_changes(client, period).json()["changes"]


def test_a_change_is_listed_with_its_note_its_craft_and_its_exception(dashboard):
    with engine().begin() as db:
        db.execute(
            insert(exceptions).values(
                case_id="PC-1204",
                submission_no=1,
                rule="classification.mismatch",
                severity="high",
                worker_id="W-008",
                line_no=1,
                expected="Ironworker Journeyman",
                actual="Laborer Journeyman",
                shortfall_cents=None,
                citation="Our worker records",
                raised_by="A test",
                source="reviewer",
                status="open",
            )
        )
    found = {c["case_id"]: c for c in changes(dashboard)}
    acting = found["PC-1202"]
    assert acting["line_notes"].startswith("Acting foreman")
    assert acting["established_craft"] == "carpenter"
    assert acting["exception"] is None
    moved = found["PC-1204"]
    assert moved["established_craft"] == "ironworker"
    assert moved["exception"]["rule"] == "classification.mismatch"
    assert moved["exception"]["severity"] == "high"


def test_no_change_isnt_listed(dashboard):
    assert [
        c["worker_id"] for c in changes(dashboard) if c["case_id"] == "PC-1202"
    ] == ["W-004"]


def test_a_first_week_with_no_week_before_isnt_listed(dashboard):
    with engine().begin() as db:
        lines = db.execute(
            select(submissions.c.lines).where(submissions.c.case_id == "PC-0101")
        ).scalar_one()
    lines[0]["classification"] = "Electrician Foreman"
    change(submissions, submissions.c.case_id == "PC-0101", lines=lines)
    assert changes(dashboard, FIRST_WEEK) == []
    # The week after compares with it, so the change shows there.
    second = [c for c in changes(dashboard, SECOND_WEEK) if c["case_id"] == "PC-0201"]
    assert [(c["worker_id"], c["classification_before"]) for c in second] == [
        (lines[0]["worker_id"], "Electrician Foreman")
    ]


def test_the_first_week_of_a_period_compares_with_the_week_before_it(dashboard):
    # PC-1202's change is against week 11, which is outside last week.
    assert "PC-1202" in {c["case_id"] for c in changes(dashboard, LAST_WEEK)}
