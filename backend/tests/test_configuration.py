"""The payroll agent's configuration in versions."""

import pytest
from sqlalchemy import select

from backend.database import engine, versions
from backend.first_version import INSTRUCTIONS
from backend.seeding import seed
from backend.tests.dashboard_reads import (
    configuration,
    evaluations,
    read,
    version_details,
)
from backend.tests.round_requests import create_round, into_round, work_copies
from backend.tests.run_requests import (
    create_dispatch,
    create_evaluation,
    fail_run,
    finish,
    get_evaluation,
    latest_dispatch,
)
from backend.tests.versions import add_version

PAYROLL_MD = (INSTRUCTIONS / "payroll.md").read_text(encoding="utf-8")


def version_1():
    with engine().connect() as db:
        query = select(versions).where(versions.c.number == 1)
        return db.execute(query).mappings().one()


def test_version_1_is_the_payroll_agent_as_it_was():
    row = version_1()
    assert row["instructions"] == PAYROLL_MD
    assert (row["model"], row["reasoning_effort"]) == ("openai/gpt-6-luna", "none")
    assert (row["proposed_by"], row["approved_by"]) == ("The compliance team", None)
    assert row["parameters"] == {"rounding_tolerance_cents": 0}
    assert row["based_on"] is None


def test_version_1_is_the_free_model_for_students_on_free_models(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    seed(engine())
    row = version_1()
    assert (row["model"], row["reasoning_effort"]) == ("openrouter/free", "default")


def test_the_payroll_agent_reads_a_version_with_its_parameters(client):
    for path in ("/api/versions/current", "/api/versions/1"):
        version = client.get(path).json()
        assert list(version) == [
            "number",
            "instructions",
            "model",
            "reasoning_effort",
            "parameters",
        ]
        assert version["number"] == 1
        assert version["instructions"] == PAYROLL_MD
        assert version["parameters"] == {"rounding_tolerance_cents": 0}
        assert (version["model"], version["reasoning_effort"]) == (
            "openai/gpt-6-luna",
            "none",
        )
    missing = client.get("/api/versions/9")
    assert (missing.status_code, missing.json()["detail"]) == (
        404,
        "Version 9 not found",
    )


TOLERANCE = {
    "name": "rounding_tolerance_cents",
    "label": "Rounding tolerance",
    "unit": "cents",
}


def test_each_version_gives_its_parameters_and_what_it_changed_of_them(client):
    add_version(
        PAYROLL_MD,
        parameters={"rounding_tolerance_cents": 50},
        motivating_cases=["PC-0311", "PC-1210"],
    )
    two, one = configuration(client)["versions"]
    assert one["parameters"] == [TOLERANCE | {"value": 0}]
    assert (one["parameter_changes"], one["motivating_cases"]) == ([], [])
    assert two["parameters"] == [TOLERANCE | {"value": 50}]
    assert two["parameter_changes"] == [TOLERANCE | {"before": 0, "after": 50}]
    assert two["motivating_cases"] == ["PC-0311", "PC-1210"]
    details = version_details(client, 2)
    assert details["parameter_changes"] == two["parameter_changes"]
    assert details["motivating_cases"] == ["PC-0311", "PC-1210"]
    assert version_details(client, 1)["parameter_changes"] == []


def test_the_payroll_agent_reads_no_motivating_cases(client):
    add_version(PAYROLL_MD, motivating_cases=["PC-0311"], verdict="kept")
    version = client.get("/api/versions/2").json()
    assert "motivating_cases" not in version
    assert "scores" not in version


def test_the_current_version_is_the_newest_kept(client):
    add_version(PAYROLL_MD + "\nA rule for baggage.\n", verdict="kept")
    add_version(PAYROLL_MD + "\nAnother rule.\n", based_on=2)
    assert client.get("/api/versions/current").json()["number"] == 2

    page = configuration(client)
    assert page["current"] == 2
    listed = [
        (v["number"], v["status"], v["lines_added"], v["lines_removed"])
        for v in page["versions"]
    ]
    assert listed == [(3, "under_test", 1, 1), (2, "current", 2, 0), (1, "kept", 0, 0)]
    two = page["versions"][1]
    assert (two["model_before"], two["model"]) == (
        "openai/gpt-6-luna",
        "google/gemini-3.5-flash-lite",
    )
    assert two["scores"] == {"development": None, "held_out": None}


def test_a_rolled_back_version_leaves_the_current_one(client):
    add_version(PAYROLL_MD + "\nA rule.\n", verdict="rolled_back")
    assert client.get("/api/versions/current").json()["number"] == 1
    statuses = [v["status"] for v in configuration(client)["versions"]]
    assert statuses == ["rolled_back", "current"]


def test_a_versions_details_hold_its_diff(client):
    add_version(
        PAYROLL_MD.replace("You are the PayrollCheck", "You are PayrollCheck's", 1)
    )
    details = version_details(client, 2)
    assert details["based_on"] == 1
    assert details["instructions"].startswith("You are PayrollCheck's payroll agent")
    assert (details["diff"]["added"], details["diff"]["removed"]) == (1, 1)
    [hunk] = details["diff"]["hunks"]
    assert [line["kind"] for line in hunk[:2]] == ["removed", "added"]
    first = version_details(client, 1)
    assert (first["diff"], first["status"]) == (None, "current")
    assert read(client, "/api/configuration/versions/9").status_code == 404


def test_runs_record_the_current_version(client):
    add_version("New instructions", verdict="kept")
    dispatch = create_dispatch(client).json()
    finish(client, dispatch["run_id"])
    evaluation = create_evaluation(client).json()
    for run in (dispatch, evaluation):
        assert (run["version"], run["round_id"]) == (2, None)
        assert (run["model"], run["reasoning_effort"]) == (
            "google/gemini-3.5-flash-lite",
            "minimal",
        )
    assert latest_dispatch(client)["version"] == 2
    assert evaluations(client)[0]["version"] == 2
    assert get_evaluation(client, evaluation["run_id"])["version"] == 2


def test_a_version_after_one_rolled_back_changes_the_current_one(client):
    add_version(PAYROLL_MD + "\nA rule for baggage.\n", verdict="kept")
    add_version(
        PAYROLL_MD + "\nA rule that failed.\n", verdict="rolled_back", based_on=2
    )
    add_version(
        PAYROLL_MD + "\nA rule for baggage.\nAnother rule.\n",
        model="openai/gpt-6-luna",
        reasoning_effort="medium",
        based_on=2,
    )
    four = version_details(client, 4)
    assert (four["based_on"], four["lines_added"], four["lines_removed"]) == (2, 1, 0)
    assert (four["model_before"], four["reasoning_effort_before"]) == (
        "google/gemini-3.5-flash-lite",
        "minimal",
    )
    [hunk] = four["diff"]["hunks"]
    assert [line["kind"] for line in hunk] == ["context", "context", "added"]


def worked_evaluation(client, evaluation_set="held_out", caught=0):
    """Start an evaluation, work its copies with `caught` of them caught, and
    finish it."""
    evaluation = create_evaluation(client, evaluation_set).json()
    work_copies(client, evaluation, caught)
    finish(client, evaluation["run_id"])
    return evaluation


def in_a_round(client, *evaluations):
    """Make evaluations a new round's, as if it had run them."""
    into_round(create_round(client).json()["round_id"], *evaluations)


def test_a_versions_scores_average_the_whole_set_evaluations_its_rounds_ran(client):
    first = worked_evaluation(client, caught=0)
    second = worked_evaluation(client, caught=5)
    tiny = worked_evaluation(client, "tiny", caught=10)
    stopped = create_evaluation(client, "held_out").json()
    fail_run(client, stopped["run_id"])
    in_a_round(client, first, second, tiny, stopped)

    rates = [
        get_evaluation(client, e["run_id"])["measures"]["catch_rate"]
        for e in (first, second)
    ]
    assert rates[0] < rates[1]
    scores = configuration(client)["versions"][0]["scores"]
    assert scores["development"] is None
    assert scores["held_out"]["catch_rate"] == pytest.approx(sum(rates) / 2)


def test_a_run_with_no_money_caught_leaves_the_shortfall_accuracy_to_the_others(
    client,
):
    none_caught = worked_evaluation(client, caught=0)
    all_caught = worked_evaluation(client, caught=100)
    in_a_round(client, none_caught, all_caught)
    measures = get_evaluation(client, none_caught["run_id"])["measures"]
    assert measures["shortfall_accuracy"] is None
    held_out = configuration(client)["versions"][0]["scores"]["held_out"]
    assert held_out["shortfall_accuracy"] == 1.0


def test_the_check_runs_on_gpt_6_luna_with_no_reasoning(client, dashboard):
    assert client.get("/api/screening").json() == {
        "model": "openai/gpt-6-luna",
        "reasoning_effort": "none",
    }
    assert dashboard.get("/api/screening").status_code == 401


def test_the_check_runs_on_the_free_model_at_its_default(client, monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert client.get("/api/screening").json() == {
        "model": "openrouter/free",
        "reasoning_effort": "default",
    }


def test_no_version_changes_the_checks_model(client):
    add_version("Version 2's instructions", model="openai/gpt-6.1-sol", verdict="kept")
    assert client.get("/api/versions/current").json()["model"] == "openai/gpt-6.1-sol"
    assert client.get("/api/screening").json()["model"] == "openai/gpt-6-luna"
