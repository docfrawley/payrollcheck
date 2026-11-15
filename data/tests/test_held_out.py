"""The held-out set: about 100 payrolls in another world, with other subcontractors
and workers, the same counties and crafts and the same mix of errors. The checks
it shares with the development set run on both, beside those."""

from collections import Counter

from context import payroll_files
from data.payroll_world.lifecycle import Status
from data.tests import development_set as development
from data.tests import held_out_set as held_out


def test_about_100_payrolls_from_five_other_subcontractors_and_their_own_workers():
    assert 90 <= len(held_out.CASES) <= 110
    subs = {sub.legal_name for sub in held_out.WORLD.subcontractors}
    assert len(subs) == 5
    assert not subs & {sub.legal_name for sub in development.WORLD.subcontractors}
    for world_has in (
        lambda world: {worker.name for worker in world.workers},
        lambda world: {worker.id for worker in world.workers},
        lambda world: {sub.fein for sub in world.subcontractors},
        lambda world: {sub.registration_no for sub in world.subcontractors},
    ):
        assert not world_has(held_out.WORLD) & world_has(development.WORLD)
    assert not {c.case_id for c in held_out.CASES} & {
        c.case_id for c in development.CASES
    }


def test_the_same_counties_and_crafts():
    def counties(world):
        return {project.county for project in world.spec.projects}

    def crafts(world):
        return {worker.craft for worker in world.workers}

    assert counties(held_out.WORLD) == counties(development.WORLD)
    assert crafts(held_out.WORLD) == crafts(development.WORLD)


def test_every_rule_at_least_once_2_hidden_instructions_and_5_decoys():
    rules = Counter(label.rule for label in held_out.SEEDED.labels)
    assert set(rules) == set(Counter(label.rule for label in development.SEEDED.labels))
    assert 20 <= sum(rules.values()) <= 25
    assert len(held_out.SEEDED.screening_flags) == 2
    assert len(held_out.MANIFEST.decoys) == 5


def test_every_case_waits_with_one_submission():
    assert {case.status for case in held_out.CASES} == {Status.RECEIVED}
    assert {len(case.submissions) for case in held_out.CASES} == {1}


def test_the_registry_and_apprentice_files_hold_both_worlds():
    files = payroll_files.FILES
    numbers = {
        r["registration_no"]
        for r in files[payroll_files.CONTRACTOR_REGISTRY]["registrations"]
    }
    apprentices = {
        a["worker_id"]
        for a in files[payroll_files.APPRENTICE_REGISTRATIONS]["apprentices"]
    }
    for world in (development.WORLD, held_out.WORLD):
        assert {sub.registration_no for sub in world.subcontractors} <= numbers
        assert {a.worker_id for a in world.apprentices} <= apprentices
