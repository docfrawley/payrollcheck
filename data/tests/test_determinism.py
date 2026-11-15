"""The generator writes the same files on every run, and the committed files are
what it writes."""

from pathlib import Path

from context import payroll_files
from context.wage_rules import rate_table
from data.generate import ROOT, generate
from data.payroll_world import determinations


def written(root: Path) -> dict[str, bytes]:
    """Every file under a root, by its path from the root."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_two_runs_write_the_same_files_as_are_committed(tmp_path):
    generate(tmp_path / "first")
    generate(tmp_path / "second")
    first = written(tmp_path / "first")
    assert first == written(tmp_path / "second")
    committed = {path: (ROOT / path).read_bytes() for path in first}
    assert first == committed


def test_the_written_rates_file_reads_back_as_the_same_rate_table():
    assert rate_table(determinations.rate_determinations()) == payroll_files.RATES
