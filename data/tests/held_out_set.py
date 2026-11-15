"""The held-out set, built once for the tests."""

from data.generate import HELD_OUT_MANIFEST
from data.payroll_world.cases import seeded_set
from data.payroll_world.manifest import read_manifest
from data.payroll_world.world import build_world
from data.payroll_world.worlds import HELD_OUT

WORLD = build_world(HELD_OUT)
MANIFEST = read_manifest(HELD_OUT_MANIFEST, WORLD)
SEEDED = seeded_set(WORLD, MANIFEST)
CASES = SEEDED.cases
