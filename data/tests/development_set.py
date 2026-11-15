"""The development set, built once for the tests, and its committed files."""

from data.generate import DATA, DEVELOPMENT_FOLDER, PAYROLLS
from data.payroll_world.cases import world_cases
from data.payroll_world.world import build_world
from data.payroll_world.worlds import DEVELOPMENT

WORLD = build_world(DEVELOPMENT)
CASES = world_cases(WORLD)
FOLDER = DATA / DEVELOPMENT_FOLDER
PAYROLL_FILES = sorted((FOLDER / PAYROLLS).glob("*.csv"))
