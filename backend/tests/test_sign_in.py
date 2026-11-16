"""Reviewers sign in through Supabase Auth, and the backend checks the reviewer on
every action a reviewer takes."""

import jwt
import pytest
from sqlalchemy import select

from backend import auth
from backend.database import engine, reviewers
from backend.seeding import load
from backend.tests.case_requests import awaiting_review
from backend.tests.gates import REVIEWER_OPERATIONS
from backend.tests.rows import everything_recorded
from backend.tests.sign_in import DANA, OTHER_KEY, SUPABASE_URL, signed_in, token

NOT_SIGNED_IN = {
    "no token": {},
    "another key": signed_in(DANA, key=OTHER_KEY),
    "expired": signed_in(DANA, expires_in=-60),
    "another audience": signed_in(DANA, audience="anon"),
    "not a token": {"Authorization": "Bearer not-a-token"},
}


def test_the_signed_in_reviewer(client):
    response = client.get("/api/me", headers=signed_in(DANA))
    assert response.status_code == 200
    assert response.json() == {
        "reviewer_id": "HND-01",
        "name": "Dana Whitfield",
        "role": "Compliance Manager",
        "email": DANA,
        "can_approve_over_limit": True,
    }


def test_a_browsers_request_with_no_key_header_at_all_is_the_reviewers(dashboard):
    headers = {"Authorization": f"Bearer {token(DANA)}"}
    assert dashboard.get("/api/me", headers=headers).status_code == 200


def test_a_sign_in_issued_a_little_ahead_of_our_clock_is_fine(client):
    headers = signed_in(DANA, issued_in=5)
    assert client.get("/api/me", headers=headers).status_code == 200


def test_supabase_out_of_reach_isnt_a_bad_sign_in(client, monkeypatch):
    def unreachable(_):
        raise jwt.PyJWKClientConnectionError("Fail to fetch data from the url")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", unreachable)
    refused = client.get("/api/me", headers=signed_in(DANA))
    assert (refused.status_code, refused.json()["detail"]) == (
        503,
        "Sign-in can't be checked: Supabase is out of reach",
    )


def test_a_sign_in_that_isnt_a_reviewers_is_refused(client):
    response = client.get("/api/me", headers=signed_in("visitor@example.com"))
    assert response.status_code == 403
    assert response.json()["detail"] == (
        "visitor@example.com isn't one of our reviewers"
    )


@pytest.mark.parametrize(
    ("method", "path", "body"),
    REVIEWER_OPERATIONS.values(),
    ids=REVIEWER_OPERATIONS.keys(),
)
def test_every_reviewer_operation_needs_a_sign_in_and_the_key_wont_do(
    client, agent_calls, method, path, body
):
    """The client sends the agent's key with every request, which never stands in
    for a reviewer."""
    awaiting_review(client, "PC-1202")
    before = everything_recorded()
    for headers in NOT_SIGNED_IN.values():
        response = client.request(method, path, json=body, headers=headers)
        assert response.status_code == 401
    assert everything_recorded() == before
    assert agent_calls == []


def test_seeding_stores_each_reviewers_email_and_who_can_sign_off_over_the_limit():
    with engine().connect() as db:
        rows = db.execute(select(reviewers).order_by(reviewers.c.reviewer_id))
        seeded = [
            (row["name"], row["email"], row["can_approve_over_limit"])
            for row in rows.mappings()
        ]
    assert seeded == [
        (h["name"], h["email"], h["can_approve_over_limit"])
        for h in load("reviewers.json")
    ]
    assert [can for _, _, can in seeded] == [True, False, False]


def test_the_public_keys_are_fetched_from_the_supabase_project():
    keys = auth.public_keys()
    assert keys.uri == f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    assert auth.public_keys() is keys
