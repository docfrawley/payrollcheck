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
from data.payroll_world.cases import world_cases
from data.payroll_world.lifecycle import Case
from data.payroll_world.template import write_payroll
from data.payroll_world.world import World, build_world
from data.payroll_world.worlds import DEVELOPMENT
from data.payroll_world.writing import write_json, write_text, write_yaml

DATA = Path(__file__).parent
ROOT = DATA.parent
DEVELOPMENT_FOLDER = "development"
PAYROLLS = "payrolls"


def write_set(folder: Path, world: World, cases: tuple[Case, ...]) -> None:
    """A set's records, and a CSV for each submission of each of its cases."""
    write_json(folder / "world.json", records.world_record(world))
    write_json(folder / "subcontractors.json", records.subcontractors_record(world))
    write_json(folder / "workers.json", records.workers_record(world))
    write_json(folder / "cases.json", records.cases_record(cases))
    shutil.rmtree(folder / PAYROLLS, ignore_errors=True)
    for case in cases:
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
    write_set(data / DEVELOPMENT_FOLDER, development, world_cases(development))
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
