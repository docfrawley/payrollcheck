"""The two labelled sets the tests check alike: the development set and the
held-out set, each built once."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from data.generate import (
    DATA,
    DEVELOPMENT_FOLDER,
    DEVELOPMENT_LABELS,
    EVALS,
    HELD_OUT_FOLDER,
    HELD_OUT_LABELS,
)
from data.payroll_world.cases import SeededSet
from data.payroll_world.corruptions import Label
from data.payroll_world.lifecycle import Case
from data.payroll_world.manifest import Manifest
from data.payroll_world.world import World
from data.tests import development_set, held_out_set


@dataclass(frozen=True)
class LabelledSet:
    name: str
    world: World
    manifest: Manifest
    seeded: SeededSet
    folder: Path
    labels_file: Path

    @property
    def cases(self) -> tuple[Case, ...]:
        return self.seeded.cases

    def case(self, case_id: str) -> Case:
        [found] = [case for case in self.cases if case.case_id == case_id]
        return found

    def labels_of(self, case_id: str) -> list[Label]:
        return [label for label in self.seeded.labels if label.case_id == case_id]


SETS = [
    LabelledSet(
        "development",
        development_set.WORLD,
        development_set.MANIFEST,
        development_set.SEEDED,
        DATA / DEVELOPMENT_FOLDER,
        DATA / EVALS / DEVELOPMENT_LABELS,
    ),
    LabelledSet(
        "held_out",
        held_out_set.WORLD,
        held_out_set.MANIFEST,
        held_out_set.SEEDED,
        DATA / HELD_OUT_FOLDER,
        DATA / EVALS / HELD_OUT_LABELS,
    ),
]


# Runs a test on each labelled set, given to it as `labelled`.
each_set = pytest.mark.parametrize("labelled", SETS, ids=lambda found: found.name)
