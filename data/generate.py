"""Builds PayrollCheck's synthetic world and writes every file made from it, the
same on every run: npm run generate, or uv run -m data.generate. It imports nothing
from the app."""

import shutil
from pathlib import Path

from context.sources import (
    APPRENTICE_REGISTRATIONS,
    CONTRACTOR_REGISTRY,
    FOLDER,
    RATE_DETERMINATIONS,
)
from data.payroll_world import determinations, records
from data.payroll_world.cases import SeededSet, seeded_set
from data.payroll_world.clean import clean_payroll
from data.payroll_world.expected_answers import expected_answers
from data.payroll_world.manifest import read_manifest
from data.payroll_world.template import write_payroll
from data.payroll_world.world import World, build_world
from data.payroll_world.worlds import DEVELOPMENT, HELD_OUT, MARCUS
from data.payroll_world.writing import write_json, write_text, write_yaml

DATA = Path(__file__).parent
ROOT = DATA.parent
DEVELOPMENT_FOLDER = "development"
DEVELOPMENT_MANIFEST = DATA / "error_manifest.yaml"
EVALS = "evals"
DEVELOPMENT_LABELS = "development_labels.json"
HELD_OUT_FOLDER = "held_out"
HELD_OUT_MANIFEST = DATA / "held_out_manifest.yaml"
HELD_OUT_LABELS = "held_out_labels.json"
TINY_LABELS = "tiny_labels.json"
COPILOT_EXPECTED = "copilot_expected.json"
# The Copilot's expected answers are for this reviewer's scope.
ASKED_BY = MARCUS
PAYROLLS = "payrolls"
# The payrolls of the expected filings left missing, which seeding never loads: the
# files a reviewer uploads when they arrive.
ARRIVALS = "arrivals"


def write_set(folder: Path, world: World, seeded: SeededSet) -> None:
    """A set's records, a CSV for each submission of each of its cases, and one for
    each missing filing as it would arrive."""
    write_json(folder / "world.json", records.world_record(world))
    write_json(folder / "subcontractors.json", records.subcontractors_record(world))
    write_json(folder / "workers.json", records.workers_record(world))
    write_json(folder / "cases.json", records.cases_record(seeded.cases))
    shutil.rmtree(folder / PAYROLLS, ignore_errors=True)
    for case in seeded.cases:
        for submission in case.submissions:
            name = records.payroll_file(case.case_id, submission.number)
            write_text(folder / PAYROLLS / name, write_payroll(submission.payroll))
    shutil.rmtree(folder / ARRIVALS, ignore_errors=True)
    for filing in seeded.missing:
        name = records.payroll_file(filing.case_id, 1)
        payroll = clean_payroll(world, filing)
        write_text(folder / ARRIVALS / name, write_payroll(payroll))


def write_development(data: Path) -> World:
    """The development set, its labels, the tiny set and the Copilot's expected
    answers."""
    world = build_world(DEVELOPMENT)
    manifest = read_manifest(DEVELOPMENT_MANIFEST, world)
    seeded = seeded_set(world, manifest)
    write_set(data / DEVELOPMENT_FOLDER, world, seeded)
    write_json(
        data / EVALS / DEVELOPMENT_LABELS,
        records.labels_record(seeded, manifest.decoys.values()),
    )
    write_json(
        data / EVALS / TINY_LABELS, records.tiny_labels_record(seeded, manifest.tiny)
    )
    write_json(data / COPILOT_EXPECTED, expected_answers(world, seeded, ASKED_BY))
    return world


def write_held_out(data: Path) -> World:
    """The held-out set and its labels."""
    world = build_world(HELD_OUT)
    manifest = read_manifest(HELD_OUT_MANIFEST, world)
    seeded = seeded_set(world, manifest)
    write_set(data / HELD_OUT_FOLDER, world, seeded)
    write_json(
        data / EVALS / HELD_OUT_LABELS,
        records.labels_record(seeded, manifest.decoys.values()),
    )
    return world


def write_reference(context: Path, worlds: list[World]) -> None:
    """The context layer's files the worlds make: the rate determinations, and every
    world's registrations and apprentices."""
    write_yaml(
        context / RATE_DETERMINATIONS,
        determinations.ABOUT,
        determinations.rate_determinations(),
    )
    write_yaml(
        context / CONTRACTOR_REGISTRY,
        records.REGISTRY_ABOUT,
        records.registry_record(worlds),
    )
    write_yaml(
        context / APPRENTICE_REGISTRATIONS,
        records.APPRENTICES_ABOUT,
        records.apprentices_record(worlds),
    )


def generate(root: Path = ROOT) -> None:
    """Write every generated file under the root: the repo's, or another folder's
    to compare with it."""
    data = root / DATA.name
    worlds = [write_development(data), write_held_out(data)]
    write_reference(root / FOLDER.name, worlds)


if __name__ == "__main__":
    generate()
