"""The send-back notice: a reviewer saves an edit beside the agent's draft without
sending it, or writes one where the agent drafted none, on a case awaiting review,
and never with the agent's key."""

from backend.dependencies import API_KEY_HEADER
from backend.tests.case_requests import NOTICE, awaiting_review, finding, save_notice
from backend.tests.sign_in import MARCUS, PRIYA, signed_in

CASE = "PC-1201"
EDITED = "Please pay the journeyman base rate on line 1 and resubmit."


def test_an_edit_is_saved_beside_the_draft_without_sending(client):
    awaiting_review(client, CASE, finding())
    case = save_notice(client, CASE, EDITED, MARCUS).json()
    assert case["status"] == "awaiting_review"
    notice = case["notice"]
    assert (notice["draft"], notice["edited_text"], notice["edited_by"]) == (
        NOTICE,
        EDITED,
        "Marcus Oyelaran",
    )
    assert notice["edited_at"]
    assert (notice["sent_by"], notice["sent_at"]) == (None, None)
    assert case["sent_notices"] == []


def test_a_notice_is_written_where_the_agent_drafted_none(client):
    awaiting_review(client, CASE)
    assert client.get(f"/api/cases/{CASE}").json()["notice"] is None
    notice = save_notice(client, CASE, EDITED, MARCUS).json()["notice"]
    assert (notice["submission_no"], notice["draft"], notice["drafted_by"]) == (
        1,
        None,
        None,
    )
    assert notice["edited_text"] == EDITED


def test_a_blank_notice_isnt_saved(client):
    awaiting_review(client, CASE, finding())
    assert save_notice(client, CASE, "   ", MARCUS).status_code == 422


def test_a_notice_is_saved_only_on_a_case_in_review_in_scope(client):
    refused = save_notice(client, "PC-1202", EDITED, MARCUS)
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        "Case PC-1202's notice is written while it awaits review or is returned to "
        "its subcontractor",
    )
    assert save_notice(client, "PC-0101", EDITED, MARCUS).status_code == 409
    # PC-0311 is Returned to sub.
    assert save_notice(client, "PC-0311", EDITED, MARCUS).status_code == 200
    awaiting_review(client, CASE, finding())
    assert save_notice(client, CASE, EDITED, PRIYA).status_code == 404


def test_the_agents_key_saves_no_notice(client, agent_key):
    awaiting_review(client, CASE, finding())
    path = f"/api/cases/{CASE}/notice"
    assert client.put(path, json={"text": EDITED}).status_code == 401
    with_the_key = signed_in(MARCUS) | {API_KEY_HEADER: agent_key}
    refused = client.put(path, json={"text": EDITED}, headers=with_the_key)
    assert refused.status_code == 403
    assert client.get(f"/api/cases/{CASE}").json()["notice"]["edited_text"] is None
