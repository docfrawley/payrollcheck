"""Seeding: the database built afresh from data/, recomputing nothing. It loads the
development world and the held-out world's records, the development set's history
and its week-12 wave, the labelled sets and their labels, the settings with the
business date, and version 1 of the configuration and of the recipe."""

import json
from typing import Any

from sqlalchemy import Connection, Engine, MetaData, Table, insert
from sqlalchemy.schema import CreateSchema, DropSchema

from backend.database import (
    AGENTS_WORK,
    ROOT,
    SCHEMA,
    SCREENING,
    cases,
    engagements,
    exceptions,
    labelled_cases,
    labels,
    locks,
    metadata,
    models_allowed,
    now,
    on_postgres,
    projects,
    recipes,
    reviewers,
    settings,
    subcontractors,
    submissions,
    versions,
    workers,
)
from backend.first_version import (
    FIRST_MODEL,
    FIRST_RECIPE,
    FIRST_VERSION,
    INSTRUCTIONS,
)
from backend.free_models import model_or_free, models_or_free
from backend.models import (
    ExceptionStatus,
    LabelledSet,
    ModelAllowed,
    SettingsValues,
    Status,
)
from backend.rule_codes import RULES
from data.payroll_world.template import payroll_record, read_payroll

DATA = ROOT / "data"
FOLDERS = {LabelledSet.DEVELOPMENT: "development", LabelledSet.HELD_OUT: "held_out"}
LABEL_FILES = {
    LabelledSet.DEVELOPMENT: "evals/development_labels.json",
    LabelledSet.HELD_OUT: "evals/held_out_labels.json",
}
TINY_LABELS = "evals/tiny_labels.json"
PAYROLLS = "payrolls"
# The statuses the generator writes, as the app keeps them.
STATUSES = {
    "Received": Status.RECEIVED,
    "Accepted": Status.ACCEPTED,
    "Returned to sub": Status.RETURNED_TO_SUB,
}
# Tables of earlier versions, dropped before the others, since on Postgres a foreign
# key of theirs would stop the tables they refer to being dropped.
RETIRED = [
    "todos",
    "grades",
    "payments",
    "calculations",
    "sent_back_decisions",
    "decisions",
    "reviewer_decisions",
    "held_out_cases",
    "policies",
    "payout_rules",
    "documents",
]
# The schema of an earlier version, under the product's old name, dropped with all it
# holds, the checkpointer's tables included.
RETIRED_SCHEMA = "undercover"


def load(name: str) -> Any:
    """Read one of the JSON files in data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class World:
    """One labelled set's world as data/ holds it, with its reviewers' ids by email."""

    def __init__(self, labelled_set: LabelledSet, reviewer_ids: dict[str, str]):
        self.folder = FOLDERS[labelled_set]
        self.held_out = labelled_set == LabelledSet.HELD_OUT
        self.world = load(f"{self.folder}/world.json")
        self.subcontractors = load(f"{self.folder}/subcontractors.json")
        self.workers = load(f"{self.folder}/workers.json")
        self.cases = load(f"{self.folder}/cases.json")
        self.reviewer_ids = reviewer_ids
        self.read: dict[str, list[dict[str, Any]]] = {}

    def submission(self, case: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
        """A submission as the app keeps it, uploaded by the project's reviewer on
        the day it was received."""
        text = (DATA / self.folder / PAYROLLS / entry["file"]).read_text(
            encoding="utf-8"
        )
        payroll = read_payroll(text)
        [project] = [
            p for p in self.world["projects"] if p["project_id"] == case["project_id"]
        ]
        return {
            "case_id": case["case_id"],
            "submission_no": entry["number"],
            "uploaded_by": self.reviewer_ids[project["reviewer"]],
            "uploaded_at": entry["received_on"],
            "received_on": entry["received_on"],
            "file_name": entry["file"],
            "payroll_no": payroll.certification.payroll_no,
            "wage_payment_date": payroll.certification.wage_payment_date.isoformat(),
            **payroll_record(payroll),
        }

    def submissions_of(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        """A case's submissions, each read from its CSV once."""
        if case["case_id"] not in self.read:
            self.read[case["case_id"]] = [
                self.submission(case, entry) for entry in case["submissions"]
            ]
        return self.read[case["case_id"]]


def seed_records(connection: Connection, world: World) -> None:
    """A world's projects, subcontractors, engagements and workers."""
    held_out = world.held_out
    connection.execute(
        insert(projects),
        [
            {
                **{k: p[k] for k in ("project_id", "name", "county", "location")},
                "public_body": p["public_body"],
                "contract_no": p["contract_no"],
                "award_date": p["award_date"],
                "held_out": held_out,
            }
            for p in world.world["projects"]
        ],
    )
    connection.execute(
        insert(subcontractors),
        [
            {
                "subcontractor_id": s["subcontractor_id"],
                "legal_name": s["legal_name"],
                "fein": s["fein"],
                "registration_no": s["registration_no"],
                "contact_name": s["payroll_contact"]["name"],
                "contact_email": s["payroll_contact"]["email"],
                "held_out": held_out,
            }
            for s in world.subcontractors
        ],
    )
    connection.execute(
        insert(engagements),
        [
            {
                "project_id": p["project_id"],
                "subcontractor_id": e["subcontractor_id"],
                "pair": e["pair"],
                "first_week_ending": e["first_week_ending"],
                "last_week_ending": e["last_week_ending"],
            }
            for p in world.world["projects"]
            for e in p["subcontractors"]
        ],
    )
    connection.execute(
        insert(workers),
        [
            {
                **{k: w[k] for k in ("worker_id", "name", "subcontractor_id")},
                "craft": w["craft"],
                "classification": w["classification"],
                "held_out": held_out,
            }
            for w in world.workers
        ],
    )


def reviewed_on(case: dict[str, Any]) -> str | None:
    return case["accepted_on"] or case["returned_on"]


def seed_queue(connection: Connection, world: World) -> list[dict[str, Any]]:
    """The development set's cases as the generator recorded them, the history and
    week 12's wave, each with its submissions, and return them."""
    connection.execute(
        insert(cases),
        [
            {
                **{k: c[k] for k in ("case_id", "subcontractor_id", "project_id")},
                "week_ending": c["week_ending"],
                "status": STATUSES[c["status"]],
                "screening_flag": False,
                "agent_failed": False,
                "latest_submission_no": len(c["submissions"]),
                "attempts": 0,
                "reviewed_by": c["reviewer"] and world.reviewer_ids[c["reviewer"]],
                "reviewed_on": reviewed_on(c),
            }
            for c in world.cases
        ],
    )
    connection.execute(
        insert(submissions),
        [s for c in world.cases for s in world.submissions_of(c)],
    )
    return world.cases


def history_exceptions(
    connection: Connection,
    history: list[dict[str, Any]],
    found: list[dict[str, Any]],
    names: dict[str, str],
) -> None:
    """The history's exceptions, from the labels, on each decided case's first
    submission, raised by the reviewer who decided it: superseded on a case with a
    correction, open on one still Returned to sub."""
    decided = {c["case_id"]: c for c in history if c["status"] != "Received"}
    rows = []
    for label in found:
        case = decided.get(label["case_id"])
        if case is None:
            continue
        rule = RULES[label["rule"]]
        corrected = len(case["submissions"]) > 1
        rows.append(
            {
                "case_id": case["case_id"],
                "submission_no": 1,
                "rule": label["rule"],
                "severity": rule.severity,
                "worker_id": label["worker_id"],
                "line_no": label["line_no"],
                "expected": "",
                "actual": "",
                "shortfall_cents": label["expected_shortfall_cents"],
                "citation": rule.cites,
                "raised_by": names[case["reviewer"]],
                "status": ExceptionStatus.SUPERSEDED
                if corrected
                else ExceptionStatus.OPEN,
            }
        )
    if rows:
        connection.execute(insert(exceptions), rows)


def seed_labelled_set(
    connection: Connection, world: World, labelled_set: LabelledSet
) -> list[dict[str, Any]]:
    """A labelled set's cases with their submissions as the generator wrote them,
    the tiny ones marked, and their labels, which are returned."""
    tiny = set(load(TINY_LABELS)["cases"])
    connection.execute(
        insert(labelled_cases),
        [
            {
                "labelled_set": labelled_set,
                **{k: c[k] for k in ("case_id", "project_id", "subcontractor_id")},
                "week_ending": c["week_ending"],
                "tiny": labelled_set == LabelledSet.DEVELOPMENT
                and c["case_id"] in tiny,
                "submissions": [
                    {k: v for k, v in s.items() if k != "case_id"}
                    for s in world.submissions_of(c)
                ],
                "before_review": len(c["submissions"])
                if c["status"] == "Received"
                else 1,
            }
            for c in world.cases
        ],
    )
    found = load(LABEL_FILES[labelled_set])
    rows = [
        {"labelled_set": labelled_set, **label} for label in found["exceptions"]
    ] + [
        {
            "labelled_set": labelled_set,
            "case_id": case_id,
            "rule": SCREENING,
            "worker_id": None,
            "line_no": None,
            "expected_shortfall_cents": None,
        }
        for case_id in found["screening_flags"]
    ]
    connection.execute(insert(labels), rows)
    return found["exceptions"]


def seed_settings(connection: Connection, business_date: str) -> None:
    """The first settings, from data/improvement.json, checked as the settings page
    checks a change, with the business date the development world names."""
    values = SettingsValues(**load("improvement.json"), business_date=business_date)
    connection.execute(
        insert(settings).values(number=1, **values.model_dump(), changed_at=now())
    )


def seed_models_allowed(connection: Connection) -> None:
    """The models the payroll agent may use, from data/models.json, or the free
    model alone for students on free models."""
    listed = [ModelAllowed(**model) for model in load("models.json")]
    connection.execute(
        insert(models_allowed),
        [
            model.model_dump() | {"position": position}
            for position, model in enumerate(models_or_free(listed))
        ],
    )


def seed_first_version(connection: Connection) -> None:
    """Version 1 of the payroll agent's configuration, from its instructions file,
    on GPT-6 Luna with no reasoning, or the free model for students on free
    models, with the check tools' first parameters."""
    model, reasoning_effort = model_or_free(*FIRST_MODEL)
    connection.execute(
        insert(versions).values(
            **FIRST_VERSION,
            instructions=(INSTRUCTIONS / "payroll.md").read_text(encoding="utf-8"),
            model=model,
            reasoning_effort=reasoning_effort,
            created_at=now(),
        )
    )
    recipe = (INSTRUCTIONS / "recipe.md").read_text(encoding="utf-8")
    connection.execute(
        insert(recipes).values(**FIRST_RECIPE, recipe=recipe, created_at=now())
    )


def rebuild(connection: Connection, on_postgres_: bool) -> None:
    """Drop every table, of this version and earlier ones, and make them afresh."""
    if on_postgres_:
        connection.execute(DropSchema(RETIRED_SCHEMA, cascade=True, if_exists=True))
        connection.execute(CreateSchema(SCHEMA, if_not_exists=True))
    for name in RETIRED:
        Table(name, MetaData()).drop(connection, checkfirst=True)
    metadata.drop_all(connection)
    metadata.create_all(connection)


def seed(db: Engine) -> dict[str, int]:
    """Build the tables afresh from data/ and count what they hold."""
    people = load("reviewers.json")
    ids = {r["email"]: r["reviewer_id"] for r in people}
    names = {r["email"]: r["name"] for r in people}
    development = World(LabelledSet.DEVELOPMENT, ids)
    held_out = World(LabelledSet.HELD_OUT, ids)
    with db.begin() as connection:
        rebuild(connection, on_postgres(db.url))
        seed_settings(connection, development.world["business_date"])
        seed_models_allowed(connection)
        connection.execute(insert(reviewers), people)
        seed_records(connection, development)
        seed_records(connection, held_out)
        queue = seed_queue(connection, development)
        found = seed_labelled_set(connection, development, LabelledSet.DEVELOPMENT)
        held = seed_labelled_set(connection, held_out, LabelledSet.HELD_OUT)
        history_exceptions(connection, queue, found, names)
        seed_first_version(connection)
        connection.execute(insert(locks).values(name=AGENTS_WORK))
    return {
        "cases": len(queue),
        "projects": len(development.world["projects"]),
        "subcontractors": len(development.subcontractors),
        "workers": len(development.workers),
        "reviewers": len(people),
        "development_cases": len(development.cases),
        "held_out_cases": len(held_out.cases),
        "labels": len(found) + len(held),
    }
