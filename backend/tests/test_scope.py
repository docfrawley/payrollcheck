"""Scope: every route that takes the id of a case, a project or a subcontractor
answers a reviewer outside its scope as if it didn't exist, every list holds only
what is in the caller's scope, the compliance manager sees every one of our
projects, and the agent's key sees everything. test_lifecycle.py has the key
refused Sign off and Send back."""

import re

import pytest
from fastapi import FastAPI
from sqlalchemy import insert

from backend.database import engine, project_reviewers
from backend.lookups import CASE_NOT_FOUND, PROJECT_NOT_FOUND
from backend.main import app
from backend.subcontractors import SUBCONTRACTOR_NOT_FOUND
from backend.tests.case_requests import awaiting_review
from backend.tests.gates import AGENT_OPERATIONS, REVIEWER_OPERATIONS
from backend.tests.run_requests import fail_run
from backend.tests.sign_in import DANA, MARCUS, PRIYA, signed_in

# The ids scope covers, each with one outside Priya's scope (on Marcus's Lincoln
# School renovation, or held out) and the not-found message of an id that doesn't
# exist. Every one of our subcontractors is on all three of our projects, so the
# one outside her scope is the held-out world's.
SCOPED = {
    "case_id": ("PC-1201", CASE_NOT_FOUND),
    "project_id": ("PRJ-01", PROJECT_NOT_FOUND),
    "subcontractor_id": ("SUB-51", SUBCONTRACTOR_NOT_FOUND),
}
# The ids that aren't of anything on a project, with why scope doesn't cover them.
UNSCOPED = {
    "exception_id": "An exception is found only on its own case, which is scoped",
    "run_id": "A run works the whole queue; its cases are filtered to the scope",
    "round_id": "The improver's rounds are the compliance manager's",
    "proposal_id": "The improver's proposals are the compliance manager's",
    "number": "A version or a recipe of the configuration, the same for everyone",
    "conversation_id": "A conversation is found for its own reviewer only",
    "turn_id": "A turn is found for its own reviewer only",
    "step_id": "A Copilot card is found for its own reviewer only",
}
IDS = re.compile(r"{(\w+)}")
# A well-formed value for each other id a scoped route takes, so the route is
# refused for its scoped id alone.
OTHER_IDS = {"exception_id": "1"}


def operations_with_ids(application: FastAPI) -> dict[str, tuple[str, str]]:
    """Every operation whose path takes an id, by its id: its method and path."""
    found = {}
    for path, methods in application.openapi()["paths"].items():
        for method, operation in methods.items():
            if IDS.search(path):
                found[operation["operationId"]] = (method.upper(), path)
    return found


def scoped_operations(application: FastAPI) -> dict[str, tuple[str, str]]:
    """The operations a reviewer may call that take a case, project or subcontractor
    id, refusing any id that is neither scoped nor listed as unscoped."""
    scoped = {}
    for operation_id, (method, path) in operations_with_ids(application).items():
        ids = set(IDS.findall(path))
        unlisted = ids - set(SCOPED) - set(UNSCOPED)
        assert not unlisted, f"{operation_id} takes {unlisted}: is it scoped?"
        if ids & set(SCOPED) and operation_id not in AGENT_OPERATIONS:
            scoped[operation_id] = (method, path)
    return scoped


def test_every_id_route_answers_an_id_outside_the_scope_as_not_found(client):
    awaiting_review(client, "PC-1201")
    operations = scoped_operations(app)
    assert set(operations) >= {"get_case", "sign_off_case", "upload_payroll"}
    for operation_id, (method, path) in operations.items():
        [scoped_id] = [name for name in IDS.findall(path) if name in SCOPED]
        outside, not_found = SCOPED[scoped_id]
        _, _, body = REVIEWER_OPERATIONS.get(operation_id, (method, path, None))
        answer = client.request(
            method,
            IDS.sub(
                lambda other: OTHER_IDS[other[1]],
                path.replace(f"{{{scoped_id}}}", outside),
            ),
            json=body,
            headers=signed_in(PRIYA),
        )
        assert (answer.status_code, answer.json()["detail"]) == (
            404,
            not_found.format(**{scoped_id: outside}),
        ), operation_id


def test_a_new_route_with_an_id_nobody_listed_fails_the_test():
    throwaway = FastAPI()

    @throwaway.get("/api/things/{thing_id}", operation_id="get_thing")
    def get_thing(thing_id: str) -> str:
        """Get a thing."""
        return thing_id

    with pytest.raises(AssertionError, match="get_thing takes {'thing_id'}"):
        scoped_operations(throwaway)


def test_the_queue_holds_the_cases_in_the_scope(client):
    def projects_of(headers):
        listed = client.get("/api/cases", headers=headers).json()
        return {case["project_id"] for case in listed}, len(listed)

    assert projects_of(signed_in(MARCUS))[0] == {"PRJ-01", "PRJ-02"}
    assert projects_of(signed_in(PRIYA))[0] == {"PRJ-03"}
    assert projects_of(signed_in(DANA)) == ({"PRJ-01", "PRJ-02", "PRJ-03"}, 207)
    assert projects_of({}) == ({"PRJ-01", "PRJ-02", "PRJ-03"}, 207)


def test_the_projects_and_subcontractors_hold_what_is_in_the_scope(client):
    projects = client.get("/api/projects", headers=signed_in(PRIYA)).json()
    assert [project["project_id"] for project in projects] == ["PRJ-03"]
    dana = client.get("/api/projects", headers=signed_in(DANA)).json()
    assert [project["project_id"] for project in dana] == ["PRJ-01", "PRJ-02", "PRJ-03"]
    # Every one of our subcontractors is on all three projects, and the held-out
    # world's on none of them.
    found = client.get("/api/subcontractors?name=e", headers=signed_in(PRIYA)).json()
    ids = {match["subcontractor_id"] for match in found}
    assert ids <= {f"SUB-0{n}" for n in range(1, 9)}
    assert ids
    sub = client.get("/api/subcontractors/SUB-01", headers=signed_in(PRIYA)).json()
    assert [project["project_id"] for project in sub["projects"]] == ["PRJ-03"]
    assert {case["project_id"] for case in sub["cases"]} == {"PRJ-03"}
    engaged = client.get(
        "/api/projects/PRJ-03/subcontractors", headers=signed_in(PRIYA)
    )
    assert engaged.status_code == 200


def test_an_upload_to_a_project_outside_the_scope_is_not_found(client):
    upload = client.post(
        "/api/projects/PRJ-01/payrolls",
        json={"subcontractor_id": "SUB-01", "file_name": "p.csv", "content": ""},
        headers=signed_in(PRIYA),
    )
    assert (upload.status_code, upload.json()["detail"]) == (
        404,
        "Project PRJ-01 not found",
    )


def copies_of(client, evaluation_set):
    """Start an evaluation of a set and stop it, and return its copies."""
    started = client.post(
        "/api/evaluations",
        json={"evaluation_set": evaluation_set, "agents": 5},
        headers=signed_in(DANA),
    ).json()
    run = client.get(f"/api/runs/{started['run_id']}").json()
    fail_run(client, run["run_id"])
    return run["cases"]


def test_every_reviewer_opens_an_evaluations_copies_kept_out_of_the_queue(
    client, agent_calls
):
    found = copies_of(client, "tiny") + copies_of(client, "held_out")
    projects = {case["project_id"] for case in found}
    assert "PRJ-01" in projects
    assert {"PRJ-51", "PRJ-52", "PRJ-53"} & projects
    copies = [case["case_id"] for case in found]
    for copy_id in copies:
        opened = client.get(f"/api/cases/{copy_id}", headers=signed_in(PRIYA))
        assert opened.status_code == 200
    queue = {
        c["case_id"] for c in client.get("/api/cases", headers=signed_in(PRIYA)).json()
    }
    assert queue.isdisjoint(copies)


def test_the_agents_key_reads_any_project_held_out_ones_too(client):
    for path in [
        "/api/cases/PC-1201",
        "/api/cases/PC-1217",
        "/api/cases/PC-1201/history",
        "/api/projects/PRJ-51",
        "/api/projects/PRJ-51/subcontractors",
    ]:
        assert client.get(path).status_code == 200, path


def test_a_held_out_project_assigned_to_a_reviewer_is_still_outside_their_scope(
    client,
):
    with engine().begin() as db:
        db.execute(
            insert(project_reviewers).values(reviewer_id="HND-03", project_id="PRJ-51")
        )
    refused = client.get("/api/projects/PRJ-51", headers=signed_in(PRIYA))
    assert (refused.status_code, refused.json()["detail"]) == (
        404,
        "Project PRJ-51 not found",
    )
    listed = client.get("/api/projects", headers=signed_in(PRIYA)).json()
    assert [project["project_id"] for project in listed] == ["PRJ-03"]
