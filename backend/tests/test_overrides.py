"""Overrides: a reviewer dismisses, restores or adds an exception on a case awaiting
review, each logged with who, when and why and never edited or deleted, refused
with its reason when it doesn't fit, and never touching the labels; and Sign off
only once nothing is open."""

import ast
import threading
from pathlib import Path

import pytest
from sqlalchemy import insert, select, update

from backend import main
from backend.database import cases, engine, labels, overrides, submissions
from backend.dependencies import API_KEY_HEADER
from backend.main import app
from backend.overrides import overrides_between
from backend.tests.case_requests import (
    awaiting_review,
    fail,
    finding,
    flag,
    sign_off,
    start,
)
from backend.tests.rows import committed_case, count, everything_recorded
from backend.tests.sign_in import MARCUS, PRIYA, signed_in

CASE = "PC-1201"
BACKEND = Path(__file__).parent.parent
MISSED = {
    "rule": "rate.fringe_short",
    "worker_id": "W-001",
    "line_no": 1,
    "expected": "$35.40/h",
    "actual": "$35.00/h",
    "shortfall_cents": 1900,
    "reason": "The fringe was paid short on line 1",
}


def path(case_id=CASE, *rest):
    return "/".join([f"/api/cases/{case_id}/exceptions", *map(str, rest)])


def dismiss(client, exception_id, reason="A false positive", email=MARCUS):
    return client.post(
        path(CASE, exception_id, "dismissal"),
        json={"reason": reason},
        headers=signed_in(email),
    )


def restore(client, exception_id, reason="Dismissed by mistake", email=MARCUS):
    return client.post(
        path(CASE, exception_id, "restoration"),
        json={"reason": reason},
        headers=signed_in(email),
    )


def add(client, email=MARCUS, case_id=CASE, **changes):
    return client.post(path(case_id), json=MISSED | changes, headers=signed_in(email))


def the_exception(client):
    """The case awaiting review with one exception, a base rate short, and its id."""
    case = awaiting_review(client, CASE, finding())
    [exception] = case["exceptions"]
    return exception["exception_id"]


def refusal(response):
    return response.status_code, response.json()["detail"]


def test_a_dismissal_an_addition_and_a_restoring_are_each_logged(client):
    exception_id = the_exception(client)
    dismissed = dismiss(client, exception_id).json()
    assert [e["status"] for e in dismissed["exceptions"]] == ["dismissed"]
    restored = restore(client, exception_id).json()
    assert [e["status"] for e in restored["exceptions"]] == ["open"]
    case = add(client).json()
    added = case["exceptions"][-1]
    assert (added["rule"], added["source"], added["raised_by"], added["status"]) == (
        "rate.fringe_short",
        "reviewer",
        "Marcus Oyelaran",
        "open",
    )
    assert (added["severity"], added["shortfall_cents"]) == ("high", 1900)
    assert added["citation"].startswith("The rate determination")
    log = [
        (o["exception_id"], o["kind"], o["reviewer_name"], o["reason"])
        for o in case["overrides"]
    ]
    assert log == [
        (exception_id, "dismissed", "Marcus Oyelaran", "A false positive"),
        (exception_id, "restored", "Marcus Oyelaran", "Dismissed by mistake"),
        (added["exception_id"], "added", "Marcus Oyelaran", MISSED["reason"]),
    ]
    assert all(o["created_at"] and o["submission_no"] == 1 for o in case["overrides"])


def test_nothing_edits_or_deletes_an_override():
    """No module of the backend updates or deletes the override log's rows, and its
    routes only add to it."""
    for module in BACKEND.glob("*.py"):
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"update", "delete"}
            ):
                [table] = node.args
                assert not (isinstance(table, ast.Name) and table.id == "overrides")
    # The override routes are a case's; the Copilot's read of a case's open
    # exceptions overrides nothing.
    for route_path, methods in app.openapi()["paths"].items():
        if route_path.startswith("/api/cases/") and "exceptions" in route_path:
            assert set(methods) <= {"post"}, route_path


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {"worker_id": None, "line_no": None},
            "rate.fringe_short is found on a worker's line: give the worker and "
            "the line",
        ),
        ({"line_no": 2}, "Line 2 of the latest submission isn't W-001's"),
        ({"line_no": 99}, "Line 99 of the latest submission isn't W-001's"),
        (
            {"rule": "sequence.gap", "shortfall_cents": None},
            "sequence.gap is about the whole payroll: give no worker or line",
        ),
        (
            {"shortfall_cents": None},
            "rate.fringe_short carries money: give a shortfall above $0.00",
        ),
        (
            {"shortfall_cents": 0},
            "rate.fringe_short carries money: give a shortfall above $0.00",
        ),
        (
            {"rule": "arithmetic.hours_total"},
            "arithmetic.hours_total carries no money: give no shortfall",
        ),
    ],
)
def test_an_addition_that_doesnt_fit_its_rule_is_refused(client, changes, message):
    the_exception(client)
    before = everything_recorded()
    assert refusal(add(client, **changes)) == (422, message)
    assert everything_recorded() == before


def test_a_blank_reason_and_a_rule_outside_the_catalogue_are_refused(client):
    exception_id = the_exception(client)
    assert dismiss(client, exception_id, reason="  ").status_code == 422
    assert add(client, reason="").status_code == 422
    assert add(client, rule="rate.vibes").status_code == 422
    assert count(overrides) == 0


def override(client, how, case_id, exception_id=1):
    """Override an exception of a case one of the three ways, as Marcus."""
    requests = {
        "dismiss": (path(case_id, exception_id, "dismissal"), {"reason": "No"}),
        "restore": (path(case_id, exception_id, "restoration"), {"reason": "No"}),
        "add": (path(case_id), MISSED),
    }
    request_path, body = requests[how]
    return client.post(request_path, json=body, headers=signed_in(MARCUS))


@pytest.mark.parametrize("how", ["dismiss", "restore", "add"])
def test_an_override_on_a_case_not_awaiting_review_or_on_a_copy_is_refused(
    client, agent_calls, how
):
    assert refusal(override(client, how, "PC-1202")) == (
        409,
        "Case PC-1202 is not awaiting review",
    )
    started = client.post(
        "/api/evaluations",
        json={"evaluation_set": "tiny", "agents": 5},
        headers=signed_in(),
    ).json()
    [copy, *_] = client.get(f"/api/runs/{started['run_id']}").json()["cases"]
    awaiting_review(client, copy["case_id"])
    assert refusal(override(client, how, copy["case_id"])) == (
        409,
        f"Case {copy['case_id']} is a copy in an evaluation and can't be overridden",
    )
    assert count(overrides) == 0


def test_an_addition_after_a_sign_off_it_read_too_soon_is_refused(
    dashboard, client, monkeypatch
):
    """The hold alone, with the case as an addition read it before a sign-off
    moved it on: the addition adds nothing to the Accepted case."""
    case = awaiting_review(client, CASE)
    as_read = committed_case(CASE)
    assert sign_off(dashboard, CASE, MARCUS).status_code == 200
    monkeypatch.setattr(main, "find_case", lambda db, case_id, scope: as_read)
    assert refusal(add(client)) == (409, f"Case {CASE} is not awaiting review")
    assert client.get(f"/api/cases/{CASE}").json()["exceptions"] == case["exceptions"]
    assert count(overrides) == 0


def test_two_dismissals_at_the_same_moment_record_one(client):
    exception_id = the_exception(client)
    together = threading.Barrier(2)
    answers = []

    def send():
        together.wait()
        answers.append(dismiss(client, exception_id).status_code)

    sending = [threading.Thread(target=send) for _ in range(2)]
    for thread in sending:
        thread.start()
    for thread in sending:
        thread.join(10)
    assert sorted(answers) == [200, 409]
    assert count(overrides) == 1


def test_an_exception_of_an_earlier_submission_isnt_overridden(client):
    exception_id = the_exception(client)
    with engine().begin() as db:
        first = (
            db.execute(select(submissions).where(submissions.c.case_id == CASE))
            .mappings()
            .one()
        )
        db.execute(insert(submissions).values(dict(first) | {"submission_no": 2}))
        db.execute(
            update(cases).where(cases.c.case_id == CASE).values(latest_submission_no=2)
        )
    assert refusal(dismiss(client, exception_id)) == (
        404,
        f"Exception {exception_id} not found on {CASE}'s latest submission",
    )
    assert count(overrides) == 0


def test_an_exception_on_another_case_isnt_found_and_an_open_one_isnt_restored(
    client,
):
    exception_id = the_exception(client)
    awaiting_review(client, "PC-1203")
    other = client.post(
        path("PC-1203", exception_id, "dismissal"),
        json={"reason": "Wrong case"},
        headers=signed_in(MARCUS),
    )
    assert refusal(other) == (
        404,
        f"Exception {exception_id} not found on PC-1203's latest submission",
    )
    assert refusal(restore(client, exception_id)) == (
        409,
        f"Exception {exception_id} isn't dismissed, so it can't be restored",
    )
    assert refusal(dismiss(client, 9999)) == (
        404,
        f"Exception 9999 not found on {CASE}'s latest submission",
    )


def test_overrides_never_touch_the_labels(client):
    with engine().connect() as db:
        before = [dict(row) for row in db.execute(select(labels)).mappings()]
    exception_id = the_exception(client)
    dismiss(client, exception_id)
    restore(client, exception_id)
    add(client)
    with engine().connect() as db:
        after = [dict(row) for row in db.execute(select(labels)).mappings()]
    assert after == before


def modules_using(table: str) -> set[str]:
    """The backend's modules that import a table from the database module."""
    using = set()
    for module in BACKEND.glob("*.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "backend.database"
                and table in {alias.name for alias in node.names}
            ):
                using.add(module.stem)
    return using


def test_only_seeding_and_scoring_reach_the_labels():
    assert modules_using("labels") == {"seeding", "scoreboard"}
    assert modules_using("decoys") == {"seeding", "scoreboard"}
    assert "overrides" not in modules_using("labelled_cases")


def test_the_override_log_reads_by_date_newest_first_with_its_exception(client):
    exception_id = the_exception(client)
    dismiss(client, exception_id)
    restore(client, exception_id)
    with engine().connect() as db:
        total, [second, first] = overrides_between(db, "2000-01-01", "2100-01-01", 9)
        assert total == 2
        assert [first.kind, second.kind] == ["dismissed", "restored"]
        assert (first.case_id, first.exception_id) == ("PC-1201", exception_id)
        assert (first.rule, first.source) == ("rate.base_short", "check")
        assert overrides_between(db, "2000-01-01", first.created_at, 9) == (0, [])
        assert overrides_between(db, first.created_at, "2100-01-01", 1) == (
            2,
            [second],
        )


def test_sign_off_waits_until_every_exception_is_dismissed(dashboard, client):
    exception_id = the_exception(client)
    assert refusal(sign_off(dashboard, CASE, MARCUS)) == (
        409,
        f"Case {CASE} has 1 open exception, so it can't be signed off: dismiss "
        "each with a reason, or send it back to its subcontractor",
    )
    dismiss(client, exception_id)
    assert sign_off(dashboard, CASE, MARCUS).status_code == 200
    assert committed_case(CASE)["status"] == "accepted"


def test_a_flagged_case_is_worked_by_hand_the_same_way(dashboard, client):
    start(client, CASE)
    flag(client, CASE)
    added = add(
        client,
        rule="form.unsigned",
        worker_id=None,
        line_no=None,
        shortfall_cents=None,
        reason="The certification isn't signed",
    ).json()
    [exception] = added["exceptions"]
    assert sign_off(dashboard, CASE, MARCUS).status_code == 409
    dismiss(client, exception["exception_id"], reason="Signed on the paper copy")
    assert sign_off(dashboard, CASE, MARCUS).status_code == 200


def test_a_case_the_agent_failed_is_worked_by_hand_the_same_way(dashboard, client):
    for attempt in ("t-1", "t-2"):
        start(client, CASE, thread_id=attempt)
        fail(client, CASE)
    assert committed_case(CASE)["agent_failed"]
    [exception] = add(client).json()["exceptions"]
    assert sign_off(dashboard, CASE, MARCUS).status_code == 409
    dismiss(client, exception["exception_id"], reason="Paid on the corrected check")
    assert sign_off(dashboard, CASE, MARCUS).status_code == 200


def test_the_agents_key_takes_no_override(client, agent_key):
    exception_id = the_exception(client)
    with_the_key = signed_in(MARCUS) | {API_KEY_HEADER: agent_key}
    for request_path, body in [
        (path(CASE, exception_id, "dismissal"), {"reason": "No"}),
        (path(CASE, exception_id, "restoration"), {"reason": "No"}),
        (path(CASE), MISSED),
    ]:
        assert client.post(request_path, json=body).status_code == 401
        refused = client.post(request_path, json=body, headers=with_the_key)
        assert refused.status_code == 403
    assert count(overrides) == 0


def test_a_reviewer_outside_the_cases_projects_cant_override_it(client):
    exception_id = the_exception(client)
    assert refusal(dismiss(client, exception_id, email=PRIYA)) == (
        404,
        f"Case {CASE} not found",
    )
