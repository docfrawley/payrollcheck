"""Withheld text: on a case the screening flagged, the Copilot's reads replace
everything its subcontractor wrote, its exceptions' expected and actual and the
screening's reason, which quotes what it found, and pass its numbers, dates, our
records' ids, rule codes, shortfalls and citations. The case page's own read
still shows the reviewer everything."""

from fastapi.routing import APIRoute

from backend.copilot_reads import router
from backend.tests.copilot_reads import (
    LAST_WEEK,
    ask,
    classification_changes,
    exposure,
    filings,
    find_cases,
    read,
)
from backend.tests.flagged import FLAGGED, REASON, WORKER, flag_with_planted_text
from backend.tests.sign_in import DANA, signed_in
from backend.withheld import SCREENED, WITHHELD

# The reads that can give a flagged case's cells, and those that give none.
WITH_CELLS = {
    "find_cases",
    "read_case",
    "get_exceptions",
    "classification_changes",
    "draft_notice",
}
WITHOUT_CELLS = {"exposure_summary", "filings_status", "find_projects"}


def answers(client):
    """What each of the Copilot's reads gives about the flagged case, as Dana."""
    return {
        "find_cases": find_cases(client, DANA, status="awaiting_review"),
        "read_case": read(client, f"/cases/{FLAGGED}", DANA),
        "get_exceptions": read(client, f"/cases/{FLAGGED}/exceptions", DANA),
        "classification_changes": classification_changes(client, LAST_WEEK, DANA),
        "exposure_summary": exposure(client, DANA),
        "filings_status": filings(client, LAST_WEEK, DANA),
        "find_projects": read(client, "/projects?name=renovation", DANA),
        "draft_notice": ask(client, f"/cases/{FLAGGED}/notice-draft", None, DANA),
    }


def test_every_read_is_checked():
    operations = {r.operation_id for r in router.routes if isinstance(r, APIRoute)}
    assert operations == WITH_CELLS | WITHOUT_CELLS


def test_no_read_gives_a_flagged_cases_text(dashboard):
    planted = flag_with_planted_text()
    for operation, answer in answers(dashboard).items():
        assert answer.status_code == 200, operation
        for text in planted:
            assert text not in answer.text, (operation, text)
    # Once its notice is drafted from the exceptions, its case in full too.
    again = read(dashboard, f"/cases/{FLAGGED}", DANA)
    assert again.json()["notice"]["draft"] == WITHHELD
    for text in planted:
        assert text not in again.text, text


def test_a_flagged_case_in_full_passes_what_isnt_its_text(dashboard):
    flag_with_planted_text()
    case = read(dashboard, f"/cases/{FLAGGED}", DANA).json()
    assert (case["screening_flag"], case["screening_reason"]) == (True, SCREENED)
    [submission] = case["submissions"]
    certification = submission["certification"]
    [line] = [x for x in submission["lines"] if x["worker_id"] == WORKER]
    for key in ("contractor_name", "payroll_notes", "fein", "registration_no"):
        assert certification[key] == WITHHELD
    assert submission["file_name"] == WITHHELD
    ids = [x["worker_id"] for x in submission["lines"]]
    assert WORKER in ids
    assert WITHHELD in ids
    assert (certification["payroll_no"], certification["week_ending"]) == (
        submission["payroll_no"],
        "2026-11-22",
    )
    assert line["line_notes"] == line["classification"] == WITHHELD
    assert line["base_rate"] > 0
    assert line["hours"]
    added = case["exceptions"][-1]
    assert (added["expected"], added["actual"]) == (WITHHELD, WITHHELD)
    assert (added["rule"], added["shortfall_cents"]) == ("rate.base_short", 1234)
    assert added["citation"].startswith("The rate determination")
    # Our records pass: the subcontractor's and the worker's names.
    assert case["subcontractor_name"] == "Raritan Valley Carpentry Inc."
    assert "Tariq Fitzgerald" in [w["name"] for w in case["workers"]]


def test_its_open_exceptions_pass_their_amounts_and_reason(dashboard):
    flag_with_planted_text()
    found = read(dashboard, f"/cases/{FLAGGED}/exceptions", DANA).json()
    assert found["screening_reason"] == SCREENED
    [exception] = found["exceptions"]
    assert (exception["expected"], exception["actual"]) == (WITHHELD, WITHHELD)
    assert (exception["shortfall_cents"], exception["shortfall"]) == (1234, "$12.34")


def test_its_classification_change_is_withheld_but_named(dashboard):
    flag_with_planted_text()
    changes = classification_changes(dashboard, LAST_WEEK, DANA).json()["changes"]
    [change] = [c for c in changes if c["case_id"] == FLAGGED]
    assert change["worker_id"] == WORKER
    assert change["classification_after"] == change["line_notes"] == WITHHELD
    # The week before isn't flagged.
    assert change["classification_before"] == "Carpenter Journeyman"
    others = [c for c in changes if c["case_id"] != FLAGGED]
    assert others
    assert all(WITHHELD not in c.values() for c in others)


def test_a_flagged_week_before_withholds_only_its_side(dashboard):
    # PC-1102 is the week before PC-1202, for the same subcontractor and project.
    planted = flag_with_planted_text("PC-1102")
    answer = classification_changes(dashboard, LAST_WEEK, DANA)
    for text in planted:
        assert text not in answer.text
    [change] = [c for c in answer.json()["changes"] if c["case_id"] == FLAGGED]
    assert change["case_id_before"] == "PC-1102"
    assert change["classification_before"] == WITHHELD
    assert change["classification_after"] == "Carpenter Foreman"
    assert change["line_notes"].startswith("Acting foreman")


def test_an_unflagged_case_is_untouched(dashboard):
    case = read(dashboard, "/cases/PC-1202", DANA).json()
    assert WITHHELD not in str(case)
    notes = [line["line_notes"] for line in case["submissions"][0]["lines"]]
    assert any(note.startswith("Acting") for note in notes)


def test_the_case_page_still_shows_the_reviewer_everything(dashboard):
    planted = flag_with_planted_text()
    page = dashboard.get(f"/api/cases/{FLAGGED}", headers=signed_in(DANA))
    for text in planted:
        assert text in page.text
    assert page.json()["screening_reason"] == REASON
