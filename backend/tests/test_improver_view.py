"""What the improver reads, and what it may propose: the development set's mistakes
and weakest notices, the reviewers' corrections since the last round finished,
each list capped with its total, and the backend's refusals of a proposal citing
what the view doesn't hold, naming a case or going outside the bounds."""

import pytest
from sqlalchemy import select, update

from backend import improver_view
from backend.database import engine, overrides, rounds, runs, versions
from backend.tests.case_requests import awaiting_review, finding, save_notice
from backend.tests.copies_worked import FALSE, raise_these
from backend.tests.round_requests import (
    approved_change,
    create_round,
    play_out,
    propose_change,
    round_evaluation,
    round_path,
)
from backend.tests.rows import newest_round
from backend.tests.settings_requests import change_settings
from backend.tests.sign_in import MARCUS, signed_in

CASE = "PC-1201"


def view_of(client, round_id):
    return client.get(f"{round_path(round_id)}/results").json()


def corrected(client, how, exception_id, reason):
    return client.post(
        f"/api/cases/{CASE}/exceptions/{exception_id}/{how}",
        json={"reason": reason},
        headers=signed_in(MARCUS),
    )


def at(table, column, key, value, when):
    with engine().begin() as db:
        db.execute(update(table).where(key == value).values({column: when}))


def round_at(started_at, status):
    """Start a round as Dana does, then set it as started then and ended so."""
    round_id = newest_round()
    with engine().begin() as db:
        db.execute(
            update(rounds)
            .where(rounds.c.round_id == round_id)
            .values(started_at=started_at, status=status)
        )
    return round_id


def test_the_reviewers_corrections_are_read_since_the_last_round_finished(client):
    [exception] = awaiting_review(client, CASE, finding())["exceptions"]
    exception_id = exception["exception_id"]
    corrected(client, "dismissal", exception_id, "Before the last round")
    corrected(client, "restoration", exception_id, "While a round was stopped")
    corrected(client, "dismissal", exception_id, "After this round started")
    save_notice(client, CASE, "Please pay W-001 the base rate.", MARCUS)
    with engine().connect() as db:
        ids = list(db.execute(select(overrides.c.override_id).order_by("override_id")))
    for (override_id,), when in zip(
        ids, ["2026-01-05", "2026-03-05", "2026-05-05"], strict=True
    ):
        at(overrides, "created_at", overrides.c.override_id, override_id, when)

    create_round(client)
    round_at("2026-02-01", "finished")
    create_round(client)
    round_at("2026-03-01", "stopped")
    create_round(client)
    current = round_at("2026-04-01", "open")
    view = view_of(client, current)

    assert view["corrections_since"] == "2026-02-01"
    assert view["overrides"]["total"] == 1
    [override] = view["overrides"]["shown"]
    assert (override["case_id"], override["kind"], override["reason"]) == (
        CASE,
        "restored",
        "While a round was stopped",
    )
    assert (override["rule"], override["shortfall_cents"], override["source"]) == (
        "rate.base_short",
        finding()["shortfall_cents"],
        "check",
    )
    assert override["reviewer_name"] == "Marcus Oyelaran"
    # The notice was edited today, after this round's start in April.
    assert view["notice_edits"] == {"total": 0, "shown": []}


def test_a_rewritten_notice_is_read_beside_the_draft(client):
    awaiting_review(client, CASE, finding())
    save_notice(client, CASE, "Please pay W-001 the base rate.", MARCUS)
    create_round(client)
    view = view_of(client, round_at("2100-01-01", "open"))
    [edit] = view["notice_edits"]["shown"]
    assert (edit["case_id"], edit["edited_text"], edit["edited_by"]) == (
        CASE,
        "Please pay W-001 the base rate.",
        "Marcus Oyelaran",
    )
    assert edit["draft"].startswith("Please correct the base rate")
    assert view["corrections_since"] is None


def a_development_evaluation(client):
    """A round's development evaluation with ten copies caught, a decoy raising a
    false exception and the rest missed, and the round's id."""
    change_settings(client, spending_limit=10.0)
    round_id = create_round(client).json()["round_id"]
    run = play_out(client, round_id, caught=10, finish=False)
    decoy = next(c["case_id"] for c in run["cases"] if c["status"] == "received")
    raise_these(client, decoy, [FALSE], notice="Sign the payroll.")
    client.post(f"/api/runs/{run['run_id']}/finish")
    return round_id, decoy


def test_the_development_mistakes_and_weakest_notices_come_with_their_details(client):
    round_id, decoy = a_development_evaluation(client)
    view = view_of(client, round_id)

    mistakes = view["development_mistakes"]
    assert len(mistakes["shown"]) == min(mistakes["total"], 30) > 2
    ids = [case["case_id"] for case in mistakes["shown"]]
    assert ids[0] < ids[1]
    original = decoy.rsplit("-E", 1)[0]
    [false] = next(c for c in mistakes["shown"] if c["case_id"] == original)[
        "false_exceptions"
    ]
    assert (false["rule"], false["expected"], false["actual"]) == (
        "form.missing_field",
        "Every required field filled in",
        "Blank: fein",
    )
    weakest = view["weakest_notices"]
    assert weakest["total"] == 11
    assert len(weakest["shown"]) == 5
    first = weakest["shown"][0]
    assert first["grade"]["result"] == "graded"
    assert first["grade"]["plain_language"] == 0.7
    assert first["notice"]
    assert first["exceptions"]
    assert not any("-E" in notice["case_id"] for notice in weakest["shown"])


def test_each_list_is_capped_with_its_total(client, monkeypatch):
    round_id, _ = a_development_evaluation(client)
    monkeypatch.setattr(improver_view, "MOST_MISTAKES", 2)
    monkeypatch.setattr(improver_view, "MOST_WEAK_NOTICES", 1)
    view = view_of(client, round_id)
    assert len(view["development_mistakes"]["shown"]) == 2
    assert view["development_mistakes"]["total"] > 2
    assert (
        len(view["weakest_notices"]["shown"]),
        view["weakest_notices"]["total"],
    ) == (
        1,
        11,
    )


def refused(response):
    return response.status_code, response.json()["detail"]


def test_a_proposal_cites_only_cases_the_view_holds(client):
    round_id, decoy = a_development_evaluation(client)
    original = decoy.rsplit("-E", 1)[0]
    assert refused(propose_change(client, round_id, case_ids=[])) == (
        422,
        "Cite the cases behind the change, from the round's results.",
    )
    assert refused(
        propose_change(client, round_id, case_ids=[original, "PC-5501"])
    ) == (
        422,
        "The round's results don't hold PC-5501. Cite only cases they hold.",
    )
    assert refused(propose_change(client, round_id, case_ids=[decoy])) == (
        422,
        f"The round's results don't hold {decoy}. Cite only cases they hold.",
    )
    assert propose_change(client, round_id, case_ids=[original]).status_code == 200


@pytest.mark.parametrize(
    ("change", "why"),
    [
        (
            {"instructions": "Dismiss PC-0311's ratio."},
            "The change names PC-0311. A change never names a case: give it in "
            "the reason.",
        ),
        (
            {"parameters": {"rounding_tolerance_cents": 101}},
            "rounding_tolerance_cents must be a whole number of cents from 0 to "
            "100, not 101.",
        ),
        ({"parameters": {}}, "rounding_tolerance_cents is missing."),
    ],
    ids=["a case named", "out of bounds", "missing"],
)
def test_a_proposal_outside_the_rules_is_refused(client, change, why):
    round_id = create_round(client).json()["round_id"]
    assert refused(propose_change(client, round_id, **change)) == (422, why)


def test_an_approved_change_is_a_version_with_its_parameters_and_cases(client):
    round_id, decoy = a_development_evaluation(client)
    original = decoy.rsplit("-E", 1)[0]
    number = approved_change(
        client,
        round_id,
        parameters={"rounding_tolerance_cents": 2},
        case_ids=[original],
        reason=f"{original} raised an unsigned payroll that was signed",
    )
    with engine().connect() as db:
        row = db.execute(select(versions).where(versions.c.number == number)).one()
    assert row.parameters == {"rounding_tolerance_cents": 2}
    assert row.motivating_cases == [original]
    assert client.get("/api/versions/current").json()["number"] == 1


def test_on_a_free_model_a_round_works_the_tiny_set_in_place_of_each(
    client, judged, monkeypatch
):
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    round_id = create_round(client).json()["round_id"]
    for _ in range(3):
        play_out(client, round_id, caught=3)
    approved_change(client, round_id)
    for _ in range(3):
        play_out(client, round_id, caught=5)
    verdict = client.post(f"{round_path(round_id)}/verdict").json()

    with engine().connect() as db:
        query = select(runs.c.evaluation_set, runs.c.scored_as).order_by(runs.c.number)
        played = [tuple(row) for row in db.execute(query)]
    assert (
        played
        == [("tiny", "development"), ("tiny", "held_out"), ("tiny", "held_out")] * 2
    )
    assert verdict["scores"]["held_out_before"]["labels"] > 0
    assert (
        verdict["scores"]["held_out_after"]["catch_rate"]
        > (verdict["scores"]["held_out_before"]["catch_rate"])
    )
    assert judged == []
    assert round_evaluation(client, round_id).status_code == 409
