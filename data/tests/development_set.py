"""The development set, built once for the tests, and its committed files."""

from data.generate import DATA, DEVELOPMENT_FOLDER, DEVELOPMENT_MANIFEST, PAYROLLS
from data.payroll_world.cases import seeded_set
from data.payroll_world.manifest import read_manifest
from data.payroll_world.world import build_world
from data.payroll_world.worlds import DEVELOPMENT

WORLD = build_world(DEVELOPMENT)
MANIFEST = read_manifest(DEVELOPMENT_MANIFEST, WORLD)
SEEDED = seeded_set(WORLD, MANIFEST)
CASES = SEEDED.cases
FOLDER = DATA / DEVELOPMENT_FOLDER
PAYROLL_FILES = sorted((FOLDER / PAYROLLS).glob("*.csv"))
