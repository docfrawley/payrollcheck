"""The judge's grades of an evaluation's draft notices, as it finishes: each copy
with an exception open graded at once, one with no draft scored 0, one the judge
can't grade left out, and nothing graded on a free model or a run that isn't a
whole finished evaluation."""

import json
import threading

import httpx
import pytest
from sqlalchemy import select, update

from backend.database import engine, notice_grades, notices, runs
from backend.tests.copies_worked import FALSE, raise_these
from backend.tests.judging import answer
from backend.tests.round_requests import (
    approved_change,
    create_round,
    improver_call,
    round_evaluation,
)
from backend.tests.run_requests import (
    create_evaluation,
    dispatch_of,
    finish,
    get_evaluation,
)


def three_copies(client):
    """A tiny evaluation whose first two copies raise an exception, each with its
    own notice, and whose third raises nothing."""
    run = create_evaluation(client).json()
    first, second, clean = (c["case_id"] for c in run["cases"][:3])
    raise_these(client, first, [FALSE], notice=f"Notice for {first}")
    raise_these(client, second, [FALSE], notice=f"Notice for {second}")
    raise_these(client, clean, [])
    return run["run_id"], first, second, clean


def grades():
    with engine().connect() as db:
        rows = db.execute(select(notice_grades)).mappings()
        return {row["case_id"]: dict(row) for row in rows}


def notice_of(request):
    return json.loads(request.content)["state"]["notice"]


def test_each_copy_with_an_exception_open_is_graded_at_once(client, judge_answers):
    both_asking = threading.Barrier(2, timeout=5)
    asked = []

    def at_once(request):
        both_asking.wait()
        asked.append(json.loads(request.content)["state"])
        return httpx.Response(200, json=answer())

    judge_answers(at_once)
    run_id, first, second, clean = three_copies(client)
    finish(client, run_id)

    assert sorted(state["notice"] for state in asked) == [
        f"Notice for {first}",
        f"Notice for {second}",
    ]
    [exception] = asked[0]["exceptions"]
    assert (exception["rule"], exception["actual"]) == (
        "form.missing_field",
        "Blank: fein",
    )
    found = grades()
    assert set(found) == {first, second}
    assert found[first]["result"] == "graded"
    assert found[first]["score"] == pytest.approx(0.85)
    assert found[first]["covers_every_exception"] == 0.9
    by_copy = {c["case_id"]: c for c in get_evaluation(client, run_id)["cases"]}
    assert by_copy[clean]["notice"] is None
    assert by_copy[first]["notice"]["amounts_match"] == 0.8


def test_a_copy_with_an_exception_and_no_draft_scores_zero(client, judged):
    run_id, first, second, _ = three_copies(client)
    with engine().begin() as db:
        db.execute(update(notices).where(notices.c.case_id == first).values(draft=None))
    finish(client, run_id)

    assert [state["state"]["notice"] for state in judged] == [f"Notice for {second}"]
    found = grades()
    assert (found[first]["result"], found[first]["score"]) == ("no_notice", 0)
    measures = get_evaluation(client, run_id)["measures"]
    assert measures["notices_graded"] == 2
    assert measures["notice_score"] == pytest.approx(0.85 / 2)


def test_a_notice_the_judge_cant_grade_is_left_out_of_the_score(client, judge_answers):
    run_id, first, second, _ = three_copies(client)
    judge_answers(
        lambda request: (
            httpx.Response(500, json={"error": "Down"})
            if notice_of(request) == f"Notice for {first}"
            else httpx.Response(200, json=answer(plain=0.3))
        )
    )
    finish(client, run_id)

    found = grades()
    assert (found[first]["result"], found[first]["score"]) == ("not_graded", None)
    measures = get_evaluation(client, run_id)["measures"]
    assert measures["notices_graded"] == 1
    assert measures["notice_score"] == pytest.approx((0.9 + 0.8 + 0.3 + 1.0) / 4)


def test_on_a_free_model_the_judge_isnt_called(client, judged, monkeypatch):
    run_id, *_ = three_copies(client)
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    finish(client, run_id)
    assert (judged, grades()) == ([], {})
    measures = get_evaluation(client, run_id)["measures"]
    assert (measures["notice_score"], measures["notices_graded"]) == (None, 0)


def test_a_dispatch_grades_nothing(client, judged):
    run_id = dispatch_of(client, "PC-1201")
    raise_these(client, "PC-1201", [FALSE], notice="Please correct it.")
    assert finish(client, run_id).json()["status"] == "finished"
    assert (judged, grades()) == ([], {})


def test_an_evaluation_the_spending_limit_cut_short_grades_nothing(client, judged):
    round_id = create_round(client).json()["round_id"]
    approved_change(client, round_id)
    run = round_evaluation(client, round_id).json()
    raise_these(client, run["cases"][0]["case_id"], [FALSE])
    improver_call(client, round_id, 5.00)
    cut = finish(client, run["run_id"]).json()
    assert (cut["status"], cut["stopped_because"]) == (
        "stopped",
        "Round 1 has spent its limit of $5.00",
    )
    assert (judged, grades()) == ([], {})


def test_an_evaluation_stopped_while_the_judge_grades_keeps_no_grades(
    client, judge_answers
):
    run_id, *_ = three_copies(client)

    def stopped_meanwhile(request):
        with engine().begin() as db:
            db.execute(
                update(runs).where(runs.c.run_id == run_id).values(status="stopped")
            )
        return httpx.Response(200, json=answer())

    judge_answers(stopped_meanwhile)
    assert finish(client, run_id).json()["status"] == "stopped"
    assert grades() == {}
