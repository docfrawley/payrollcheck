"""Layer 1 of the Copilot's acceptance tests: each of its six questions' reads,
called as Marcus Oyelaran with the inputs the question implies, on a freshly
seeded database, gives what data/copilot_expected.json holds, field by field.
Question 4 is the context layer's, in context/tests/test_payroll_files.py."""

from backend.tests.copilot_reads import (
    LAST_FOUR_WEEKS,
    LAST_WEEK,
    THIS_MONTH,
    classification_changes,
    expected_answer,
    exposure,
    filings,
    find_cases,
    read,
)


def test_1_the_subs_on_the_lincoln_school_renovation_with_open_exceptions(dashboard):
    expected = expected_answer(1)
    found = find_cases(
        dashboard, project_id=expected["project_id"], has_open_exceptions=True
    ).json()
    assert [
        {
            "subcontractor_id": group["subcontractor_id"],
            "name": group["name"],
            "case_ids": group["case_ids"],
            "open_exceptions": group["open_exceptions"],
        }
        for group in found["by_subcontractor"]
    ] == expected["subcontractors"]
    assert all(c["open_exceptions"] > 0 for c in found["cases"])


def test_2_the_underpayment_flagged_for_garden_state_electric_this_month(
    dashboard,
):
    expected = expected_answer(2)
    found = exposure(
        dashboard, subcontractor_id=expected["subcontractor_id"], period=THIS_MONTH
    ).json()
    assert found["period"] == expected["period"]
    assert found["case_ids"] == expected["case_ids"] == ["PC-1009"]
    assert found["flagged_cents"] == expected["flagged_cents"] == 19875
    assert found["outstanding_cents"] == expected["outstanding_cents"]
    assert (found["flagged"], found["outstanding"]) == ("$198.75", "$198.75")
    assert [
        {
            "case_id": e["case_id"],
            "rule": e["rule"],
            "worker_id": e["worker_id"],
            "line_no": e["line_no"],
            "expected_shortfall_cents": e["shortfall_cents"],
        }
        for e in found["exceptions"]
    ] == expected["exceptions"]


def test_3_the_payrolls_late_or_missing_for_last_week(dashboard):
    expected = expected_answer(3)
    found = filings(dashboard, LAST_WEEK).json()
    assert found["period"] == expected["period"]
    assert [
        {
            "case_id": f["case_id"],
            "subcontractor_id": f["subcontractor_id"],
            "project_id": f["project_id"],
            "wage_payment_date": f["wage_payment_date"],
            "received_on": f["received_on"],
        }
        for f in found["late"]
    ] == expected["late"]
    assert [
        {
            "subcontractor_id": m["subcontractor_id"],
            "project_id": m["project_id"],
            "week_ending": m["week_ending"],
        }
        for m in found["missing"]
    ] == expected["missing"]
    assert [m["late"] for m in found["missing"]] == [False]
    assert found["missing"][0]["deadline"] == "2026-12-02"


def test_5_every_worker_whose_classification_changed_in_the_last_four_weeks(
    dashboard,
):
    expected = expected_answer(5)
    found = classification_changes(dashboard, LAST_FOUR_WEEKS).json()
    assert found["period"] == expected["period"]
    assert [
        {
            "case_id": c["case_id"],
            "worker_id": c["worker_id"],
            "worker_name": c["worker_name"],
            "week_ending": c["week_ending"],
            "from": c["classification_before"],
            "to": c["classification_after"],
            "line_notes": c["line_notes"],
        }
        for c in found["changes"]
    ] == expected["changes"]


def test_6_the_three_exceptions_open_on_pc_0311(dashboard):
    expected = expected_answer(6)
    found = read(dashboard, f"/cases/{expected['case_id']}/exceptions").json()
    assert found["status"] == "returned_to_sub"
    assert [
        {
            "case_id": found["case_id"],
            "rule": e["rule"],
            "worker_id": e["worker_id"],
            "line_no": e["line_no"],
            "expected_shortfall_cents": e["shortfall_cents"],
        }
        for e in found["exceptions"]
    ] == expected["exceptions"]
    assert found["shortfall_cents"] == expected["shortfall_cents"] == 50375
    assert found["shortfall"] == "$503.75"
    assert all(e["citation"] for e in found["exceptions"])
