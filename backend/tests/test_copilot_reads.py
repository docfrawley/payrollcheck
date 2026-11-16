"""The app's reads the Copilot uses with the reviewer's sign-in: finding
subcontractors by legal name and reading one with its record, projects and cases,
the run a start names, and the Copilot's model."""

import json

from backend.tests.dashboard_reads import read
from backend.tests.run_requests import start_dispatch
from backend.tests.sign_in import DANA


def test_find_subcontractors_by_the_words_in_their_legal_name(dashboard):
    found = read(dashboard, "/api/subcontractors?name=garden").json()
    assert found == [
        {"subcontractor_id": "SUB-01", "legal_name": "Garden State Electric LLC"}
    ]
    words = read(dashboard, "/api/subcontractors?name=ELECTRIC%20garden").json()
    assert words == found
    assert read(dashboard, "/api/subcontractors?name=nobody").json() == []


def test_a_blank_name_finds_nothing(dashboard):
    for name in ("", "%20%20"):
        assert read(dashboard, f"/api/subcontractors?name={name}").status_code == 422
    assert read(dashboard, "/api/subcontractors").status_code == 422


def test_a_subcontractor_with_its_projects_and_cases(dashboard):
    subcontractor = read(dashboard, "/api/subcontractors/SUB-01").json()
    assert subcontractor["legal_name"] == "Garden State Electric LLC"
    assert subcontractor["registration_no"] == "177511"
    assert [p["project_id"] for p in subcontractor["projects"]] == [
        "PRJ-01",
        "PRJ-02",
        "PRJ-03",
    ]
    assert "PC-0101" in [c["case_id"] for c in subcontractor["cases"]]
    assert "payroll@gardenstateelectric.example" not in json.dumps(subcontractor)
    unknown = read(dashboard, "/api/subcontractors/SUB-99")
    assert (unknown.status_code, unknown.json()["detail"]) == (
        404,
        "Subcontractor SUB-99 not found",
    )


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
