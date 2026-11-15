"""The context layer's payroll files and their lookups, against the files in
context/."""

import pytest

from context import payroll_files
from context.sources import SYNTHETIC


@pytest.mark.parametrize("file", payroll_files.FILES)
def test_every_payroll_file_names_its_source_and_says_it_is_synthetic(file):
    read = payroll_files.FILES[file]
    assert read["source"]["file"] == file
    assert set(read["source"]) == {"file", "system", "owner", "reviewed"}
    assert read["notice"] == SYNTHETIC
