"""The cases follow the lifecycle: dates in order, each history case decided by a
reviewer of its project or the compliance manager, the last week waiting."""

from datetime import timedelta

from context.payroll_files import DUE_DAYS
from data.payroll_world.lifecycle import Status
from data.tests.development_set import CASES, SEEDED, WORLD
from data.tests.sets import LabelledSet, each_set

LATE = {label.case_id for label in SEEDED.labels if label.rule == "timeliness.late"}


@each_set
def test_wages_are_paid_after_the_week_and_payrolls_received_after_that(
    labelled: LabelledSet,
):
    errors = labelled.manifest.errors
    # The last week's late filings were paid more than the due days before they came.
    paid_early = {e.case for e in errors if "wage_paid_days_before" in e.given}
    unsigned = {e.case for e in errors if e.rule == "form.unsigned"}
    for case in labelled.cases:
        if case.case_id in paid_early:
            continue
        for submission in case.submissions:
            cert = submission.payroll.certification
            assert cert.week_ending < cert.wage_payment_date <= submission.received_on
            if case.case_id in unsigned and submission.number == 1:
                continue
            assert cert.signed_on is not None
            assert cert.week_ending < cert.signed_on <= submission.received_on


def test_the_last_week_is_received_on_the_business_date_and_waits_for_a_reviewer():
    last = [case for case in CASES if case.filing.week == WORLD.spec.weeks]
    assert {case.status for case in last} == {Status.RECEIVED}
    assert {s.received_on for c in last for s in c.submissions} == {
        WORLD.spec.business_date
    }
    assert all(case.reviewer is None and case.accepted_on is None for case in last)


def test_history_is_received_within_the_due_days_and_decided_after():
    history = [case for case in CASES if case.filing.week < WORLD.spec.weeks]
    for case in history:
        for submission in case.submissions:
            paid = submission.payroll.certification.wage_payment_date
            on_time = submission.received_on <= paid + timedelta(days=DUE_DAYS)
            assert on_time != (case.case_id in LATE)
        decided = case.accepted_on or case.returned_on
        assert decided is not None
        assert decided > case.submissions[-1].received_on


def test_history_is_decided_by_the_projects_reviewer_or_the_compliance_manager():
    for case in CASES:
        if case.reviewer:
            project = WORLD.project(case.filing.engagement.project_id)
            assert case.reviewer in (project.reviewer, WORLD.spec.compliance_manager)
    deciders = {case.reviewer for case in CASES if case.reviewer}
    assert WORLD.spec.compliance_manager in deciders
