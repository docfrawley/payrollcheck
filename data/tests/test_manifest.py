"""A manifest refuses, as it is read, an entry the generator can't apply."""

import pytest

from data.payroll_world.manifest import ManifestError, read_manifest
from data.tests.development_set import WORLD

ERROR = "{case: PC-0311, rule: rate.base_short, worker: W-026, cut_cents: 150}"


def manifest(tmp_path, **entries):
    """A manifest file with the error above, or the entries given."""
    found = {"errors": ERROR, "decoys": "", "hidden": "", "returned": "", "missing": ""}
    found |= entries
    path = tmp_path / "manifest.yaml"
    path.write_text(
        f"errors: [{found['errors']}]\ndecoys: [{found['decoys']}]\n"
        f"hidden_instructions: [{found['hidden']}]\n"
        f"still_returned: [{found['returned']}]\nmissing: [{found['missing']}]\n"
        "tiny: []\n",
        encoding="utf-8",
    )
    return path


def test_a_manifest_reads_its_entries(tmp_path):
    found = read_manifest(
        manifest(tmp_path, decoys="{case: PC-0702, kind: later_determination}"), WORLD
    )
    [error] = found.errors_on("PC-0311")
    assert (error.rule, error.worker, error.given) == (
        "rate.base_short",
        "W-026",
        {"cut_cents": 150},
    )
    assert found.decoys["PC-0702"].worker == ""


@pytest.mark.parametrize(
    ("entries", "reason"),
    [
        (
            {"errors": "{case: PC-0101, rule: rate.made_up, worker: W-001}"},
            "no rule rate.made_up",
        ),
        (
            {"errors": "{case: PC-0101, rule: rate.base_short}"},
            "needs a worker only for a line",
        ),
        (
            {"errors": "{case: PC-0101, rule: sequence.gap, worker: W-001}"},
            "needs a worker only",
        ),
        ({"decoys": "{case: PC-0101, kind: made_up}"}, "no decoy made_up"),
        (
            {"decoys": "{case: PC-0101, kind: cash_in_lieu}"},
            "needs a worker only on a line",
        ),
        (
            {"hidden": "{case: PC-0101, column: gross, text: x}"},
            "isn't a free text cell",
        ),
        (
            {"hidden": "{case: PC-0101, column: classification, text: x}"},
            "isn't a free text",
        ),
        (
            {"hidden": "{case: PC-0101, column: line_notes, text: x}"},
            "needs a worker only on a line",
        ),
        ({"decoys": "{case: PC-0311, kind: later_determination}"}, "clash of entries"),
        ({"errors": "{case: PC-9999, rule: sequence.gap}"}, "Not expected filings"),
        (
            {"decoys": "{case: PC-1101, kind: corrected_resubmission, worker: W-001}"},
            "waiting case",
        ),
        ({"missing": "PC-1101"}, "only a filing in the last week"),
        ({"returned": "PC-1101"}, "only a history case with errors"),
        (
            {"missing": "PC-1201", "errors": "{case: PC-1201, rule: sequence.gap}"},
            "clash",
        ),
    ],
)
def test_a_manifest_refuses_an_entry_it_cant_apply(tmp_path, entries, reason):
    with pytest.raises(ManifestError, match=reason):
        read_manifest(manifest(tmp_path, **entries), WORLD)
