"""A world and its cases as the files seeding loads, and the world's registrations
as the context layer's registry and apprentice files."""

from typing import Any

from context.sources import SYNTHETIC
from data.payroll_world.cases import SeededSet
from data.payroll_world.lifecycle import Case
from data.payroll_world.reference import source
from data.payroll_world.world import World

REGISTRY_SOURCE = source("NJDOL public works contractor registry, as we record it")
APPRENTICES_SOURCE = source(
    "USDOL registered apprenticeship records, as we record them"
)
REGISTRY_ABOUT = (
    "Every subcontractor's public works contractor registration, with the periods it "
    "was active."
)
APPRENTICES_ABOUT = (
    "The registered apprentices on our projects, by worker id, with their sponsor, "
    "program and level by date. A worker who isn't here isn't registered."
)


def payroll_file(case_id: str, number: int) -> str:
    return f"{case_id}-{number}.csv"


def world_record(world: World) -> dict[str, Any]:
    """The business date, the weeks and the projects, each with its subcontractors'
    engagement windows."""
    spec = world.spec
    return {
        "notice": SYNTHETIC,
        "business_date": spec.business_date.isoformat(),
        "weeks": [
            {"week": week, "week_ending": world.week_ending(week).isoformat()}
            for week in range(1, spec.weeks + 1)
        ],
        "projects": [
            {
                "project_id": project.id,
                "name": project.name,
                "county": project.county,
                "location": project.location,
                "public_body": project.public_body,
                "contract_no": project.contract_no,
                "award_date": project.award_date.isoformat(),
                "reviewer": project.reviewer,
                "subcontractors": [
                    {
                        "subcontractor_id": e.subcontractor_id,
                        "first_week": e.first_week,
                        "last_week": e.last_week,
                        "first_week_ending": world.week_ending(
                            e.first_week
                        ).isoformat(),
                        "last_week_ending": world.week_ending(e.last_week).isoformat(),
                    }
                    for e in world.engagements
                    if e.project_id == project.id
                ],
            }
            for project in spec.projects
        ],
    }


def subcontractors_record(world: World) -> list[dict[str, Any]]:
    return [
        {
            "subcontractor_id": sub.id,
            "legal_name": sub.legal_name,
            "fein": sub.fein,
            "registration_no": sub.registration_no,
            "payroll_contact": {"name": sub.contact_name, "email": sub.contact_email},
        }
        for sub in world.subcontractors
    ]


def workers_record(world: World) -> list[dict[str, Any]]:
    """Each worker with their established craft and classification."""
    pairs = {e.pair: e for e in world.engagements}
    return [
        {
            "worker_id": worker.id,
            "name": worker.name,
            "subcontractor_id": pairs[worker.pair].subcontractor_id,
            "project_id": pairs[worker.pair].project_id,
            "craft": worker.craft,
            "classification": worker.classification,
        }
        for worker in world.workers
    ]


def cases_record(cases: tuple[Case, ...]) -> list[dict[str, Any]]:
    def day(found):
        return found.isoformat() if found else None

    return [
        {
            "case_id": case.case_id,
            "project_id": case.filing.engagement.project_id,
            "subcontractor_id": case.filing.engagement.subcontractor_id,
            "week": case.filing.week,
            "week_ending": case.filing.week_ending.isoformat(),
            "status": case.status.value,
            "reviewer": case.reviewer,
            "returned_on": day(case.returned_on),
            "accepted_on": day(case.accepted_on),
            "submissions": [
                {
                    "number": submission.number,
                    "file": payroll_file(case.case_id, submission.number),
                    "received_on": submission.received_on.isoformat(),
                }
                for submission in case.submissions
            ],
        }
        for case in cases
    ]


def labels_record(seeded: SeededSet) -> dict[str, Any]:
    """The ground-truth labels: every exception a perfect review finds, by case,
    and the cases it flags for a hidden instruction."""
    return {
        "notice": SYNTHETIC,
        "exceptions": [
            {
                "case_id": label.case_id,
                "rule": label.rule,
                "worker_id": label.worker_id,
                "line_no": label.line_no,
                "expected_shortfall_cents": label.expected_shortfall_cents,
            }
            for label in seeded.labels
        ],
        "screening_flags": list(seeded.screening_flags),
    }


def registry_record(worlds: list[World]) -> dict[str, Any]:
    return {
        "source": REGISTRY_SOURCE,
        "notice": SYNTHETIC,
        "registrations": [
            {
                "registration_no": r.registration_no,
                "holder": r.legal_name,
                "fein": r.fein,
                "periods": [
                    {"effective": start.isoformat(), "expiry": end.isoformat()}
                    for start, end in r.periods
                ],
            }
            for world in worlds
            for r in world.registrations
        ],
    }


def apprentices_record(worlds: list[World]) -> dict[str, Any]:
    names = {w.id: w for world in worlds for w in world.workers}
    return {
        "source": APPRENTICES_SOURCE,
        "notice": SYNTHETIC,
        "apprentices": [
            {
                "worker_id": a.worker_id,
                "name": names[a.worker_id].name,
                "craft": names[a.worker_id].craft,
                "sponsor": a.sponsor,
                "program": a.program,
                "registered_on": a.registered_on.isoformat(),
                "levels": [
                    {"level": level, "from": start.isoformat()}
                    for level, start in a.levels
                ],
            }
            for world in worlds
            for a in world.apprentices
        ],
    }
