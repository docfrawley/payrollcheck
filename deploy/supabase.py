"""Step 1, Supabase: the three reviewers' users in the new project's Auth, made through
Supabase Auth's admin API with the project's secret key, and the command that points
Claude Code's read-only Supabase MCP server at the project."""

import json
from urllib.parse import urlparse

import httpx

from deploy import settings

USERS = "/auth/v1/admin/users"
REVIEWERS = settings.REPO / "data" / "reviewers.json"
# Enough for one page to hold every user of a project our size.
PAGE = {"page": 1, "per_page": 1000}


def reviewer_emails() -> list[str]:
    """Our reviewers' emails, from data/reviewers.json."""
    return [person["email"] for person in json.loads(REVIEWERS.read_text())]


def admin(url: str, secret_key: str, transport: httpx.BaseTransport | None = None):
    """A client for the project's Auth admin API, sending the secret key as Supabase's
    own client does."""
    return httpx.Client(
        base_url=url,
        headers={"apikey": secret_key, "Authorization": f"Bearer {secret_key}"},
        timeout=30,
        transport=transport,
    )


def make_users(client: httpx.Client, emails: list[str], password: str) -> None:
    """Create each reviewer's user who isn't there yet, email confirmed, with the
    reviewers' password, and leave alone those who are, password and all."""
    response = client.get(USERS, params=PAGE)
    response.raise_for_status()
    there = {user["email"] for user in response.json()["users"]}
    for email in emails:
        if email in there:
            print(f"Auth user {email}: unchanged")
            continue
        made = client.post(
            USERS, json={"email": email, "password": password, "email_confirm": True}
        )
        made.raise_for_status()
        print(f"Auth user {email}: created")


def mcp_command(url: str) -> str:
    """The command that adds Supabase's MCP server for the project, read-only."""
    ref = urlparse(url).netloc.split(".")[0]
    server = f"https://mcp.supabase.com/mcp?project_ref={ref}&read_only=true"
    return f'claude mcp add --transport http supabase "{server}"'


def run() -> None:
    """Step 1: the reviewers' Auth users, and the MCP server's command."""
    found = settings.required(
        settings.SUPABASE_URL, settings.SUPABASE_ADMIN_KEY, settings.REVIEWERS_SIGN_IN
    )
    url = found[settings.SUPABASE_URL]
    with admin(url, found[settings.SUPABASE_ADMIN_KEY]) as client:
        make_users(client, reviewer_emails(), found[settings.REVIEWERS_SIGN_IN])
    print("To point Claude Code's Supabase MCP server at the project, run:")
    print(f"  {mcp_command(url)}")
