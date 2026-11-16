"""A corrected payroll reopens its case, whatever its status but In progress: the
upload is its next submission, the case is Received again as a fresh first attempt,
the earlier submissions' open exceptions are superseded and their dismissed ones
stay dismissed, and Sign off looks only at the new submission."""

import threading

from backend import intake
from backend.tests.case_requests import (
    awaiting_review,
    fail,
    finding,
    flag,
    report,
    send_back,
    sign_off,
    start,
)
from backend.tests.rows import committed_case, everything_recorded
from backend.tests.sign_in import MARCUS, signed_in
from backend.tests.uploads import seeded_payroll, upload

CASE = "PC-1201"


def correct(client):
    """Upload PC-1201's payroll again, as Marcus, as its corrected submission."""
    _, content = seeded_payroll(CASE)
    payroll = ("PC-1201-2.csv", content)
    return upload(client, "PRJ-01", "SUB-01", payroll, signed_in(MARCUS))


def dismiss(client, exception_id):
    return client.post(
        f"/api/cases/{CASE}/exceptions/{exception_id}/dismissal",
        json={"reason": "Paid on the corrected check"},
        headers=signed_in(MARCUS),
    )


def statuses(case):
    return [(e["submission_no"], e["status"]) for e in case["exceptions"]]


def two_exceptions(client):
    """PC-1201 awaiting review with a base rate and a fringe short, and their ids."""
    case = awaiting_review(
        client, CASE, finding(), finding(rule="rate.fringe_short", shortfall_cents=19)
    )
    return [e["exception_id"] for e in case["exceptions"]]


def test_a_correction_reopens_an_accepted_case(dashboard, client):
    base, fringe = two_exceptions(client)
    dismiss(client, base)
    dismiss(client, fringe)
    assert sign_off(dashboard, CASE, MARCUS).status_code == 200
    reopened = correct(client)
    assert reopened.status_code == 201
    case = reopened.json()
    assert (case["status"], case["latest_submission_no"]) == ("received", 2)
    assert (case["thread_id"], case["attempts"]) == (None, 0)
    assert (case["reviewed_by"], case["reviewed_on"]) == (None, None)
    assert statuses(case) == [(1, "dismissed"), (1, "dismissed")]
    assert (case["open_exceptions"], case["notice"]) == (0, None)
    assert [s["file_name"] for s in case["submissions"]] == [
        "PC-1201-1.csv",
        "PC-1201-2.csv",
    ]


def test_a_correction_supersedes_the_open_exceptions_and_keeps_the_dismissed(
    client,
):
    base, _ = two_exceptions(client)
    dismiss(client, base)
    case = correct(client).json()
    assert statuses(case) == [(1, "dismissed"), (1, "superseded")]
    assert case["status"] == "received"


def test_a_correction_reopens_a_case_returned_to_sub(dashboard, client):
    two_exceptions(client)
    assert send_back(dashboard, CASE, MARCUS).status_code == 200
    case = correct(client).json()
    assert (case["status"], case["latest_submission_no"]) == ("received", 2)
    assert statuses(case) == [(1, "superseded"), (1, "superseded")]
    assert [n["submission_no"] for n in case["sent_notices"]] == [1]


def test_a_reopened_case_is_worked_again_and_signed_off(dashboard, client):
    two_exceptions(client)
    correct(client)
    assert committed_case(CASE)["open_exceptions"] == 0
    start(client, CASE, thread_id="t-2")
    case = client.get(f"/api/cases/{CASE}").json()
    assert (case["status"], case["attempts"]) == ("in_progress", 1)
    report(client, CASE)
    assert sign_off(dashboard, CASE, MARCUS).status_code == 200


def test_a_flagged_case_reopens_unflagged(client):
    start(client, CASE)
    flag(client, CASE)
    case = correct(client).json()
    assert (case["screening_flag"], case["screening_reason"]) == (False, None)


def test_a_case_the_agent_failed_reopens_as_a_first_attempt(client):
    for attempt in ("t-1", "t-2"):
        start(client, CASE, thread_id=attempt)
        fail(client, CASE)
    assert committed_case(CASE)["agent_failed"]
    case = correct(client).json()
    assert (case["agent_failed"], case["attempts"], case["thread_id"]) == (
        False,
        0,
        None,
    )


def test_a_case_the_agent_starts_as_it_is_reopened_is_being_checked(
    client, monkeypatch
):
    """The reopen's conditional update alone, with the case as the upload read it
    before the agent started it."""
    as_read = dict(committed_case(CASE))
    start(client, CASE)
    monkeypatch.setattr(intake, "existing_case", lambda *_: as_read)
    refused = correct(client)
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        f"{CASE} is being checked: upload the correction once it's awaiting review",
    )


def test_a_case_being_checked_isnt_reopened(client):
    start(client, CASE)
    before = everything_recorded()
    refused = correct(client)
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        f"{CASE} is being checked: upload the correction once it's awaiting review",
    )
    assert everything_recorded() == before


def test_two_corrections_at_the_same_moment_make_one_submission(client):
    two_exceptions(client)
    together = threading.Barrier(2)
    answers = []

    def send():
        together.wait()
        answers.append(correct(client).status_code)

    sending = [threading.Thread(target=send) for _ in range(2)]
    for thread in sending:
        thread.start()
    for thread in sending:
        thread.join(10)
    assert sorted(answers) == [201, 409]
    case = client.get(f"/api/cases/{CASE}").json()
    assert [s["submission_no"] for s in case["submissions"]] == [1, 2]
