"""The judge, Jev, grading a draft notice against the business's rubric."""

import json
import logging

import httpx
import pytest

from backend import judge
from backend.models import ExceptionAsRead, NoticeToGrade
from backend.tests.judging import POINTS, answer

NOTICE = NoticeToGrade(
    notice="Please pay Jorge Oliveira the $0.40 he was short on line 1.",
    exceptions=[
        ExceptionAsRead(
            rule="rate.base_short",
            worker="Jorge Oliveira",
            line_no=1,
            expected="$55.12 an hour",
            actual="$55.11 an hour",
            shortfall="$0.40",
            citation="MID-2025-11, Carpenter Journeyman, effective 2026-10-01",
        )
    ],
)


def test_the_request_carries_the_notice_its_exceptions_and_the_four_points(
    judge_answers,
):
    requests = []

    def keep(request):
        requests.append(request)
        return httpx.Response(200, json=answer())

    judge_answers(keep)
    grade = judge.grade(NOTICE)
    [request] = requests
    assert str(request.url) == "https://judge.test/api/alpha/decisions"
    body = json.loads(request.content)
    assert body["model"] == "typesafe/jev-1.13"
    assert body["state"] == NOTICE.model_dump()
    assert list(body["questions"]) == list(POINTS)
    assert all(q["type"] == "noul" for q in body["questions"].values())
    assert request.extensions["timeout"]["read"] == 10
    assert grade is not None
    assert (
        grade.covers_every_exception,
        grade.amounts_match,
        grade.plain_language,
        grade.no_legal_interpretation,
    ) == (0.9, 0.8, 0.7, 1.0)
    assert grade.score == pytest.approx(0.85)
    assert grade.cost == 0.00002


@pytest.mark.parametrize(
    "fails",
    [
        lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("Timed out")),
        lambda request: httpx.Response(500, json={"error": "Down"}),
        lambda request: httpx.Response(
            200,
            json=answer()
            | {"answers": {"covers_every_exception": {"type": "noul", "noul": 1}}},
        ),
    ],
    ids=["a timeout", "an error", "a point missing"],
)
def test_a_notice_the_judge_cant_grade_isnt_graded(judge_answers, caplog, fails):
    calls = []

    def once(request):
        calls.append(request)
        return fails(request)

    judge_answers(once)
    with caplog.at_level(logging.ERROR):
        assert judge.grade(NOTICE) is None
    assert len(calls) == 1
    assert "The judge couldn't grade the notice" in caplog.text
