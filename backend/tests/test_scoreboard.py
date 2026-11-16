"""The Scoreboard: an evaluation played out through the API, with a label caught, one
missed, one caught with a shortfall a cent out, a false exception, a flagged decoy
and a missed screening flag, read back with each measure worked out by hand, in a
fixed number of queries however many evaluations there are."""

import pytest
from sqlalchemy import event

from backend.database import SCREENING, engine
from backend.tests.case_requests import flag, record_findings, report, start
from backend.tests.dashboard_reads import evaluations
from backend.tests.round_requests import as_finding, labels_of
from backend.tests.run_requests import create_evaluation, fail_run, get_evaluation


def money_labelled(copies, found, count):
    """The first copies whose labels all carry money, and no screening."""
    chosen = [
        c
        for c in copies
        if found.get(original(c))
        and all(x["expected_shortfall_cents"] for x in found[original(c)])
    ]
    return chosen[:count]


def original(copy_id):
    return copy_id.rsplit("-E", 1)[0]


def raise_these(client, copy_id, findings, notice="Please correct and resubmit."):
    start(client, copy_id, thread_id=copy_id)
    candidates = record_findings(client, copy_id, findings=findings).json()
    ids = [c["candidate_id"] for c in candidates]
    return report(client, copy_id, raised=ids, notice=notice if ids else "")


FALSE = {
    "rule": "form.missing_field",
    "worker_id": None,
    "line_no": None,
    "expected": "Every required field filled in",
    "actual": "Blank: fein",
    "shortfall_cents": None,
    "citation": "MW-562 payroll certification",
}


@pytest.fixture
def played_out(client):
    """A development evaluation in which six copies are worked, each to show one
    way of scoring, and the rest left as copied, raising nothing."""
    run = create_evaluation(client, "development").json()
    copies = [c["case_id"] for c in run["cases"]]
    found = labels_of("development")
    caught, wrong, missed = money_labelled(copies, found, 3)
    decoy, flagged_decoy = [c for c in copies if original(c) not in found][:2]
    [hidden] = [
        c
        for c in copies
        if any(x["rule"] == SCREENING for x in found.get(original(c), []))
    ][:1]
    raise_these(client, caught, [as_finding(x) for x in found[original(caught)]])
    off = [as_finding(x) for x in found[original(wrong)]]
    off[0]["shortfall_cents"] += 1
    raise_these(client, wrong, off)
    raise_these(client, missed, [])
    raise_these(client, decoy, [FALSE])
    start(client, flagged_decoy, thread_id=flagged_decoy)
    flag(client, flagged_decoy)
    raise_these(client, hidden, [])
    client.post(f"/api/runs/{run['run_id']}/finish")
    return run, found, (caught, wrong, missed, decoy, flagged_decoy, hidden), copies


def test_an_evaluations_measures_as_worked_out_by_hand(client, played_out):
    run, found, worked, copies = played_out
    caught, wrong, missed, decoy, flagged_decoy, hidden = worked
    evaluation = get_evaluation(client, run["run_id"])
    every = [x for xs in found.values() for x in xs if x["rule"] != SCREENING]
    flags = [x for xs in found.values() for x in xs if x["rule"] == SCREENING]
    measures = evaluation["measures"]
    caught_labels = len(found[original(caught)]) + len(found[original(wrong)])
    assert (measures["caught"], measures["labels"]) == (caught_labels, len(every))
    assert measures["catch_rate"] == pytest.approx(caught_labels / len(every))
    # The wrong copy's first label is a cent out; every other caught one is right.
    assert measures["shortfall_accuracy"] == pytest.approx(
        (caught_labels - 1) / caught_labels
    )
    # The decoy's exception, and the flag on the other decoy.
    assert measures["false_exceptions"] == 2
    assert measures["false_per_100"] == pytest.approx(200 / len(copies))
    assert (measures["screening_caught"], measures["screening_expected"]) == (
        0,
        len(flags),
    )

    by_copy = {c["case_id"]: c for c in evaluation["cases"]}
    assert {x["result"] for x in by_copy[caught]["labels"]} == {"caught"}
    assert by_copy[wrong]["labels"][0]["result"] == "shortfall_wrong"
    assert by_copy[wrong]["labels"][0]["shortfall_cents"] == (
        found[original(wrong)][0]["expected_shortfall_cents"] + 1
    )
    assert {x["result"] for x in by_copy[missed]["labels"]} == {"missed"}
    assert by_copy[missed]["misses"] == len(found[original(missed)])
    assert [e["matched"] for e in by_copy[decoy]["exceptions"]] == [False]
    assert by_copy[flagged_decoy]["false_exceptions"] == 1
    assert (
        by_copy[hidden]["screening_expected"],
        by_copy[hidden]["screening_found"],
    ) == (
        True,
        False,
    )


def queries_for_the_list(client):
    """Count the queries one read of the Scoreboard's list makes."""
    statements = []

    def counted(*_):
        statements.append(1)

    event.listen(engine(), "before_cursor_execute", counted)
    try:
        evaluations(client)
    finally:
        event.remove(engine(), "before_cursor_execute", counted)
    return len(statements)


def test_the_list_takes_as_many_queries_for_three_evaluations_as_for_one(
    client, played_out
):
    one = queries_for_the_list(client)
    for _ in range(2):
        fail_run(client, create_evaluation(client, "tiny").json()["run_id"])
    assert len(evaluations(client)) == 3
    assert queries_for_the_list(client) == one
