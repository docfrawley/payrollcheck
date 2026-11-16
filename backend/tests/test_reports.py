"""The guarantee: an exception report is recorded only when every shortfall in it
is a check tool's finding of this attempt, every finding is raised or dismissed
with a reason, and a report with exceptions has a notice."""

from typing import get_args

import pytest

from backend.models import CheckName, RuleCode
from backend.rule_codes import CHECKS, RULES
from backend.tests.case_requests import (
    NOTICE,
    finding,
    record_findings,
    report,
    run_the_other_checks,
    start,
)
from backend.tests.rows import everything_recorded

CASE = "PC-1201"


@pytest.fixture
def candidates(client):
    """A started case with two of a check's findings, the second with no money,
    and every other check run, finding nothing."""
    start(client, CASE)
    found = [finding(), finding("classification.changed", "W-002", 2)]
    found[1]["shortfall_cents"] = None
    kept = record_findings(client, CASE, findings=found).json()
    run_the_other_checks(client, CASE)
    return kept


def added(**changes):
    """An exception the agent adds of its own, carrying the first finding's money
    unless told otherwise."""
    fields = finding() | changes
    return {k: fields[k] for k in fields}


def test_a_check_s_findings_are_kept_with_ids_severities_and_a_step(client, candidates):
    assert [c["candidate_id"] for c in candidates] == sorted(
        c["candidate_id"] for c in candidates
    )
    assert [c["severity"] for c in candidates] == ["high", "low"]
    case = client.get(f"/api/cases/{CASE}").json()
    assert case["checks_run"] == list(CHECKS)
    assert [c["candidate_id"] for c in case["candidates"]] == [
        c["candidate_id"] for c in candidates
    ]


def test_a_check_run_again_replaces_its_findings(client, candidates):
    again = record_findings(client, CASE, findings=[finding()]).json()
    case = client.get(f"/api/cases/{CASE}").json()
    assert [c["candidate_id"] for c in case["candidates"]] == [
        c["candidate_id"] for c in again
    ]


def test_a_report_matching_its_candidates_is_recorded(client, candidates):
    money, note = candidates
    reason = "The note says W-002 was acting foreman."
    recorded = report(
        client,
        CASE,
        raised=[money["candidate_id"]],
        dismissed=[{"candidate_id": note["candidate_id"], "reason": reason}],
        notice=NOTICE,
    )
    assert recorded.status_code == 200
    case = recorded.json()
    assert case["status"] == "awaiting_review"
    [exception] = case["exceptions"]
    assert (exception["rule"], exception["shortfall_cents"]) == ("rate.base_short", 32)
    assert exception["candidate_id"] == money["candidate_id"]
    assert exception["raised_by"] == "PayrollCheck Agent, version 1"
    assert exception["source"] == "check"
    assert case["notice"]["draft"] == NOTICE
    dismissed = [c for c in case["candidates"] if c["dismissed_because"]]
    assert [c["dismissed_because"] for c in dismissed] == [reason]


def test_an_added_exception_with_a_candidates_money_raises_that_candidate(
    client, candidates
):
    money, note = candidates
    case = report(
        client,
        CASE,
        dismissed=[{"candidate_id": note["candidate_id"], "reason": "Explained"}],
        added=[added()],
        notice=NOTICE,
    ).json()
    assert [e["candidate_id"] for e in case["exceptions"]] == [money["candidate_id"]]


def test_an_added_exception_with_no_money_is_the_agent_s_own(client, candidates):
    ids = [c["candidate_id"] for c in candidates]
    own = added(rule="form.project_mismatch", worker_id=None, line_no=None)
    own["shortfall_cents"] = None
    case = report(client, CASE, raised=ids, added=[own], notice=NOTICE).json()
    [agents] = [e for e in case["exceptions"] if e["candidate_id"] is None]
    assert (agents["rule"], agents["severity"]) == ("form.project_mismatch", "medium")
    assert agents["source"] == "agent"


@pytest.mark.parametrize(
    "changes",
    [
        {"shortfall_cents": 9999},
        {"shortfall_cents": 33},
        {"worker_id": "W-009"},
        {"rule": "rate.fringe_short"},
        {"line_no": 2},
    ],
    ids=["invented", "a cent out", "another worker", "another rule", "another line"],
)
def test_a_money_exception_no_check_found_is_refused(client, candidates, changes):
    before = everything_recorded()
    refused = report(
        client,
        CASE,
        raised=[c["candidate_id"] for c in candidates],
        added=[added(**changes)],
        notice=NOTICE,
    )
    assert refused.status_code == 422
    assert "must be one a check tool found" in refused.json()["detail"]
    assert everything_recorded() == before


def test_every_finding_must_be_raised_or_dismissed(client, candidates):
    money, note = candidates
    refused = report(client, CASE, raised=[money["candidate_id"]], notice=NOTICE)
    assert refused.status_code == 422
    assert refused.json()["detail"] == (
        f"Raise or dismiss every finding: candidates {note['candidate_id']} are neither"
    )


def test_a_finding_raised_and_dismissed_or_unknown_is_refused(client, candidates):
    money, note = candidates
    both = report(
        client,
        CASE,
        raised=[money["candidate_id"], note["candidate_id"]],
        dismissed=[{"candidate_id": note["candidate_id"], "reason": "No"}],
        notice=NOTICE,
    )
    assert both.status_code == 422
    unknown = report(
        client, CASE, raised=[money["candidate_id"], note["candidate_id"], 999]
    )
    assert unknown.status_code == 422
    assert "999 isn't one of this attempt's findings" in unknown.json()["detail"]


def test_a_dismissal_needs_a_reason(client, candidates):
    money, note = candidates
    refused = report(
        client,
        CASE,
        raised=[money["candidate_id"]],
        dismissed=[{"candidate_id": note["candidate_id"], "reason": "  "}],
        notice=NOTICE,
    )
    assert refused.status_code == 422


def test_exceptions_need_a_notice(client, candidates):
    ids = [c["candidate_id"] for c in candidates]
    refused = report(client, CASE, raised=ids, notice="  ")
    assert (refused.status_code, refused.json()["detail"]) == (
        422,
        "A report with exceptions needs a draft send-back notice",
    )


def test_a_rule_outside_the_catalogue_is_refused(client, candidates):
    ids = [c["candidate_id"] for c in candidates]
    own = added(rule="rate.made_up")
    assert (
        report(client, CASE, raised=ids, added=[own], notice=NOTICE).status_code == 422
    )


def test_a_clean_report_needs_no_notice(client):
    start(client, CASE)
    record_findings(client, CASE, findings=[])
    case = report(client, CASE).json()
    assert (case["status"], case["exceptions"], case["notice"]) == (
        "awaiting_review",
        [],
        None,
    )
    assert case["checks_run"] == list(CHECKS)


def test_a_report_before_every_check_has_run_is_refused(client):
    start(client, CASE)
    for check in CHECKS[:-2]:
        record_findings(client, CASE, check, [])
    before = everything_recorded()
    body = {"raised": [], "dismissed": [], "added": [], "notice": ""}
    refused = client.post(
        f"/api/cases/{CASE}/report", json=body | {"raised_by": "The agent"}
    )
    assert (refused.status_code, refused.json()["detail"]) == (
        422,
        "Run every check before reporting: check_timeliness, check_classification "
        "hasn't run on this attempt",
    )
    assert everything_recorded() == before


def test_a_case_not_in_progress_is_refused(client):
    assert report(client, CASE).status_code == 409
    assert record_findings(client, CASE).status_code == 409
    assert report(client, "PC-9999").status_code == 404


@pytest.mark.parametrize("rule", ["rate.base_short", "classification.mismatch"])
def test_a_rule_that_carries_money_cant_be_added_without_a_check(
    client, candidates, rule
):
    ids = [c["candidate_id"] for c in candidates]
    own = added(rule=rule, worker_id="W-009")
    own["shortfall_cents"] = None
    refused = report(client, CASE, raised=ids, added=[own], notice=NOTICE)
    assert refused.status_code == 422
    assert refused.json()["detail"].startswith(f"A {rule} exception for W-009")


def test_the_reports_codes_and_checks_are_the_catalogues():
    assert set(get_args(RuleCode)) == set(RULES)
    assert get_args(CheckName) == CHECKS
