import json

import httpx
import pytest

from deploy import supabase

URL = "https://abcdefghijkl.supabase.co"
ADMIN_KEY = "sb_secret_test"
SIGN_IN = "reviewers-password"
EMAILS = [
    "dana.whitfield@payrollcheck.example",
    "marcus.oyelaran@payrollcheck.example",
    "priya.raman@payrollcheck.example",
]


@pytest.fixture
def auth():
    """Supabase Auth's admin API with Dana's user already there, keeping the users
    created and the headers of every request."""
    users = [{"email": EMAILS[0]}]
    headers: list[httpx.Headers] = []
    created: list[dict] = []

    def answer(request: httpx.Request) -> httpx.Response:
        headers.append(request.headers)
        assert request.url.path == supabase.USERS
        if request.method == "GET":
            return httpx.Response(200, json={"users": users})
        body = json.loads(request.content)
        created.append(body)
        users.append({"email": body["email"]})
        return httpx.Response(200, json={"id": "new"})

    client = supabase.admin(URL, ADMIN_KEY, httpx.MockTransport(answer))
    return client, created, headers


def test_the_missing_reviewers_are_made_and_the_one_there_is_left(auth, capsys):
    client, created, headers = auth
    supabase.make_users(client, EMAILS, SIGN_IN)
    assert created == [
        {"email": EMAILS[1], "password": SIGN_IN, "email_confirm": True},
        {"email": EMAILS[2], "password": SIGN_IN, "email_confirm": True},
    ]
    assert all(h["apikey"] == ADMIN_KEY for h in headers)
    assert all(h["authorization"] == f"Bearer {ADMIN_KEY}" for h in headers)
    shown = capsys.readouterr().out
    assert f"Auth user {EMAILS[0]}: unchanged" in shown
    assert SIGN_IN not in shown
    assert ADMIN_KEY not in shown


def test_a_second_run_makes_no_one(auth):
    client, created, _ = auth
    supabase.make_users(client, EMAILS, SIGN_IN)
    supabase.make_users(client, EMAILS, SIGN_IN)
    assert len(created) == 2


def test_the_reviewers_are_ours():
    assert supabase.reviewer_emails() == EMAILS


def test_the_mcp_server_is_read_only_on_the_project():
    assert supabase.mcp_command(URL) == (
        'claude mcp add --transport http supabase "https://mcp.supabase.com/mcp'
        '?project_ref=abcdefghijkl&read_only=true"'
    )


def test_the_step_makes_the_users_and_prints_the_command(monkeypatch, capsys, auth):
    client, created, _ = auth
    monkeypatch.setenv("VITE_SUPABASE_URL", URL)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", ADMIN_KEY)
    monkeypatch.setenv("VITE_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    monkeypatch.setenv("REVIEWER_PASSWORD", SIGN_IN)
    asked: list[tuple[str, str]] = []

    def admin(url, key):
        asked.append((url, key))
        return client

    monkeypatch.setattr(supabase, "admin", admin)
    supabase.run()
    assert asked == [(URL, ADMIN_KEY)]
    assert len(created) == 2
    assert "project_ref=abcdefghijkl" in capsys.readouterr().out
