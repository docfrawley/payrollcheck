"""What the app gives the Copilot to read beside the dashboard's reads: subcontractors
by name and in full, the count of payouts over the limit, a run a reviewer started, and
the Copilot's model."""

import json

from sqlalchemy import insert

from backend.database import engine, now, payments
from backend.tests.case_requests import decide, held, pay, sign_off, start
from backend.tests.dashboard_reads import read
from backend.tests.run_requests import create_evaluation, start_dispatch
from backend.tests.sign_in import DANA


def paid_without_a_sign_off(case_id, amount):
    """Write a payment straight into the table, as nothing in the app would for a
    payout held for sign-off."""
    with engine().begin() as db:
        db.execute(
            insert(payments).values(case_id=case_id, amount=amount, paid_at=now())
        )


def test_find_subcontractors_by_the_words_in_their_name(dashboard):
    found = read(dashboard, "/api/subcontractors?name=maya").json()
    assert found == [{"subcontractor_id": "CUS-3001", "name": "Maya Patel"}]
    assert read(dashboard, "/api/subcontractors?name=PATEL%20maya").json() == found
    assert read(dashboard, "/api/subcontractors?name=nobody").json() == []


def test_a_blank_name_finds_nothing(dashboard):
    for name in ("", "%20%20"):
        assert read(dashboard, f"/api/subcontractors?name={name}").status_code == 422
    assert read(dashboard, "/api/subcontractors").status_code == 422


def test_a_subcontractor_in_full_without_their_personal_details(dashboard):
    subcontractor = read(dashboard, "/api/subcontractors/CUS-3001").json()
    assert subcontractor["name"] == "Maya Patel"
    assert "POL-2001" in [policy["policy_id"] for policy in subcontractor["policies"]]
    assert "CLM-0412" in [case["case_id"] for case in subcontractor["earlier_cases"]]
    assert "CLM-1001" in [c["case_id"] for c in subcontractor["cases_in_the_queue"]]
    assert {"email", "phone", "address", "date_of_birth"} & set(subcontractor) == set()
    assert "maya.patel@example.com" not in json.dumps(subcontractor)
    unknown = read(dashboard, "/api/subcontractors/CUS-9999")
    assert (unknown.status_code, unknown.json()["detail"]) == (
        404,
        "Subcontractor CUS-9999 not found",
    )


def over_the_limit(client):
    return read(client, "/api/payouts/over-limit").json()


def test_the_payouts_over_the_limit_and_those_signed_off(client, dashboard):
    assert over_the_limit(dashboard) == {"paid_over_the_limit": 0, "signed_off": 0}
    held(client, "CLM-1002", 1350.0)
    sign_off(client, "CLM-1002", DANA)
    assert over_the_limit(dashboard) == {"paid_over_the_limit": 1, "signed_off": 1}
    held(client, "CLM-1008", 1200.0)
    paid_without_a_sign_off("CLM-1008", 1200.0)
    assert over_the_limit(dashboard) == {"paid_over_the_limit": 2, "signed_off": 1}


def test_a_payout_within_the_limit_and_a_copy_arent_counted(client, dashboard):
    start(client, "CLM-1001")
    decide(client, "CLM-1001", "approve", 420.0)
    pay(client, "CLM-1001", 420.0)
    copy = create_evaluation(client).json()["cases"][0]["case_id"]
    held(client, copy, 1500.0)
    paid_without_a_sign_off(copy, 1500.0)
    assert over_the_limit(dashboard) == {"paid_over_the_limit": 0, "signed_off": 0}


def test_a_reviewer_reads_the_run_a_start_names(dashboard):
    started = start_dispatch(dashboard, 10, DANA)
    assert started.status_code == 202
    body = started.json()
    run = read(dashboard, f"/api/runs/{body['run_id']}").json()
    assert (run["number"], run["agents"], run["status"]) == (
        body["number"],
        10,
        "running",
    )


def test_the_copilots_model(dashboard, monkeypatch):
    model = read(dashboard, "/api/copilot/model").json()
    assert model == {"model": "openai/gpt-6-luna", "reasoning_effort": "low"}
    monkeypatch.setenv("MODEL_NAME", "free/model")
    model = read(dashboard, "/api/copilot/model").json()
    assert model == {"model": "free/model", "reasoning_effort": "default"}
