"""A world's cases: every expected filing's clean payroll, the manifest's errors,
decoys and hidden instructions applied to it, made into its case by the
lifecycle, with the labels a perfect review would find."""

from dataclasses import dataclass

from data.payroll_world.clean import clean_payroll
from data.payroll_world.corruptions import Label, hide_instruction, seed_errors
from data.payroll_world.decoys import shape_decoy
from data.payroll_world.filings import Filing, filings
from data.payroll_world.lifecycle import Case, Fate, make_case, waits
from data.payroll_world.manifest import Manifest
from data.payroll_world.world import World

# Errors a correction can't undo: a payroll filed late, or work done unregistered.
UNCORRECTABLE = ("timeliness.late", "registration.inactive")


@dataclass(frozen=True)
class SeededSet:
    """A world's cases with their labels: the exceptions, the cases expected to be
    flagged for a hidden instruction, and the expected filings left missing."""

    cases: tuple[Case, ...]
    labels: tuple[Label, ...]
    screening_flags: tuple[str, ...]
    missing: tuple[Filing, ...]


def case_with_errors(
    world: World, filing: Filing, manifest: Manifest
) -> tuple[Case, tuple[Label, ...]]:
    """A filing seeded with its errors: waiting in the last week, sent back and left
    Returned to sub when its errors can't be corrected or the manifest says so, or
    else accepted on a clean correction."""
    errors = manifest.errors_on(filing.case_id)
    seeded = seed_errors(world, filing, clean_payroll(world, filing), errors)
    if waits(world, filing):
        fate, payrolls = Fate.WAITING, [seeded.filed]
    elif filing.case_id in manifest.still_returned or any(
        error.rule in UNCORRECTABLE for error in errors
    ):
        fate, payrolls = Fate.RETURNED, [seeded.filed]
    else:
        fate, payrolls = Fate.CORRECTED, [seeded.filed, seeded.corrected]
    return make_case(world, filing, fate, payrolls, seeded.late_by), seeded.labels


def clean_case(world: World, filing: Filing, manifest: Manifest) -> Case:
    """A filing with no error: as it came, or shaped as its decoy, with its hidden
    instruction."""
    payrolls = [clean_payroll(world, filing)]
    if decoy := manifest.decoys.get(filing.case_id):
        payrolls = shape_decoy(world, filing, payrolls[0], decoy)
    if hidden := manifest.hidden_instructions.get(filing.case_id):
        payrolls = [hide_instruction(payroll, hidden) for payroll in payrolls]
    fate = Fate.WAITING if waits(world, filing) else Fate.ACCEPTED
    return make_case(world, filing, fate, payrolls)


def seeded_set(world: World, manifest: Manifest) -> SeededSet:
    """Every filing's case, in case id order, but the missing ones."""
    cases, labels, missing = [], [], []
    for filing in filings(world):
        if filing.case_id in manifest.missing:
            missing.append(filing)
        elif manifest.errors_on(filing.case_id):
            case, seeded = case_with_errors(world, filing, manifest)
            cases.append(case)
            labels.extend(seeded)
        else:
            cases.append(clean_case(world, filing, manifest))
    flags = tuple(manifest.hidden_instructions)
    return SeededSet(tuple(cases), tuple(labels), tuple(sorted(flags)), tuple(missing))
