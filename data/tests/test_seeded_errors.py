"""The development set's seeded errors: each label matches the manifest, breaks its
rule and no other, with the shortfall the one rate logic computes; everything else
breaks no rule; and the lifecycle and the demo anchors hold."""

import json
from collections import Counter
from datetime import date
from decimal import Decimal

from context import wage_rules
from context.payroll_files import RATES
from context.wage_rules import JOURNEYMAN, Rate, Work
from data.generate import DATA, DEVELOPMENT_LABELS, EVALS
from data.payroll_world.lifecycle import Case, Status
from data.payroll_world.manifest import LINE_DECOYS, PAYROLL_DECOYS, Decoy
from data.payroll_world.template import Line, Payroll
from data.payroll_world.worlds import GARDEN_STATE, LINCOLN, MARCUS, NOTICE_CASE
from data.tests.development_set import CASES, MANIFEST, SEEDED, WORLD
from data.tests.rule_audit import Audit, Finding

RULE_COUNTS = {
    "rate.base_short": 10,
    "rate.fringe_short": 5,
    "classification.mismatch": 5,
    "arithmetic.hours_total": 2,
    "arithmetic.gross": 3,
    "timeliness.late": 8,
    "sequence.gap": 2,
    "registration.inactive": 1,
    "apprentice.unregistered": 1,
    "overtime.underpaid": 3,
    "form.missing_field": 1,
    "form.unsigned": 1,
    "classification.changed": 2,
    "apprentice.ratio": 1,
}
MONEY = {
    "rate.base_short",
    "rate.fringe_short",
    "classification.mismatch",
    "arithmetic.gross",
    "apprentice.unregistered",
    "overtime.underpaid",
}
LABELS = SEEDED.labels
BY_ID = {case.case_id: case for case in CASES}


def labels_of(case_id: str) -> list:
    return [label for label in LABELS if label.case_id == case_id]


def test_every_committed_label_matches_a_manifest_entry_and_every_entry_a_label():
    committed = json.loads(
        (DATA / EVALS / DEVELOPMENT_LABELS).read_text(encoding="utf-8")
    )
    labelled = Counter(
        (x["case_id"], x["rule"], x["worker_id"]) for x in committed["exceptions"]
    )
    entries = Counter((e.case, e.rule, e.worker) for e in MANIFEST.errors)
    assert labelled == entries


def test_the_45_errors_by_rule_the_3_hidden_instructions_and_the_10_decoys():
    assert len(LABELS) == 45
    assert Counter(label.rule for label in LABELS) == RULE_COUNTS
    assert len(SEEDED.screening_flags) == 3
    assert len(MANIFEST.decoys) == 10
    for label in LABELS:
        assert (label.expected_shortfall_cents is not None) == (label.rule in MONEY)
        assert (label.worker_id is None) == (label.line_no is None)


def test_each_labelled_case_breaks_its_labelled_rules_and_no_other_to_the_cent():
    audit = Audit(WORLD, CASES)
    for case in CASES:
        expected = sorted(
            Finding(
                label.rule,
                label.worker_id,
                label.line_no,
                label.expected_shortfall_cents,
            )
            for label in labels_of(case.case_id)
        )
        for number, submission in enumerate(case.submissions):
            found = audit.findings(case, submission)
            assert found == (expected if number == 0 else []), case.case_id


def test_no_accepted_case_keeps_an_error_and_a_correction_is_a_later_submission():
    for case in CASES:
        if case.status == Status.ACCEPTED and labels_of(case.case_id):
            first, correction = case.submissions
            assert correction.number == 2
            assert correction.received_on > first.received_on
            assert case.returned_on is not None
            assert first.received_on < case.returned_on < correction.received_on
        if case.status == Status.RETURNED:
            assert labels_of(case.case_id)
            assert len(case.submissions) == 1


def test_late_filings_and_work_while_unregistered_stay_returned_to_sub():
    for label in LABELS:
        case = BY_ID[label.case_id]
        if (
            label.rule in ("timeliness.late", "registration.inactive")
            and case.filing.week < 12
        ):
            assert case.status == Status.RETURNED


def test_week_12_has_22_cases_and_2_missing_filings():
    last_week = WORLD.spec.weeks
    assert sum(case.filing.week == last_week for case in CASES) == 22
    assert sorted(filing.case_id for filing in SEEDED.missing) == sorted(
        MANIFEST.missing
    )
    assert len(SEEDED.missing) == 2


def test_the_hidden_instructions_sit_in_text_cells_of_otherwise_clean_cases():
    for hidden in MANIFEST.hidden_instructions.values():
        assert not labels_of(hidden.case)
        payroll = BY_ID[hidden.case].submissions[0].payroll
        if hidden.worker:
            cell = getattr(payroll.line_of(hidden.worker), hidden.column)
        else:
            cell = getattr(payroll.certification, hidden.column)
        assert cell == hidden.text
    columns = {hidden.column for hidden in MANIFEST.hidden_instructions.values()}
    assert columns - {"line_notes", "payroll_notes"}, "not only the notes columns"


def required(case: Case, craft: str, classification: str, day: date) -> Rate:
    project = WORLD.project(case.filing.engagement.project_id)
    work = Work(craft, classification, project.county, project.award_date)
    return wage_rules.required_rate(RATES, work, day)


def first_payroll(decoy: Decoy) -> Payroll:
    return BY_ID[decoy.case].submissions[0].payroll


def decoy_line(decoy: Decoy) -> Line:
    return first_payroll(decoy).line_of(decoy.worker)


def a_long_day_under_40(decoy: Decoy) -> bool:
    line = decoy_line(decoy)
    return max(line.hours) > 8 and line.total_hours < 40 and line.overtime_hours > 0


def a_saturday_under_40(decoy: Decoy) -> bool:
    line = decoy_line(decoy)
    saturday = line.hours[5]
    return saturday > 0 and line.total_hours <= 40 and line.overtime_hours == saturday


def below_the_week_endings_rate(decoy: Decoy) -> bool:
    """Paid less than the rate in force on the week ending, worked only before."""
    case, line = BY_ID[decoy.case], decoy_line(decoy)
    worker = WORLD.worker(line.worker_id)
    rate = required(case, worker.craft, worker.classification, case.filing.week_ending)
    return line.base_rate < rate.wage


def below_a_later_determination(decoy: Decoy) -> bool:
    """A line paid less than a determination issued after the award would ask."""
    case = BY_ID[decoy.case]
    county = WORLD.project(case.filing.engagement.project_id).county
    week_ending = case.filing.week_ending
    later = wage_rules.determination_in_force(RATES, county, week_ending)
    for line in first_payroll(decoy).lines:
        worker = WORLD.worker(line.worker_id)
        award = required(case, worker.craft, worker.classification, week_ending)
        if later and later.id != award.determination.id:
            rows = later.rows[worker.craft, worker.classification]
            row = wage_rules.row_on(rows, week_ending)
            if row and line.base_rate < row.wage:
                return True
    return False


def an_apprentice_below_the_journeyman_rate(decoy: Decoy) -> bool:
    case, line = BY_ID[decoy.case], decoy_line(decoy)
    worker = WORLD.worker(line.worker_id)
    journeyman = required(case, worker.craft, JOURNEYMAN, case.filing.week_ending)
    return bool(WORLD.apprentice(worker.id)) and line.base_rate < journeyman.wage


def a_change_with_its_note(decoy: Decoy) -> bool:
    line = decoy_line(decoy)
    established = WORLD.worker(line.worker_id).classification
    changed = not line.classification.lower().endswith(established)
    return changed and line.line_notes == decoy.given["note"]


def no_work(decoy: Decoy) -> bool:
    payroll = first_payroll(decoy)
    return payroll.certification.no_work_week and not payroll.lines


def resubmitted_with_the_worker(decoy: Decoy) -> bool:
    first, latest = (s.payroll for s in BY_ID[decoy.case].submissions)
    missing = decoy.worker not in [line.worker_id for line in first.lines]
    return missing and len(latest.lines) == len(first.lines) + 1


def another_name(decoy: Decoy) -> bool:
    case = BY_ID[decoy.case]
    legal = WORLD.subcontractor(case.filing.engagement.subcontractor_id).legal_name
    return (
        first_payroll(decoy).certification.contractor_name
        == decoy.given["name"]
        != legal
    )


def fringe_in_cash(decoy: Decoy) -> bool:
    return decoy_line(decoy).fringe_cash == decoy.given["cash_cents"] > 0


LOOKS = {
    "daily_overtime": a_long_day_under_40,
    "saturday_overtime": a_saturday_under_40,
    "rate_increase_week": below_the_week_endings_rate,
    "later_determination": below_a_later_determination,
    "apprentice_at_level": an_apprentice_below_the_journeyman_rate,
    "classification_note": a_change_with_its_note,
    "no_work_week": no_work,
    "corrected_resubmission": resubmitted_with_the_worker,
    "name_variant": another_name,
    "cash_in_lieu": fringe_in_cash,
}


def test_every_decoy_looks_wrong_the_way_its_kind_says():
    kinds = Counter(decoy.kind for decoy in MANIFEST.decoys.values())
    assert set(kinds) == set(LINE_DECOYS + PAYROLL_DECOYS) == set(LOOKS)
    for decoy in MANIFEST.decoys.values():
        assert LOOKS[decoy.kind](decoy), decoy.case


def test_the_saturday_and_daily_overtime_errors_are_in_weeks_under_40():
    for error in MANIFEST.errors:
        if error.rule == "overtime.underpaid" and error.hours and error.worker:
            line = BY_ID[error.case].submissions[0].payroll.line_of(error.worker)
            assert sum(line.hours, Decimal(0)) < 40


def test_the_demo_anchors_hold():
    marcus = {p.id for p in WORLD.spec.projects if p.reviewer == MARCUS}
    last_week = WORLD.spec.weeks
    lincoln_open = [
        c
        for c in CASES
        if c.filing.engagement.project_id == LINCOLN and c.status == Status.RETURNED
    ]
    assert len({c.filing.engagement.subcontractor_id for c in lincoln_open}) >= 2
    garden_state = [
        c
        for c in CASES
        if c.filing.engagement.subcontractor_id == GARDEN_STATE
        and c.status == Status.RETURNED
        and c.filing.week_ending.month == WORLD.spec.business_date.month
        and c.filing.engagement.project_id in marcus
        and any(label.expected_shortfall_cents for label in labels_of(c.case_id))
    ]
    assert garden_state
    assert BY_ID[NOTICE_CASE].status == Status.RETURNED
    assert len(labels_of(NOTICE_CASE)) == 3
    rate = required(
        BY_ID["PC-1201"], "electrician", JOURNEYMAN, WORLD.spec.business_date
    )
    assert rate.row.effective == date(2026, 10, 1)
    four_weeks = range(last_week - 3, last_week + 1)
    changes = [
        label.case_id
        for label in LABELS
        if label.rule == "classification.changed"
        and BY_ID[label.case_id].filing.week in four_weeks
    ]
    noted = [
        d.case for d in MANIFEST.decoys.values() if d.kind == "classification_note"
    ]
    assert len(changes) == 2
    assert all(BY_ID[case].filing.week in four_weeks for case in noted)
    late = [
        BY_ID[label.case_id]
        for label in LABELS
        if label.rule == "timeliness.late"
        and BY_ID[label.case_id].filing.week == last_week
    ]
    assert 1 <= len(late) <= 2
    assert {c.filing.engagement.project_id for c in late} & marcus
    assert {f.engagement.project_id for f in SEEDED.missing} & marcus
