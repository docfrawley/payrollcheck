"""The Copilot's expected answers, checked against facts the labels, the manifest
and the cases give apart from the code that computes them: one for each of the six
questions, inside Marcus Oyelaran's scope."""

from data.generate import ASKED_BY, DATA
from data.payroll_world import periods
from data.payroll_world.expected_answers import QUESTIONS, read_expected
from data.payroll_world.lifecycle import Status
from data.payroll_world.records import label_record
from data.payroll_world.worlds import GARDEN_STATE, LINCOLN, NOTICE_CASE
from data.tests.development_set import CASES, MANIFEST, SEEDED, WORLD

COMMITTED = read_expected(DATA)
BY_ID = {case.case_id: case for case in CASES}
SCOPE = {p.id for p in WORLD.spec.projects if p.reviewer == ASKED_BY}
BUSINESS_DATE = WORLD.spec.business_date
LAST_WEEK = WORLD.spec.weeks


def answer(number: int) -> dict:
    return COMMITTED["answers"][number - 1]["answer"]


def in_scope(case_id: str) -> bool:
    return BY_ID[case_id].filing.engagement.project_id in SCOPE


def open_labels(case_id: str) -> list:
    """A case's labels, open while it is Returned to sub on its first submission."""
    if BY_ID[case_id].status != Status.RETURNED:
        return []
    return [label for label in SEEDED.labels if label.case_id == case_id]


def test_an_answer_for_each_question_for_the_reviewers_projects():
    assert [entry["question"] for entry in COMMITTED["answers"]] == list(QUESTIONS)
    assert set(COMMITTED["projects"]) == SCOPE
    assert COMMITTED["business_date"] == BUSINESS_DATE.isoformat()


def test_the_subs_with_open_exceptions_on_the_lincoln_school_renovation():
    expected = {}
    for case in CASES:
        if case.filing.engagement.project_id == LINCOLN and open_labels(case.case_id):
            expected.setdefault(case.filing.engagement.subcontractor_id, []).append(
                case.case_id
            )
    found = {s["subcontractor_id"]: s["case_ids"] for s in answer(1)["subcontractors"]}
    assert found == expected
    assert len(found) >= 2
    counts = {
        s["subcontractor_id"]: s["open_exceptions"] for s in answer(1)["subcontractors"]
    }
    assert counts == {
        sub: sum(len(open_labels(case)) for case in cases)
        for sub, cases in expected.items()
    }


def test_garden_states_flagged_and_outstanding_underpayment_this_month():
    month = periods.this_month(BUSINESS_DATE)
    labels = [
        label
        for case in CASES
        if case.filing.engagement.subcontractor_id == GARDEN_STATE
        and in_scope(case.case_id)
        and month.holds(case.filing.week_ending)
        for label in open_labels(case.case_id)
        if label.expected_shortfall_cents is not None
    ]
    total = sum(label.expected_shortfall_cents or 0 for label in labels)
    found = answer(2)
    assert found["case_ids"] == sorted({label.case_id for label in labels})
    assert found["flagged_cents"] == found["outstanding_cents"] == total > 0
    assert found["exceptions"] == [label_record(label) for label in labels]
    assert found["period"]["last_week_ending"] == "2026-11-29"


def test_last_weeks_late_and_missing_payrolls():
    late = sorted(
        label.case_id
        for label in SEEDED.labels
        if label.rule == "timeliness.late"
        and BY_ID[label.case_id].filing.week == LAST_WEEK
        and in_scope(label.case_id)
    )
    missing = [
        (f.engagement.subcontractor_id, f.engagement.project_id)
        for f in SEEDED.missing
        if f.engagement.project_id in SCOPE
    ]
    found = answer(3)
    assert sorted(case["case_id"] for case in found["late"]) == late
    assert [
        (m["subcontractor_id"], m["project_id"]) for m in found["missing"]
    ] == missing
    assert late
    assert missing
    assert all(m["project_id"] in SCOPE for m in found["missing"])
    assert (
        found["period"]["last_week_ending"] == WORLD.week_ending(LAST_WEEK).isoformat()
    )


def test_the_middlesex_journeyman_electricians_rate_and_since_when():
    rate = answer(4)
    assert (rate["determination_id"], rate["effective"]) == (
        "MID-2025-11",
        "2026-10-01",
    )
    assert (rate["wage_cents"], rate["fringe_cents"], rate["total_cents"]) == (
        6110,
        3540,
        9650,
    )
    assert rate["source"]["file"] == "rate_determinations.yaml"


def test_the_classification_changes_in_the_last_four_weeks():
    four_weeks = periods.last_weeks(BUSINESS_DATE, 4)
    found = answer(5)["changes"]
    changed = {(c["case_id"], c["worker_id"]) for c in found}
    seeded = {
        (label.case_id, label.worker_id)
        for label in SEEDED.labels
        if label.rule == "classification.changed" and in_scope(label.case_id)
    }
    noted = {
        (decoy.case, decoy.worker)
        for decoy in MANIFEST.decoys.values()
        if decoy.kind == "classification_note"
    }
    assert seeded | noted <= changed
    assert len(seeded) >= 2
    for change in found:
        assert in_scope(change["case_id"])
        assert four_weeks.holds(BY_ID[change["case_id"]].filing.week_ending)


def test_pc_0311_has_its_three_exceptions_with_their_lines():
    notice = answer(6)
    labels = open_labels(NOTICE_CASE)
    assert notice["status"] == Status.RETURNED
    assert notice["exceptions"] == [label_record(label) for label in labels]
    assert len(labels) == 3
    assert all(e["line_no"] for e in notice["exceptions"])
    assert notice["shortfall_cents"] == sum(
        e["expected_shortfall_cents"] for e in notice["exceptions"]
    )
