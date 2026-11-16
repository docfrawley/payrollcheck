"""The tiny set: ten development cases, one for each check family, one hidden
instruction and one decoy, labelled as the development set labels them."""

import json

from data.generate import DATA, EVALS, TINY_LABELS
from data.payroll_world.records import labels_record
from data.tests.development_set import MANIFEST, SEEDED

FAMILIES = {
    "form",
    "registration",
    "rate",
    "overtime",
    "arithmetic",
    "apprentice",
    "timeliness",
    "classification",
}
TINY = json.loads((DATA / EVALS / TINY_LABELS).read_text(encoding="utf-8"))


def test_ten_cases_one_for_each_check_family_a_hidden_instruction_and_a_decoy():
    cases = TINY["cases"]
    assert len(cases) == len(set(cases)) == 10
    # Timeliness and sequence are one family of checks.
    families = {
        label["rule"].split(".")[0].replace("sequence", "timeliness")
        for label in TINY["exceptions"]
    }
    assert families == FAMILIES
    labelled = {label["case_id"] for label in TINY["exceptions"]}
    assert len(labelled) == 8
    assert len(TINY["screening_flags"]) == 1
    assert len([case for case in cases if case in MANIFEST.decoys]) == 1


def test_the_tiny_labels_are_the_development_labels_for_its_cases():
    development = labels_record(SEEDED, MANIFEST.decoys.values())
    cases = TINY["cases"]
    assert TINY["exceptions"] == [
        label for label in development["exceptions"] if label["case_id"] in cases
    ]
    assert TINY["screening_flags"] == [
        case for case in development["screening_flags"] if case in cases
    ]
