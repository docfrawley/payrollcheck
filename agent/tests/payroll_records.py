"""The committed payroll records as the app gives them to the check tools, built
from data/'s files, and the context layer's lookups called in process: what the
check tools' tests read a case through."""

import json
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from agent.check_inputs import (
    CHECK_APPRENTICE,
    CHECK_REGISTRATION,
    GET_FILING_RULES,
    GET_WAGE_RATE,
    LookupRefused,
    read_inputs,
)
from agent.checks.inputs import CheckInputs
from context import payroll_files
from context.sources import Refused
from data.payroll_world.template import payroll_record, read_payroll

DATA = Path(__file__).parents[2] / "data"
SETS = {
    "development": (DATA / "development", DATA / "error_manifest.yaml"),
    "held_out": (DATA / "held_out", DATA / "held_out_manifest.yaml"),
}
LABELS = {
    "development": DATA / "evals" / "development_labels.json",
    "held_out": DATA / "evals" / "held_out_labels.json",
}
LOOKUPS = {
    GET_WAGE_RATE: payroll_files.get_wage_rate,
    CHECK_REGISTRATION: payroll_files.check_registration,
    CHECK_APPRENTICE: payroll_files.check_apprentice,
    GET_FILING_RULES: payroll_files.get_filing_rules,
}
DATES = ("award_date", "work_date", "date")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def lookup(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """A context layer lookup, called in process as its server would."""
    given = {
        name: date.fromisoformat(value) if name in DATES else value
        for name, value in arguments.items()
    }
    if "date" in given:
        given["day"] = given.pop("date")
    try:
        return LOOKUPS[tool](**given)
    except Refused as refused:
        raise LookupRefused(str(refused)) from refused


class Records:
    """One labelled set's records, as the app holds them."""

    def __init__(self, name: str):
        folder, manifest = SETS[name]
        self.folder = folder
        self.world = read_json(folder / "world.json")
        self.subcontractors = read_json(folder / "subcontractors.json")
        self.workers = read_json(folder / "workers.json")
        self.cases = {c["case_id"]: c for c in read_json(folder / "cases.json")}
        seeded = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        self.decoys = seeded["decoys"]
        self.hidden_instructions = seeded["hidden_instructions"]

    def submission(self, case_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        text = (self.folder / "payrolls" / entry["file"]).read_text(encoding="utf-8")
        return {
            "submission_no": entry["number"],
            "received_on": entry["received_on"],
            **payroll_record(read_payroll(text)),
        }

    def case(self, case_id: str, submission_no: int) -> dict[str, Any]:
        """The case with its submissions up to this one, as the app gives it."""
        found = self.cases[case_id]
        return {
            "case_id": case_id,
            "project_id": found["project_id"],
            "subcontractor_id": found["subcontractor_id"],
            "week_ending": found["week_ending"],
            "latest_submission_no": submission_no,
            "submissions": [
                self.submission(case_id, s)
                for s in found["submissions"]
                if s["number"] <= submission_no
            ],
            "workers": [
                {k: w[k] for k in ("worker_id", "name", "craft", "classification")}
                for w in self.workers
                if w["subcontractor_id"] == found["subcontractor_id"]
            ],
        }

    def project(self, project_id: str) -> dict[str, Any]:
        [found] = [p for p in self.world["projects"] if p["project_id"] == project_id]
        return found

    def project_subcontractors(self, project_id: str) -> list[dict[str, Any]]:
        records = {s["subcontractor_id"]: s for s in self.subcontractors}
        return [
            records[e["subcontractor_id"]] | e
            for e in self.project(project_id)["subcontractors"]
        ]

    def history(self, case_id: str) -> list[dict[str, Any]]:
        """The latest submission of each earlier week of the same subcontractor and
        project."""
        found = self.cases[case_id]
        earlier = [
            c
            for c in self.cases.values()
            if c["subcontractor_id"] == found["subcontractor_id"]
            and c["project_id"] == found["project_id"]
            and c["week_ending"] < found["week_ending"]
        ]
        return [
            {
                "case_id": c["case_id"],
                "week_ending": c["week_ending"],
                **self.submission(c["case_id"], c["submissions"][-1]),
            }
            for c in earlier
        ]

    def inputs(
        self, case_id: str, submission_no: int = 1, edit: Any = None
    ) -> CheckInputs:
        """What the checks read for one submission, after an edit of the case."""
        case = self.case(case_id, submission_no)
        if edit:
            edit(case)
        project_id = case["project_id"]
        return read_inputs(
            case,
            self.project(project_id),
            self.project_subcontractors(project_id),
            self.history(case_id),
            lookup,
        )


@cache
def records(name: str) -> Records:
    return Records(name)


@cache
def labels(name: str) -> list[dict[str, Any]]:
    return read_json(LABELS[name])["exceptions"]
