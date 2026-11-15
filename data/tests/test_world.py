"""The development world has the shape the brief asks for."""

from collections import Counter
from datetime import date

from context.wage_rules import APPRENTICE
from data.payroll_world.filings import filings
from data.tests.development_set import CASES, SEEDED, WORLD

LAPSED = "SUB-06"


def test_three_projects_in_three_counties_middlesex_among_them():
    counties = {project.county for project in WORLD.spec.projects}
    assert len(WORLD.spec.projects) == 3
    assert counties == {"Middlesex", "Monmouth", "Ocean"}


def test_eight_subcontractors_garden_state_electric_among_them():
    names = [sub.legal_name for sub in WORLD.subcontractors]
    assert len(names) == 8
    assert "Garden State Electric LLC" in names
    assert all(len(sub.registration_no) == 6 for sub in WORLD.subcontractors)
    assert all(sub.contact_email.endswith(".example") for sub in WORLD.subcontractors)
    assert len({sub.fein for sub in WORLD.subcontractors}) == 8


def test_about_60_workers_across_the_8_crafts_6_of_them_apprentices():
    assert 55 <= len(WORLD.workers) <= 65
    assert len({worker.craft for worker in WORLD.workers}) == 8
    apprentices = [w for w in WORLD.workers if w.classification == APPRENTICE]
    registered = [w for w in apprentices if WORLD.apprentice(w.id)]
    assert (len(apprentices), len(registered)) == (6, 5)
    [unregistered] = set(apprentices) - set(registered)
    worked = [
        case.filing.week
        for case in CASES
        if any(
            line.worker_id == unregistered.id
            for line in case.submissions[0].payroll.lines
        )
    ]
    assert worked == [12]


def test_one_registration_lapses_for_a_week_and_is_renewed():
    lapsed = WORLD.registration(LAPSED)
    assert lapsed.periods[0][1] == date(2026, 10, 11)
    assert lapsed.periods[1][0] == date(2026, 10, 18)
    others = [r for r in WORLD.registrations if r.subcontractor_id != LAPSED]
    weeks = [WORLD.week_ending(1), WORLD.week_ending(12)]
    assert all(len(r.periods) == 1 for r in others)
    assert all(r.active_on(day) for r in others for day in weeks)
    # Its only engagement in the week of the lapse is the Lincoln School renovation.
    in_week_7 = [
        e
        for e in WORLD.engagements
        if e.subcontractor_id == LAPSED and e.first_week <= 7
    ]
    assert [e.project_id for e in in_week_7] == ["PRJ-01"]


def test_every_pair_is_engaged_in_week_12_and_about_200_filings_are_expected():
    assert len(WORLD.engagements) == 24
    assert all(e.last_week == 12 for e in WORLD.engagements)
    assert all(1 <= e.first_week <= 9 for e in WORLD.engagements)
    assert 190 <= len(filings(WORLD)) <= 215
    week_12 = Counter(case.filing.week for case in CASES)[12] + len(SEEDED.missing)
    assert week_12 == 24


def test_case_ids_carry_the_week_and_the_pair():
    assert {case.case_id for case in CASES} >= {"PC-0311", "PC-0101", "PC-1224"}
    assert len({case.case_id for case in CASES}) == len(CASES)
