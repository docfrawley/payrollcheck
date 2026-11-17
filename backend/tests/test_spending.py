"""A round's spending limit: its improver's calls and its evaluations' model calls,
an estimate before a version's evaluations, and no new case once the limit is
spent."""

import pytest

from backend.tests.case_requests import record_call, start
from backend.tests.copies_worked import FALSE, raise_these
from backend.tests.round_requests import (
    approved_change,
    create_round,
    improvement,
    improver_call,
    round_evaluation,
    round_path,
)
from backend.tests.run_requests import create_evaluation, finish, get_evaluation


def luna_at_two_tenths_of_a_cent_a_case(client):
    """A finished evaluation on GPT-6 Luna whose cases cost $0.002 each."""
    run = create_evaluation(client).json()
    for copy in run["cases"]:
        start(client, copy["case_id"])
        record_call(client, copy["case_id"], run["run_id"], cost=0.002)
    finish(client, run["run_id"])


def test_an_evaluation_the_round_cant_afford_is_refused(client):
    luna_at_two_tenths_of_a_cent_a_case(client)
    round_id = create_round(client).json()["round_id"]
    approved_change(client, round_id)
    improver_call(client, round_id, 4.90)

    refused = round_evaluation(client, round_id)
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        "The evaluations could cost about $0.81, and $0.10 of the round's limit "
        "is left",
    )
    verdict = client.post(f"{round_path(round_id)}/verdict").json()
    assert (verdict["verdict"], verdict["reason"]) == (
        "rolled_back",
        "the round couldn't afford to evaluate it",
    )


def test_a_model_with_no_runs_is_estimated_by_its_prices(client):
    luna_at_two_tenths_of_a_cent_a_case(client)
    round_id = create_round(client).json()["round_id"]
    approved_change(
        client,
        round_id,
        model="google/gemini-3.5-flash-lite",
        reasoning_effort="minimal",
    )
    improver_call(client, round_id, 1.50)
    refused = round_evaluation(client, round_id)
    # Five times Luna's cost a case, on the 403 cases of the three evaluations:
    # Gemini's output price is five times Luna's.
    assert refused.json()["detail"] == (
        "The evaluations could cost about $4.03, and $3.50 of the round's limit is left"
    )


def test_no_new_case_starts_once_the_limit_is_spent(client):
    round_id = create_round(client).json()["round_id"]
    approved_change(client, round_id)
    run = round_evaluation(client, round_id).json()
    first, second = (copy["case_id"] for copy in run["cases"][:2])
    start(client, first)
    improver_call(client, round_id, 3.00)
    record_call(client, first, run["run_id"], cost=2.00)

    refused = start(client, second)
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        "Round 1 has spent its limit of $5.00",
    )
    assert client.get(f"/api/cases/{second}").json()["status"] == "received"
    assert finish(client, run["run_id"]).json()["status"] == "stopped"
    assert get_evaluation(client, run["run_id"])["status"] == "stopped"
    verdict = client.post(f"{round_path(round_id)}/verdict").json()
    assert (verdict["verdict"], verdict["reason"]) == (
        "rolled_back",
        "its evaluations were stopped",
    )


def test_a_first_evaluation_cut_short_stops_the_round(client):
    round_id = create_round(client).json()["round_id"]
    run = round_evaluation(client, round_id).json()
    improver_call(client, round_id, 5.00)
    cut = finish(client, run["run_id"]).json()
    assert (cut["status"], cut["stopped_because"]) == (
        "stopped",
        "The spending limit cut short its first evaluations",
    )
    round_ = client.get(round_path(round_id)).json()
    assert round_["status"] == "stopped"
    [listed] = improvement(client)["rounds"]
    assert listed["stopped_because"] == (
        "The spending limit cut short its first evaluations"
    )
    assert (listed["cost"], listed["spending_limit"]) == (5.0, 5.0)


def test_a_rounds_spending_counts_the_judge(client):
    round_id = create_round(client).json()["round_id"]
    run = round_evaluation(client, round_id).json()
    first = run["cases"][0]["case_id"]
    raise_these(client, first, [FALSE])
    record_call(client, first, run["run_id"], cost=0.01)
    improver_call(client, round_id, 0.02)
    assert finish(client, run["run_id"]).json()["status"] == "finished"
    [listed] = improvement(client)["rounds"]
    # The improver's call, the copy's model call and the judge's grade of its notice.
    assert listed["cost"] == pytest.approx(0.02 + 0.01 + 0.00002)
