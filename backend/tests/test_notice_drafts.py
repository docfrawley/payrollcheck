"""The send-back notice the Copilot drafts: worded by the backend from the case's
open exceptions, saved as the latest submission's draft for the reviewer, never
over the reviewer's unsent edit."""

from sqlalchemy import select

from backend import notices as notices_module
from backend.database import cases, engine, notices
from backend.dependencies import API_KEY_HEADER
from backend.tests.case_requests import (
    awaiting_review,
    finding,
    save_notice,
    send_again,
)
from backend.tests.copilot_reads import ask
from backend.tests.rows import change
from backend.tests.sign_in import MARCUS, signed_in

CASE = "PC-0311"
DRAFTED_BY = "PayrollCheck Copilot for Marcus Oyelaran"


def draft_notice(client, case_id=CASE, email=MARCUS):
    return ask(client, f"/cases/{case_id}/notice-draft", None, email)


def saved(case_id=CASE):
    with engine().connect() as db:
        return (
            db.execute(select(notices).where(notices.c.case_id == case_id))
            .mappings()
            .one()
        )


def test_pc_0311s_draft_covers_its_three_exceptions(dashboard):
    answer = draft_notice(dashboard)
    assert answer.status_code == 200
    drafted = answer.json()
    assert (drafted["drafted_by"], drafted["send_from"]) == (
        DRAFTED_BY,
        "the case page",
    )
    draft = drafted["draft"]
    assert draft.startswith(
        "Certified payroll PC-0311, Municipal building, week ending Sep 20, 2026"
    )
    assert "3 items" in draft
    for paragraph, amount in (("1.", "$60.00"), ("2.", "$150.00"), ("3.", "$293.75")):
        [found] = [p for p in draft.split("\n\n") if p.startswith(paragraph)]
        assert f"Amount owed: {amount}." in found
        assert ", line " in found
        assert "We expected" in found
        assert "the payroll shows" in found
    assert "In all, $503.75 is owed" in draft
    assert "corrected certified payroll" in draft


def test_it_is_saved_as_the_latest_submissions_draft(dashboard):
    draft = draft_notice(dashboard).json()["draft"]
    row = saved()
    assert (row["submission_no"], row["draft"], row["drafted_by"]) == (
        1,
        draft,
        DRAFTED_BY,
    )
    assert row["drafted_at"]


def test_a_case_with_nothing_open_is_refused(dashboard):
    # PC-0101 is Accepted, and PC-1202 Received.
    for case_id in ("PC-0101", "PC-1202"):
        assert draft_notice(dashboard, case_id).status_code == 409
    change(cases, cases.c.case_id == "PC-1201", status="awaiting_review")
    nothing = draft_notice(dashboard, "PC-1201")
    assert (nothing.status_code, nothing.json()["detail"]) == (
        409,
        "PC-1201 has no open exception to put in a notice",
    )


def test_a_reviewers_unsent_edit_is_never_overwritten(dashboard):
    save_notice(dashboard, CASE, "Please fix line 1.", MARCUS)
    refused = draft_notice(dashboard)
    assert refused.status_code == 409
    detail = refused.json()["detail"]
    assert detail.startswith("PC-0311's notice has Marcus Oyelaran's edit of ")
    assert detail.endswith(". Edit it on the case page.")
    assert saved()["edited_text"] == "Please fix line 1."


def test_a_notice_already_sent_is_replaced_by_the_new_draft(dashboard):
    save_notice(dashboard, CASE, "Please fix line 1.", MARCUS)
    assert send_again(dashboard, CASE, MARCUS).status_code == 200
    assert draft_notice(dashboard).status_code == 200
    row = saved()
    assert (row["drafted_by"], row["edited_text"], row["sent_at"]) == (
        DRAFTED_BY,
        None,
        None,
    )
    # The outbox keeps what was sent.
    case = dashboard.get(f"/api/cases/{CASE}", headers=signed_in(MARCUS)).json()
    assert [n["body"] for n in case["sent_notices"]] == ["Please fix line 1."]


def test_the_agents_key_drafts_no_notice(client, agent_key):
    with_the_key = signed_in(MARCUS) | {API_KEY_HEADER: agent_key}
    path = f"/api/copilot/cases/{CASE}/notice-draft"
    assert client.post(path, headers=with_the_key).status_code == 403
    with engine().connect() as db:
        query = select(notices).where(notices.c.case_id == CASE)
        assert db.execute(query).first() is None


def test_an_agents_draft_with_no_edit_is_replaced(dashboard, client):
    awaiting_review(client, "PC-1201", finding())
    assert saved("PC-1201")["drafted_for"] is None
    assert draft_notice(dashboard, "PC-1201").status_code == 200
    row = saved("PC-1201")
    assert (row["drafted_by"], row["drafted_for"]) == (DRAFTED_BY, "Marcus Oyelaran")
    assert row["draft"].startswith("Certified payroll PC-1201,")


def test_the_judge_and_the_improver_never_read_a_copilot_draft_as_the_agents(
    dashboard,
):
    draft_notice(dashboard)
    save_notice(dashboard, CASE, "Please pay W-025 what is owed.", MARCUS)
    with engine().connect() as db:
        assert notices_module.drafts_of(db, [CASE]) == {}
        edited, _ = notices_module.edited_between(db, "2000-01-01", "2999-01-01", 10)
    assert edited == 0
