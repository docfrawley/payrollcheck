"""The Copilot's reads, as Marcus Oyelaran, hold only his projects: the road
resurfacing isn't found, and every read across all projects holds only the
Lincoln School renovation's and the municipal building's cases. The agent's key
reads none of them."""

from fastapi.routing import APIRoute

from backend.copilot_reads import router
from backend.dependencies import THE_AGENTS_REQUEST
from backend.lookups import PROJECT_NOT_FOUND
from backend.tests.copilot_reads import (
    LAST_FOUR_WEEKS,
    classification_changes,
    exposure,
    filings,
    find_cases,
    read,
)
from backend.tests.sign_in import MARCUS, token

MARCUS_PROJECTS = {"PRJ-01", "PRJ-02"}


def test_the_road_resurfacing_isnt_found(dashboard):
    assert read(dashboard, "/projects?name=road").json() == []
    assert [
        p["project_id"] for p in read(dashboard, "/projects?name=school").json()
    ] == ["PRJ-01"]
    refused = exposure(dashboard, project_id="PRJ-03")
    assert (refused.status_code, refused.json()["detail"]) == (
        404,
        PROJECT_NOT_FOUND.format(project_id="PRJ-03"),
    )
    assert filings(dashboard, LAST_FOUR_WEEKS, project_id="PRJ-03").status_code == 404
    assert find_cases(dashboard, subcontractor_id="SUB-51").status_code == 404
    assert read(dashboard, "/cases/PC-0123/exceptions").status_code == 404


def test_every_read_across_all_projects_holds_only_his(dashboard):
    cases = find_cases(dashboard).json()["cases"]
    assert {c["project_id"] for c in cases} == MARCUS_PROJECTS
    exposed = exposure(dashboard).json()["exceptions"]
    assert exposed
    assert {c["case_id"] for c in exposed} <= {c["case_id"] for c in cases}
    found = filings(dashboard, LAST_FOUR_WEEKS).json()
    assert {f["project_id"] for f in found["late"] + found["missing"]} <= (
        MARCUS_PROJECTS
    )
    on_time = set(found["on_time"])
    assert on_time
    assert on_time <= {c["case_id"] for c in cases}
    changed = classification_changes(dashboard, LAST_FOUR_WEEKS).json()["changes"]
    assert {c["project_id"] for c in changed} <= MARCUS_PROJECTS


def test_the_agents_key_is_refused_every_read(client):
    # The client sends the agent's key, beside Marcus's sign-in.
    sign_in = {"Authorization": f"Bearer {token(MARCUS)}"}
    reads = [
        (method, route.path)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods or ()
    ]
    assert len(reads) == 8
    for method, path in reads:
        filled = path.replace("{case_id}", "PC-0311")
        answer = client.request(method, filled, headers=sign_in)
        assert answer.status_code == 403, (method, path)
        assert answer.json()["detail"] == THE_AGENTS_REQUEST
