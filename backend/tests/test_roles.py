"""The two roles: what only the compliance manager may do or see, what every reviewer
sees, and who reviews which project."""

import pytest
from sqlalchemy import select

from backend.database import engine, project_reviewers, reviewers
from backend.tests.round_requests import ROUNDS
from backend.tests.settings_requests import STARTING
from backend.tests.sign_in import DANA, MARCUS, PRIYA, signed_in

ROUND = f"{ROUNDS}/round-1"
PROPOSAL = f"{ROUND}/proposals/proposal-1"

# What only the compliance manager may do or see, with the action each 403 names.
COMPLIANCE_MANAGERS = {
    "start_round": ("POST", ROUNDS, None, "start a round"),
    "stop_round": ("POST", f"{ROUND}/stop", None, "stop a round"),
    "approve_proposal": (
        "POST",
        f"{PROPOSAL}/approval",
        None,
        "approve or reject the improver's proposals",
    ),
    "reject_proposal": (
        "POST",
        f"{PROPOSAL}/rejection",
        {"reason": "No"},
        "approve or reject the improver's proposals",
    ),
    "change_settings": ("PUT", "/api/settings", STARTING, "change the settings"),
    "get_improvement": (
        "GET",
        "/api/improvement",
        None,
        "see the improver's rounds and recipes",
    ),
    "get_recipe": (
        "GET",
        "/api/improvement/recipes/1",
        None,
        "see the improver's rounds and recipes",
    ),
    "get_settings": ("GET", "/api/settings", None, "see the settings"),
}
# What every reviewer reads.
EVERYONES = ["/api/evaluations", "/api/configuration"]
NAMES = {MARCUS: "Marcus Oyelaran", PRIYA: "Priya Raman"}


def test_seeding_assigns_each_reviewer_their_projects():
    with engine().connect() as db:
        rows = db.execute(
            select(project_reviewers).order_by(
                project_reviewers.c.reviewer_id, project_reviewers.c.project_id
            )
        )
        assigned = [(row.reviewer_id, row.project_id) for row in rows]
        columns = set(reviewers.c.keys())
    assert assigned == [
        ("HND-01", "PRJ-01"),
        ("HND-01", "PRJ-02"),
        ("HND-01", "PRJ-03"),
        ("HND-02", "PRJ-01"),
        ("HND-02", "PRJ-02"),
        ("HND-03", "PRJ-03"),
    ]
    assert columns == {"reviewer_id", "name", "role", "email"}


@pytest.mark.parametrize("email", [MARCUS, PRIYA])
@pytest.mark.parametrize(
    "operation", COMPLIANCE_MANAGERS.values(), ids=COMPLIANCE_MANAGERS.keys()
)
def test_a_reviewer_is_refused_what_only_the_compliance_manager_may_do(
    client, agent_calls, email, operation
):
    method, path, body, action = operation
    refused = client.request(method, path, json=body, headers=signed_in(email))
    assert (refused.status_code, refused.json()["detail"]) == (
        403,
        f"Only the compliance manager can {action}. {NAMES[email]} can't.",
    )
    assert agent_calls == []


def test_the_compliance_manager_sees_and_changes_the_settings_and_starts_a_round(
    client,
):
    """test_rounds.py has her reviews and stops."""
    for path in ["/api/improvement", "/api/improvement/recipes/1", "/api/settings"]:
        assert client.get(path, headers=signed_in(DANA)).status_code == 200
    changed = client.put("/api/settings", json=STARTING, headers=signed_in(DANA))
    assert changed.status_code == 200
    started = client.post(ROUNDS, headers=signed_in(DANA))
    assert started.status_code == 202


@pytest.mark.parametrize("email", [DANA, MARCUS, PRIYA])
def test_every_reviewer_reads_the_scoreboard_and_the_configuration(
    client, agent_calls, email
):
    started = client.post(
        "/api/evaluations",
        json={"evaluation_set": "tiny", "agents": 5},
        headers=signed_in(DANA),
    )
    evaluation = f"/api/evaluations/{started.json()['run_id']}"
    for path in [*EVERYONES, evaluation]:
        assert client.get(path, headers=signed_in(email)).status_code == 200, path
