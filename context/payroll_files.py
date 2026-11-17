"""The context layer's payroll files, read once when the process starts: the rate
determinations, the contractor registry, the apprentice registrations, the filing
rules and the payroll glossary. Every answer holds its sources, the files it came
from with their system, owner and review date. It reads only from its own folder
and writes nothing."""

from datetime import date
from typing import Any

from context import registrations, wage_rules
from context.sources import (
    APPRENTICE_REGISTRATIONS,
    CONTRACTOR_REGISTRY,
    FILING_RULES,
    PAYROLL_GLOSSARY,
    RATE_DETERMINATIONS,
    Refused,
    read_yaml,
)

FILES: dict[str, dict[str, Any]] = {
    file: read_yaml(file)
    for file in (
        RATE_DETERMINATIONS,
        CONTRACTOR_REGISTRY,
        APPRENTICE_REGISTRATIONS,
        FILING_RULES,
        PAYROLL_GLOSSARY,
    )
}
RATES = wage_rules.rate_table(FILES[RATE_DETERMINATIONS])
# A payroll is due this many calendar days after its wages are paid.
DUE_DAYS: int = FILES[FILING_RULES]["due_days"]
CLASSIFICATIONS = tuple(
    dict.fromkeys(key[1] for found in RATES.determinations for key in found.rows)
)
COUNTIES = sorted(
    {d.area for d in RATES.determinations if d.area != wage_rules.STATEWIDE}
)
UNKNOWN_TERM = (
    'The payroll glossary doesn\'t define "{term}". These are the terms it does.'
)
APPRENTICE_RATES = (
    "An apprentice's rate is a percentage of the journeyman rate: ask for the "
    "journeyman rate, whose answer holds the craft's apprentice schedule."
)


def sources_of(file: str) -> list[dict[str, str]]:
    return [FILES[file]["source"]]


def craft_entry(craft: str) -> dict[str, Any]:
    [found] = [c for c in FILES[RATE_DETERMINATIONS]["crafts"] if c["craft"] == craft]
    return found


def refuse_unknown_rate(craft: str, classification: str, county: str) -> None:
    """Refuse a rate the table can't answer, before looking it up: an unknown
    craft or classification, an apprentice's, or a county with no determinations
    for a craft that isn't statewide."""
    if craft not in RATES.crafts:
        crafts = ", ".join(RATES.crafts)
        raise Refused(f"{wage_rules.UNKNOWN_NAMES[0]}{craft}. The crafts are {crafts}.")
    if classification == wage_rules.APPRENTICE:
        raise Refused(APPRENTICE_RATES)
    if classification not in CLASSIFICATIONS:
        known = ", ".join(CLASSIFICATIONS)
        unknown = wage_rules.UNKNOWN_NAMES[1]
        raise Refused(f"{unknown}{classification}. They are {known}.")
    if not RATES.crafts[craft].statewide and county not in COUNTIES:
        raise Refused(f"No county {county}. The counties are {', '.join(COUNTIES)}.")


def in_dollars(cents: int) -> str:
    """An amount in cents as a person reads it, such as $61.10."""
    return f"${cents / 100:,.2f}"


def get_wage_rate(
    craft: str, classification: str, county: str, award_date: date, work_date: date
) -> dict[str, Any]:
    """The rate for a day's work on a project: the determination in force on the
    project's award date and its latest row dated on or before the work date, with
    the craft's whole entry: its name, whether it is statewide, its overtime rules,
    apprentice schedule and ratio."""
    refuse_unknown_rate(craft, classification, county)
    work = wage_rules.Work(craft, classification, county, award_date)
    try:
        rate = wage_rules.required_rate(RATES, work, work_date)
    except LookupError as missing:
        raise Refused(str(missing)) from missing
    found, row = rate.determination, rate.row
    entry = craft_entry(craft)
    return {
        "determination": {
            "id": found.id,
            "area": found.area,
            "issued": found.issued.isoformat(),
        },
        "craft": craft,
        "classification": classification,
        "row": {
            "effective": row.effective.isoformat(),
            "wage_cents": row.wage,
            "fringe_cents": row.fringe,
            "total_cents": row.total,
            "wage": in_dollars(row.wage),
            "fringe": in_dollars(row.fringe),
            "total": in_dollars(row.total),
        },
        "craft_rules": entry,
        "weekly_overtime_floor": FILES[RATE_DETERMINATIONS]["weekly_overtime_floor"],
        "holidays": FILES[RATE_DETERMINATIONS]["holidays"],
        "sources": sources_of(RATE_DETERMINATIONS),
    }


def check_registration(registration_no: str, day: date) -> dict[str, Any]:
    """A public works contractor registration on a date: its holder, FEIN, the
    period it was in or the latest before it, and whether it was active."""
    found = [
        r
        for r in FILES[CONTRACTOR_REGISTRY]["registrations"]
        if r["registration_no"] == registration_no
    ]
    if not found:
        raise Refused(f"No registration {registration_no} in the registry")
    [registration] = found
    periods = [
        (date.fromisoformat(p["effective"]), date.fromisoformat(p["expiry"]))
        for p in registration["periods"]
    ]
    period = registrations.period_on(periods, day)
    active = registrations.active_on(periods, day)
    return {
        "registration_no": registration["registration_no"],
        "holder": registration["holder"],
        "fein": registration["fein"],
        "date": day.isoformat(),
        "effective": period[0].isoformat() if period else None,
        "expiry": period[1].isoformat() if period else None,
        "status": "active" if active else "not active",
        "sources": sources_of(CONTRACTOR_REGISTRY),
    }


def check_apprentice(worker_id: str, day: date) -> dict[str, Any]:
    """Whether a worker was a registered apprentice on a date and, if so, their
    sponsor and program and their level then, with its percentages of the
    journeyman rate."""
    found = [
        a
        for a in FILES[APPRENTICE_REGISTRATIONS]["apprentices"]
        if a["worker_id"] == worker_id
    ]
    unregistered = {
        "worker_id": worker_id,
        "date": day.isoformat(),
        "registered": False,
        "sources": sources_of(APPRENTICE_REGISTRATIONS),
    }
    if not found:
        return unregistered
    [apprentice] = found
    levels = [
        (lv["level"], date.fromisoformat(lv["from"])) for lv in apprentice["levels"]
    ]
    level = registrations.level_on(levels, day)
    if level is None:
        return unregistered | {"registered_on": apprentice["registered_on"]}
    schedule = RATES.crafts[apprentice["craft"]].apprentice_schedule[level]
    return {
        "worker_id": worker_id,
        "date": day.isoformat(),
        "registered": True,
        "name": apprentice["name"],
        "craft": apprentice["craft"],
        "sponsor": apprentice["sponsor"],
        "program": apprentice["program"],
        "registered_on": apprentice["registered_on"],
        "level": level,
        "wage_percent": schedule.wage_percent,
        "fringe_percent": schedule.fringe_percent,
        "sources": sources_of(APPRENTICE_REGISTRATIONS),
    }


def get_filing_rules() -> dict[str, Any]:
    """When a certified payroll is due, how payrolls are numbered and what a
    resubmission is."""
    rules = FILES[FILING_RULES]
    return {
        "due_days": DUE_DAYS,
        "rules": rules["rules"],
        "sources": sources_of(FILING_RULES),
    }


def lookup_payroll_term(term: str) -> dict[str, Any]:
    """A payroll term's definition, matched whatever its case, or, for a term the
    glossary doesn't define, the terms it does."""
    terms = FILES[PAYROLL_GLOSSARY]["terms"]
    for entry in terms:
        if entry["term"].lower() == term.strip().lower():
            return entry | {"sources": sources_of(PAYROLL_GLOSSARY)}
    return {
        "answer": UNKNOWN_TERM.format(term=term),
        "terms": [entry["term"] for entry in terms],
        "sources": sources_of(PAYROLL_GLOSSARY),
    }
