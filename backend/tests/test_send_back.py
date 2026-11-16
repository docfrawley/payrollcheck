"""Send back: the case is Returned to sub and its notice goes to the outbox, one
record to the subcontractor's payroll contact with the notice as the reviewer
edited it, delivered once, in the same transaction as the move."""

import threading

import pytest
from sqlalchemy import select

from backend import outbox
from backend.database import engine, notices
from backend.database import outbox as outbox_table
from backend.tests.case_requests import (
    NOTICE,
    awaiting_review,
    finding,
    save_notice,
    send_back,
)
from backend.tests.rows import committed_case, count, everything_recorded
from backend.tests.sign_in import MARCUS

CASE = "PC-1201"
EDITED = "Please pay Kim Dimitrov the journeyman base rate on line 1 and resubmit."
SUBJECT = (
    "Certified payroll PC-1201, Lincoln School renovation, week ending "
    "Nov 22, 2026: corrections needed"
)


@pytest.fixture
def delivered(monkeypatch):
    """The outbox rows deliver is called with, in place of sending them."""
    rows = []
    monkeypatch.setattr(outbox, "deliver", rows.append)
    return rows


def test_send_back_writes_one_outbox_record_and_delivers_it(
    dashboard, client, delivered
):
    awaiting_review(client, CASE, finding())
    save_notice(client, CASE, EDITED, MARCUS)
    sent = send_back(dashboard, CASE, MARCUS)
    assert (sent.status_code, sent.json()["status"]) == (200, "returned_to_sub")
    [record] = sent.json()["sent_notices"]
    assert {key: record[key] for key in ("to_address", "subject", "body")} == {
        "to_address": "payroll@gardenstateelectric.example",
        "subject": SUBJECT,
        "body": EDITED,
    }
    assert record["sent_by"] == "Marcus Oyelaran <marcus.oyelaran@payrollcheck.example>"
    assert record["sent_at"]
    assert record["draft"] == NOTICE
    [row] = delivered
    assert (row["outbox_id"], row["body"]) == (record["outbox_id"], EDITED)
    assert count(outbox_table) == 1


def test_the_draft_and_the_sent_text_are_both_kept(dashboard, client, delivered):
    awaiting_review(client, CASE, finding())
    save_notice(client, CASE, EDITED, MARCUS)
    send_back(dashboard, CASE, MARCUS)
    notice = client.get(f"/api/cases/{CASE}").json()["notice"]
    assert (notice["draft"], notice["edited_text"]) == (NOTICE, EDITED)
    assert (notice["edited_by"], notice["sent_by"]) == (
        "Marcus Oyelaran",
        "Marcus Oyelaran",
    )


def test_the_answer_shows_the_notice_sent_and_its_record(dashboard, client, delivered):
    awaiting_review(client, CASE, finding())
    answer = send_back(dashboard, CASE, MARCUS).json()
    assert answer["notice"]["sent_by"] == "Marcus Oyelaran"
    assert answer["notice"]["sent_at"] == answer["sent_notices"][0]["sent_at"]


def test_the_edit_stored_when_the_case_is_sent_back_is_the_one_sent(
    dashboard, client, delivered
):
    """Send back reads the notice once it holds the case, so the outbox sends the
    edit the notice keeps, never an earlier one."""
    awaiting_review(client, CASE, finding())
    save_notice(client, CASE, "A first edit", MARCUS)
    save_notice(client, CASE, EDITED, MARCUS)
    [record] = send_back(dashboard, CASE, MARCUS).json()["sent_notices"]
    stored = client.get(f"/api/cases/{CASE}").json()["notice"]["edited_text"]
    assert record["body"] == stored == EDITED


def test_the_draft_is_sent_when_nobody_edited_it(dashboard, client, delivered):
    awaiting_review(client, CASE, finding())
    [record] = send_back(dashboard, CASE, MARCUS).json()["sent_notices"]
    assert record["body"] == NOTICE


def test_a_case_with_no_notice_to_send_isnt_sent_back(dashboard, client, delivered):
    awaiting_review(client, CASE)
    before = everything_recorded()
    refused = send_back(dashboard, CASE, MARCUS)
    assert (refused.status_code, refused.json()["detail"]) == (
        422,
        f"{CASE} has no notice to send: write one for its subcontractor first",
    )
    assert everything_recorded() == before
    assert delivered == []


def test_two_send_backs_at_the_same_moment_write_one_record(
    dashboard, client, delivered
):
    awaiting_review(client, CASE, finding())
    together = threading.Barrier(2)
    answers = []

    def send():
        together.wait()
        answers.append(send_back(dashboard, CASE, MARCUS).status_code)

    sending = [threading.Thread(target=send) for _ in range(2)]
    for thread in sending:
        thread.start()
    for thread in sending:
        thread.join(10)
    assert sorted(answers) == [200, 409]
    assert count(outbox_table) == 1
    assert len(delivered) == 1


def test_a_notice_that_cant_be_delivered_leaves_the_case_awaiting_review(
    dashboard, client, monkeypatch
):
    awaiting_review(client, CASE, finding())

    def undeliverable(_):
        raise RuntimeError("The mail server is down")

    monkeypatch.setattr(outbox, "deliver", undeliverable)
    with pytest.raises(RuntimeError):
        send_back(dashboard, CASE, MARCUS)
    assert committed_case(CASE)["status"] == "awaiting_review"
    assert count(outbox_table) == 0
    with engine().connect() as db:
        sent_by = db.execute(
            select(notices.c.sent_by).where(notices.c.case_id == CASE)
        ).scalar_one()
    assert sent_by is None
