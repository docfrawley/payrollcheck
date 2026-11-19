import os
import zipfile
from pathlib import Path

import pytest

from deploy import commands, packaging


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A repo of its own, whose installs put one package in the target, keeping each
    command asked for."""
    (tmp_path / "backend" / "tests").mkdir(parents=True)
    (tmp_path / "backend" / "__pycache__").mkdir()
    (tmp_path / "backend" / "main.py").write_text("app = None\n")
    (tmp_path / "backend" / "tests" / "test_main.py").write_text("")
    (tmp_path / "backend" / "__pycache__" / "main.pyc").write_bytes(b"\0")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "records.json").write_text("{}")
    (tmp_path / "data" / ".DS_Store").write_bytes(b"finder")
    (tmp_path / "context").mkdir()
    (tmp_path / "context" / "filing_dates.py").write_text("")
    (tmp_path / "context" / "payroll_files.py").write_text("")
    monkeypatch.setattr(packaging, "REPO", tmp_path)
    monkeypatch.setattr(packaging, "BUILD", tmp_path / "build")
    asked: list[list[str]] = []

    def run(command):
        asked.append(command)
        if command[:3] == ["uv", "pip", "install"]:
            installed = Path(command[command.index("--target") + 1]) / "fastapi"
            installed.mkdir()
            (installed / "x.py").write_text("")

    monkeypatch.setattr(commands, "run", run)
    return asked


def test_a_package_holds_its_folders_and_packages_but_no_tests(repo):
    path = packaging.build("lambda", "server", {"backend": "backend", "data": "data"})
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == [
            "backend/main.py",
            "data/records.json",
            "fastapi/x.py",
        ]
        assert {entry.date_time for entry in archive.infolist()} == {
            packaging.FIXED_TIME
        }


def test_a_package_holds_a_single_file_and_not_its_neighbours(repo):
    wanted = {
        "backend": "backend",
        "context/filing_dates.py": "context/filing_dates.py",
    }
    path = packaging.build("lambda", "server", wanted)
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == [
            "backend/main.py",
            "context/filing_dates.py",
            "fastapi/x.py",
        ]


def test_the_packages_are_for_lambdas_linux_and_python(repo):
    packaging.build("context", "context", {"data": "data"})
    export, install = repo
    assert export[:4] == ["uv", "export", "--only-group", "context"]
    assert install[:3] == ["uv", "pip", "install"]
    assert install[install.index("--python-platform") + 1] == "x86_64-manylinux2014"
    assert install[install.index("--python-version") + 1] == "3.12"
    assert install[install.index("--only-binary") + 1] == ":all:"
    assert install[-1] == export[-1]


def test_the_same_code_gives_the_same_zip(repo):
    first = packaging.code_sha256(packaging.build("lambda", "server", {"data": "data"}))
    os.utime(packaging.REPO / "data" / "records.json", (1_000_000_000, 1_000_000_000))
    (packaging.REPO / "data" / "records.json").chmod(0o600)
    second = packaging.code_sha256(
        packaging.build("lambda", "server", {"data": "data"})
    )
    assert first == second
    (packaging.REPO / "data" / "records.json").write_text('{"changed": true}')
    third = packaging.code_sha256(packaging.build("lambda", "server", {"data": "data"}))
    assert third != first


def test_lambdas_code_sha256_is_the_zips_sha256_in_base64(tmp_path):
    path = tmp_path / "x.zip"
    path.write_bytes(b"abc")
    assert packaging.code_sha256(path) == "ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0="
