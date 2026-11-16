"""What the check tools read for a case, from the app's records and the context
layer's lookups: the app's JSON read into the checks' plain data, and each lookup
asked once. It fetches them on the payroll agent's route; the tests give it the
records and the lookups in process."""

from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from langchain_core.tools import ToolException

from agent.app_operations import (
    GET_CASE,
    GET_PAYROLL_HISTORY,
    GET_PROJECT,
    LIST_SUBCONTRACTORS,
)
from agent.checks.inputs import (
    Certification,
    CheckInputs,
    DayRate,
    FilingRule,
    Line,
    LineInputs,
    Registration,
    Requirement,
    week_days,
)
from agent.context_tools import (
    CHECK_APPRENTICE,
    CHECK_REGISTRATION,
    GET_FILING_RULES,
    GET_WAGE_RATE,
)
from agent.routes import Route, Target
from context import wage_rules
from context.wage_rules import APPRENTICE, JOURNEYMAN, Row

# A lookup on the context layer: a tool's name and its arguments, and its answer.
Lookup = Callable[[str, dict[str, Any]], dict[str, Any]]


class LookupRefused(Exception):
    """A lookup the context layer refused, with its reason."""


def read_certification(found: dict[str, Any]) -> Certification:
    signed_on = found["signed_on"]
    return Certification(
        found["contractor_name"],
        found["fein"],
        found["registration_no"],
        found["project_id"],
        found["payroll_no"],
        date.fromisoformat(found["week_ending"]),
        date.fromisoformat(found["wage_payment_date"]),
        found["signed_by"],
        date.fromisoformat(signed_on) if signed_on else None,
        found["no_work_week"],
        found["payroll_notes"],
    )


def read_line(found: dict[str, Any]) -> Line:
    return Line(
        found["worker_id"],
        found["worker_name"],
        found["classification"],
        tuple(Decimal(h) for h in found["hours"]),
        Decimal(found["total_hours"]),
        found["base_rate"],
        found["fringe_rate"],
        found["fringe_cash"],
        Decimal(found["overtime_hours"]),
        found["gross"],
        found["line_notes"],
    )


def craft_of(classification: str) -> tuple[str, str] | None:
    """The craft and classification a line's classification names, such as
    "Operating Engineer Apprentice", or none when it names neither."""
    if " " not in classification:
        return None
    name, kind = classification.rsplit(" ", 1)
    return name.lower().replace(" ", "_"), kind.lower()


class Reader:
    """Reads what the checks need for one case's week, asking each lookup once."""

    def __init__(
        self,
        project: dict[str, Any],
        week_ending: date,
        workers: dict[str, dict[str, Any]],
        last_week: dict[str, str],
        lookup: Lookup,
    ):
        self.county = project["county"]
        self.award_date = project["award_date"]
        self.week_ending = week_ending
        self.workers = workers
        self.last_week = last_week
        self.lookup = lookup
        self.answers: dict[tuple[str, tuple[tuple[str, Any], ...]], dict[str, Any]] = {}

    def ask(self, tool: str, **arguments: Any) -> dict[str, Any]:
        key = (tool, tuple(sorted(arguments.items())))
        if key not in self.answers:
            self.answers[key] = self.lookup(tool, arguments)
        return self.answers[key]

    def level(self, worker_id: str, day: date) -> int | None:
        found = self.ask(CHECK_APPRENTICE, worker_id=worker_id, date=day.isoformat())
        return found["level"] if found["registered"] else None

    def wage_rate(self, craft: str, classification: str, day: date) -> dict[str, Any]:
        return self.ask(
            GET_WAGE_RATE,
            craft=craft,
            classification=classification,
            county=self.county,
            award_date=self.award_date,
            work_date=day.isoformat(),
        )

    def requirement(
        self,
        worker_id: str,
        craft: str,
        classification: str,
        worked: list[date],
    ) -> Requirement | None:
        """What each work day requires paid as this craft and classification: an
        apprentice at their registered level, or the journeyman rate on a day they
        aren't registered. None when the rate determinations don't have it."""
        apprentice = classification == APPRENTICE
        asked = JOURNEYMAN if apprentice else classification
        try:
            answers = {day: self.wage_rate(craft, asked, day) for day in worked}
            entry = next(iter(answers.values()), None) or self.wage_rate(
                craft, asked, self.week_ending
            )
        except LookupRefused:
            return None
        craft_rules = wage_rules.craft_rules(entry["craft_rules"])
        rates = {}
        for day, answer in answers.items():
            row = answer["row"]
            found = DayRate(
                answer["determination"]["id"],
                date.fromisoformat(row["effective"]),
                row["wage_cents"],
                row["fringe_cents"],
            )
            level = self.level(worker_id, day) if apprentice else None
            if level is not None:
                wage, fringe = wage_rules.apprentice_rate(
                    craft_rules, Row(found.effective, found.wage, found.fringe), level
                )
                found = DayRate(found.determination_id, found.effective, wage, fringe)
            rates[day] = found
        table = wage_rules.rate_table(
            {
                "crafts": [entry["craft_rules"]],
                "determinations": [],
                "holidays": entry["holidays"],
                "weekly_overtime_floor": entry["weekly_overtime_floor"],
            }
        )
        return Requirement(craft, classification, craft_rules.name, rates, table)

    def line_inputs(self, line_no: int, found: dict[str, Any]) -> LineInputs:
        line = read_line(found)
        days = tuple(zip(week_days(self.week_ending), line.hours, strict=True))
        worked = [day for day, hours in days if hours]
        named = craft_of(line.classification)
        claimed = self.requirement(line.worker_id, *named, worked) if named else None
        worker = self.workers.get(line.worker_id)
        established = (
            self.requirement(
                line.worker_id, worker["craft"], worker["classification"], worked
            )
            if worker
            else None
        )
        apprentice = claimed is not None and claimed.classification == APPRENTICE
        levels = (
            {day: self.level(line.worker_id, day) for day in worked}
            if apprentice
            else {}
        )
        return LineInputs(
            line_no,
            line,
            days,
            claimed,
            established,
            levels,
            self.last_week.get(line.worker_id),
        )

    def registration(self, registration_no: str, day: date) -> Registration:
        try:
            found = self.ask(
                CHECK_REGISTRATION,
                registration_no=registration_no,
                date=day.isoformat(),
            )
        except LookupRefused as refused:
            return Registration(False, f"Contractor registry: {refused}")
        period = (
            f"period {found['effective']} to {found['expiry']}"
            if found["effective"]
            else "no period"
        )
        return Registration(
            found["status"] == "active",
            f"Contractor registry {registration_no}, {found['holder']}: {period}",
        )

    def filing_rules(self) -> tuple[int, dict[str, FilingRule]]:
        found = self.ask(GET_FILING_RULES)
        rules = {r["rule"]: FilingRule(r["name"], r["cites"]) for r in found["rules"]}
        return found["due_days"], rules


def latest_submission(case: dict[str, Any]) -> dict[str, Any]:
    [found] = [
        s
        for s in case["submissions"]
        if s["submission_no"] == case["latest_submission_no"]
    ]
    return found


def last_week_classifications(
    history: list[dict[str, Any]], week_ending: date
) -> dict[str, str]:
    """Each worker's classification on last week's latest submission."""
    before = (week_ending - timedelta(days=7)).isoformat()
    return {
        line["worker_id"]: line["classification"]
        for payroll in history
        if payroll["week_ending"] == before
        for line in payroll["lines"]
    }


def read_inputs(
    case: dict[str, Any],
    project: dict[str, Any],
    subcontractors: list[dict[str, Any]],
    history: list[dict[str, Any]],
    lookup: Lookup,
) -> CheckInputs:
    """What the checks read for a case's latest submission, from the app's case,
    project, the project's subcontractors and the case's payroll history, and the
    context layer's lookups."""
    submission = latest_submission(case)
    certification = read_certification(submission["certification"])
    week_ending = date.fromisoformat(case["week_ending"])
    [subcontractor] = [
        s for s in subcontractors if s["subcontractor_id"] == case["subcontractor_id"]
    ]
    workers = {w["worker_id"]: w for w in case["workers"]}
    last_week = last_week_classifications(history, week_ending)
    reader = Reader(project, week_ending, workers, last_week, lookup)
    lines = tuple(
        reader.line_inputs(n, found)
        for n, found in enumerate(submission["lines"], start=1)
    )
    worked = sorted({day for found in lines for day in found.worked})
    registration_no = subcontractor["registration_no"]
    due_days, filing_rules = reader.filing_rules()
    return CheckInputs(
        case["case_id"],
        case["project_id"],
        week_ending,
        date.fromisoformat(submission["received_on"]),
        certification,
        lines,
        subcontractor["legal_name"],
        subcontractor["fein"],
        registration_no,
        date.fromisoformat(subcontractor["first_week_ending"]),
        {day: reader.registration(registration_no, day) for day in worked},
        due_days,
        filing_rules,
    )


def on_route(route: Route) -> Lookup:
    """The context layer's lookups on the payroll agent's route, a refusal raised
    as LookupRefused."""

    def lookup(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            return route.call(Target.CONTEXT, tool, arguments)
        except ToolException as refused:
            raise LookupRefused(str(refused)) from refused

    return lookup


def fetch_inputs(route: Route, case_id: str) -> CheckInputs:
    """What the checks read for a case, from the app and the context layer on the
    payroll agent's route."""
    case = route.call(Target.APP, GET_CASE, {"case_id": case_id})
    project = {"project_id": case["project_id"]}
    history = route.call(Target.APP, GET_PAYROLL_HISTORY, {"case_id": case_id})
    return read_inputs(
        case,
        route.call(Target.APP, GET_PROJECT, project),
        route.call(Target.APP, LIST_SUBCONTRACTORS, project),
        history["payrolls"],
        on_route(route),
    )
