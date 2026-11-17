"""The success-criteria table the Copilot reports, every figure worked out in code:
criteria 1 to 4 from the current version's latest finished development-set
evaluation, 5 from our records, and 6 and 7 outside what it can check."""

from backend.database import cases
from backend.tests.case_requests import record_call, start
from backend.tests.copilot_reads import read
from backend.tests.rows import change
from backend.tests.run_requests import (
    create_evaluation,
    dispatch_of,
    fail_run,
    finish,
    get_evaluation,
)
from backend.tests.sign_in import DANA
from backend.tests.versions import add_version


def report(client):
    return read(client, "/success-criteria").json()


def test_with_no_evaluation_it_says_which_it_needs(dashboard):
    found = report(dashboard)
    assert found["evaluation"] is None
    assert found["needs"] == (
        "Criteria 1 to 4 need a finished evaluation of version 1 on the whole "
        "development set, 207 cases, whose cost can't be estimated until a run on "
        "its model has finished"
    )
    first_four = found["criteria"][:4]
    assert [c["number"] for c in first_four] == [1, 2, 3, 4]
    assert all(c["figure"] is None and c["met"] is None for c in first_four)


def test_the_evaluation_it_needs_is_estimated_from_a_finished_run(client, dashboard):
    run_id = dispatch_of(client, "PC-1201")
    start(client, "PC-1201")
    record_call(client, "PC-1201", run_id, cost=0.001)
    finish(client, run_id)
    assert report(dashboard)["needs"].endswith("207 cases, about $0.21 of model calls")


def test_criteria_1_to_4_are_the_evaluation_pages(client, dashboard):
    run_id = create_evaluation(client, "development").json()["run_id"]
    client.post(f"/api/runs/{run_id}/finish")
    # A later evaluation that stopped doesn't count.
    stopped = create_evaluation(client, "development").json()["run_id"]
    fail_run(client, stopped)
    page = get_evaluation(client, run_id)
    found = report(dashboard)
    assert found["evaluation"]["run_id"] == run_id
    assert found["needs"] is None
    assert [
        {"title": c["target"], "figure": c["figure"], "met": c["met"]}
        for c in found["criteria"][:4]
    ] == page["success_criteria"]
    assert {c["source"] for c in found["criteria"][:4]} == {
        f"Evaluation {page['number']}, of version 1 on the development set"
    }


def test_a_tiny_evaluation_doesnt_count(client, dashboard):
    run_id = create_evaluation(client, "tiny").json()["run_id"]
    client.post(f"/api/runs/{run_id}/finish")
    assert report(dashboard)["evaluation"] is None


def test_criterion_5_counts_the_accepted_cases_with_no_sign_off(dashboard):
    [fifth] = [c for c in report(dashboard)["criteria"] if c["number"] == 5]
    assert (fifth["figure"], fifth["met"]) == ("0 Accepted without a sign-off", True)
    change(cases, cases.c.case_id == "PC-0101", reviewed_by=None)
    [fifth] = [c for c in report(dashboard)["criteria"] if c["number"] == 5]
    assert (fifth["figure"], fifth["met"]) == ("1 Accepted without a sign-off", False)


def test_criteria_6_and_7_are_outside_what_it_can_check(dashboard):
    sixth, seventh = report(dashboard)["criteria"][5:]
    assert (sixth["number"], seventh["number"]) == (6, 7)
    for criterion in (sixth, seventh):
        assert criterion["met"] is None
        assert criterion["figure"] == "Outside what the Copilot can check of itself"
    assert "grading its own answers" in sixth["source"]


def test_an_older_versions_evaluation_doesnt_count(client, dashboard):
    run_id = create_evaluation(client, "development").json()["run_id"]
    client.post(f"/api/runs/{run_id}/finish")
    add_version("Version 2's instructions", verdict="kept")
    found = report(dashboard)
    assert (found["current_version"], found["evaluation"]) == (2, None)
    assert "version 2" in found["needs"]


def test_every_figure_is_in_the_answer(client, dashboard):
    run_id = create_evaluation(client, "development").json()["run_id"]
    client.post(f"/api/runs/{run_id}/finish")
    found = read(dashboard, "/success-criteria", DANA).json()
    assert [c["number"] for c in found["criteria"]] == [1, 2, 3, 4, 5, 6, 7]
    for criterion in found["criteria"][:5]:
        assert criterion["target"]
        assert criterion["figure"]
        assert isinstance(criterion["met"], bool)
    assert [c["met"] for c in found["criteria"][5:]] == [None, None]
