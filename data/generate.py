"""Builds PayrollCheck's synthetic world and writes every file made from it, the
same on every run: npm run generate, or uv run -m data.generate. It imports nothing
from the app."""

import shutil
from pathlib import Path

from context.payroll_files import (
    APPRENTICE_REGISTRATIONS,
    CONTRACTOR_REGISTRY,
    RATE_DETERMINATIONS,
)
from context.sources import FOLDER
from data.payroll_world import determinations, records
from data.payroll_world.cases import SeededSet, seeded_set
from data.payroll_world.manifest import read_manifest
from data.payroll_world.template import write_payroll
from data.payroll_world.world import World, build_world
from data.payroll_world.worlds import DEVELOPMENT
from data.payroll_world.writing import write_json, write_text, write_yaml

DATA = Path(__file__).parent
ROOT = DATA.parent
DEVELOPMENT_FOLDER = "development"
DEVELOPMENT_MANIFEST = DATA / "error_manifest.yaml"
EVALS = "evals"
DEVELOPMENT_LABELS = "development_labels.json"
PAYROLLS = "payrolls"


def write_set(folder: Path, world: World, seeded: SeededSet) -> None:
    """A set's records, and a CSV for each submission of each of its cases."""
    write_json(folder / "world.json", records.world_record(world))
    write_json(folder / "subcontractors.json", records.subcontractors_record(world))
    write_json(folder / "workers.json", records.workers_record(world))
    write_json(folder / "cases.json", records.cases_record(seeded.cases))
    shutil.rmtree(folder / PAYROLLS, ignore_errors=True)
    for case in seeded.cases:
        for submission in case.submissions:
            name = records.payroll_file(case.case_id, submission.number)
            write_text(folder / PAYROLLS / name, write_payroll(submission.payroll))


def generate(root: Path = ROOT) -> None:
    """Write every generated file under the root: the repo's, or another folder's
    to compare with it."""
    context, data = root / FOLDER.name, root / DATA.name
    write_yaml(
        context / RATE_DETERMINATIONS,
        determinations.ABOUT,
        determinations.rate_determinations(),
    )
    development = build_world(DEVELOPMENT)
    manifest = read_manifest(DEVELOPMENT_MANIFEST, development)
    seeded = seeded_set(development, manifest)
    write_set(data / DEVELOPMENT_FOLDER, development, seeded)
    write_json(data / EVALS / DEVELOPMENT_LABELS, records.labels_record(seeded))
    worlds = [development]
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


if __name__ == "__main__":
    generate()
