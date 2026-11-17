"""The answers the PayrollCheck Copilot must give to its six questions, computed
from the development set as seeding will leave it, before any dispatch: the
history's exceptions open on cases Returned to sub, superseded on corrected cases,
and none yet on the last week's Received cases. Each is for one reviewer's scope,
the projects they review, at the business date, with every period resolved by the
periods module."""

import json
from pathlib import Path
from typing import Any

from context.sources import (
    FILING_RULES,
    RATE_DETERMINATIONS,
    SYNTHETIC,
    file_source,
    read_yaml,
)
from context.wage_rules import JOURNEYMAN, Work, required_rate
from data.payroll_world import determinations, periods
from data.payroll_world.cases import SeededSet
from data.payroll_world.corruptions import Label
from data.payroll_world.lifecycle import Case, Status
from data.payroll_world.periods import Period
from data.payroll_world.records import label_record
from data.payroll_world.world import World
from data.payroll_world.worlds import GARDEN_STATE, LINCOLN, NOTICE_CASE

QUESTIONS = (
    "Which subs on the Lincoln School renovation have open exceptions?",
    "How much underpayment have we flagged for Garden State Electric this month?",
    "Which payrolls are late or missing for last week?",
    "What's the journeyman electrician rate in Middlesex County in our rate table, "
    "and since when?",
    "Show me every worker whose classification changed in the last four weeks.",
    "Draft a send-back notice for PC-0311 covering all three exceptions.",
)
LAST_WEEKS = 4
# The file the generator writes them to, in data/.
COPILOT_EXPECTED = "copilot_expected.json"
# Read from the hand-written filing rules alone, so the generator runs before the
# files it writes exist.
DUE_DAYS: int = read_yaml(FILING_RULES)["due_days"]
ELECTRICIAN = "electrician"


class Answers:
    """The development set as one reviewer sees it after seeding."""

    def __init__(self, world: World, seeded: SeededSet, reviewer: str):
        self.world = world
        self.seeded = seeded
        self.projects = [p.id for p in world.spec.projects if p.reviewer == reviewer]
        self.cases = [
            c for c in seeded.cases if c.filing.engagement.project_id in self.projects
        ]
        self.by_week = {
            (c.filing.engagement.pair, c.filing.week): c for c in seeded.cases
        }

    def open_exceptions(self, case: Case) -> list[Label]:
        """The exceptions open on a case's latest submission: its labels while it is
        Returned to sub on its first submission, and none on a corrected or a
        Received case."""
        if case.status != Status.RETURNED:
            return []
        return [label for label in self.seeded.labels if label.case_id == case.case_id]

    def in_period(self, period: Period) -> list[Case]:
        return [c for c in self.cases if period.holds(c.filing.week_ending)]

    def open_by_subcontractor(self, project_id: str) -> dict[str, Any]:
        found: dict[str, dict[str, Any]] = {}
        for case in self.cases:
            exceptions = self.open_exceptions(case)
            if case.filing.engagement.project_id == project_id and exceptions:
                sub = self.world.subcontractor(case.filing.engagement.subcontractor_id)
                entry = found.setdefault(
                    sub.id,
                    {
                        "subcontractor_id": sub.id,
                        "name": sub.legal_name,
                        "case_ids": [],
                        "open_exceptions": 0,
                    },
                )
                entry["case_ids"].append(case.case_id)
                entry["open_exceptions"] += len(exceptions)
        return {"project_id": project_id, "subcontractors": list(found.values())}

    def flagged(self, subcontractor_id: str, period: Period) -> dict[str, Any]:
        """The money exceptions not dismissed on the latest submissions of a
        subcontractor's cases in the period, flagged, and those still open on cases
        Awaiting review or Returned to sub, outstanding. After seeding no case
        awaits review and every open exception is on a case Returned to sub, so
        the two are the same."""
        exceptions = [
            label
            for case in self.in_period(period)
            if case.filing.engagement.subcontractor_id == subcontractor_id
            for label in self.open_exceptions(case)
            if label.expected_shortfall_cents is not None
        ]
        return {
            "subcontractor_id": subcontractor_id,
            "period": period.record(),
            "case_ids": sorted({label.case_id for label in exceptions}),
            "flagged_cents": money(exceptions),
            "outstanding_cents": money(exceptions),
            "exceptions": [label_record(label) for label in exceptions],
        }

    def late_or_missing(self, period: Period) -> dict[str, Any]:
        """The cases in the period whose filing, their first submission, was
        received more than the due days after its wage payment date (a correction
        doesn't make a filing late), and the expected filings in it with no case,
        none of them yet past its due date."""
        late = []
        for case in self.in_period(period):
            first = case.submissions[0]
            paid = first.payroll.certification.wage_payment_date
            if (first.received_on - paid).days > DUE_DAYS:
                late.append(
                    {
                        "case_id": case.case_id,
                        "subcontractor_id": case.filing.engagement.subcontractor_id,
                        "project_id": case.filing.engagement.project_id,
                        "wage_payment_date": paid.isoformat(),
                        "received_on": first.received_on.isoformat(),
                    }
                )
        missing = [
            {
                "subcontractor_id": filing.engagement.subcontractor_id,
                "project_id": filing.engagement.project_id,
                "week_ending": filing.week_ending.isoformat(),
            }
            for filing in self.seeded.missing
            if filing.engagement.project_id in self.projects
            and period.holds(filing.week_ending)
        ]
        return {"period": period.record(), "late": late, "missing": missing}

    def classification_changes(self, period: Period) -> list[dict[str, Any]]:
        """Every worker on a case in the period whose classification on its latest
        submission differs from their line the week before."""
        changes = []
        for case in self.in_period(period):
            before = self.by_week.get(
                (case.filing.engagement.pair, case.filing.week - 1)
            )
            if before is None:
                continue
            last = {ln.worker_id: ln for ln in before.submissions[-1].payroll.lines}
            for line in case.submissions[-1].payroll.lines:
                earlier = last.get(line.worker_id)
                if earlier and earlier.classification != line.classification:
                    changes.append(
                        {
                            "case_id": case.case_id,
                            "worker_id": line.worker_id,
                            "worker_name": line.worker_name,
                            "week_ending": case.filing.week_ending.isoformat(),
                            "from": earlier.classification,
                            "to": line.classification,
                            "line_notes": line.line_notes,
                        }
                    )
        return changes

    def case_exceptions(self, case_id: str) -> dict[str, Any]:
        [case] = [c for c in self.cases if c.case_id == case_id]
        exceptions = self.open_exceptions(case)
        return {
            "case_id": case_id,
            "status": case.status.value,
            "exceptions": [label_record(label) for label in exceptions],
            "shortfall_cents": money(exceptions),
        }


def money(labels: list[Label]) -> int:
    """The shortfalls of the labels that leave money owed, together."""
    return sum(
        label.expected_shortfall_cents
        for label in labels
        if label.expected_shortfall_cents is not None
    )


def rate_answer(world: World, project_id: str, craft: str) -> dict[str, Any]:
    """The journeyman rate the project's award-date determination gives on the
    business date, and the row it comes from."""
    project = world.project(project_id)
    work = Work(craft, JOURNEYMAN, project.county, project.award_date)
    rate = required_rate(determinations.RATES, work, world.spec.business_date)
    return {
        "craft": craft,
        "classification": JOURNEYMAN,
        "county": project.county,
        "project_id": project_id,
        "award_date": project.award_date.isoformat(),
        "determination_id": rate.determination.id,
        "effective": rate.row.effective.isoformat(),
        "wage_cents": rate.row.wage,
        "fringe_cents": rate.row.fringe,
        "total_cents": rate.row.total,
        "source": file_source(RATE_DETERMINATIONS, determinations.SOURCE),
    }


def expected_answers(world: World, seeded: SeededSet, reviewer: str) -> dict[str, Any]:
    """The six questions with the case ids, totals and rate record each answer must
    give, for the reviewer's scope at the business date."""
    answers = Answers(world, seeded, reviewer)
    business_date = world.spec.business_date
    four_weeks = periods.last_weeks(business_date, LAST_WEEKS)
    return {
        "notice": SYNTHETIC,
        "business_date": business_date.isoformat(),
        "reviewer": reviewer,
        "projects": answers.projects,
        "answers": [
            {"question": question, "answer": answer}
            for question, answer in zip(
                QUESTIONS,
                (
                    answers.open_by_subcontractor(LINCOLN),
                    answers.flagged(GARDEN_STATE, periods.this_month(business_date)),
                    answers.late_or_missing(periods.last_week(business_date)),
                    rate_answer(world, LINCOLN, ELECTRICIAN),
                    {
                        "period": four_weeks.record(),
                        "changes": answers.classification_changes(four_weeks),
                    },
                    answers.case_exceptions(NOTICE_CASE),
                ),
                strict=True,
            )
        ],
    }


def read_expected(data: Path) -> dict[str, Any]:
    """The expected answers as the generator wrote them in the data folder."""
    return json.loads((data / COPILOT_EXPECTED).read_text(encoding="utf-8"))


def answer_to(expected: dict[str, Any], number: int) -> dict[str, Any]:
    """The expected answer to the question of this number, from 1."""
    [answer] = [
        a["answer"]
        for a in expected["answers"]
        if a["question"] == QUESTIONS[number - 1]
    ]
    return answer
