"""The two Lambda packages, as docs/TECH_STACK.md describes them: folders of the repo
without their tests, with a dependency group's packages installed for Lambda's Linux
and Python 3.12, zipped the same way every time, so the same code gives the same bytes
and Lambda's CodeSha256 says whether the code has changed."""

import base64
import hashlib
import shutil
import stat
import zipfile
from pathlib import Path

from deploy import commands
from deploy.settings import REPO

BUILD = REPO / "build"
PYTHON = "3.12"
LINUX = [
    "--python-platform",
    "x86_64-manylinux2014",
    "--python-version",
    PYTHON,
    "--only-binary",
    ":all:",
]
# Every entry's date, system and permissions, so a zip's bytes depend only on what's
# in it, whoever builds it on whichever computer.
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
UNIX = 3
READABLE_FILE = (stat.S_IFREG | 0o644) << 16
LEFT_OUT = shutil.ignore_patterns("tests", "__pycache__", ".DS_Store")


def build(name: str, group: str, folders: dict[str, str]) -> Path:
    """A zip of the repo's folders, each at its path in the package, with a dependency
    group's packages installed beside them for Lambda."""
    folder = BUILD / name
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    requirements = BUILD / f"{name}-requirements.txt"
    commands.run(
        [
            "uv",
            "export",
            "--only-group",
            group,
            "--no-hashes",
            "--no-emit-project",
            "--quiet",
            "--output-file",
            str(requirements),
        ]
    )
    commands.run(
        ["uv", "pip", "install", "--quiet", "--target", str(folder), *LINUX]
        + ["-r", str(requirements)]
    )
    for source, target in folders.items():
        shutil.copytree(REPO / source, folder / target, ignore=LEFT_OUT)
    return zip_folder(folder, BUILD / f"{name}.zip")


def zip_folder(folder: Path, path: Path) -> Path:
    """Zip a folder's files in order of their paths, each with the fixed date, system
    and permissions, and print the zip's size against Lambda's limit."""
    files = {
        file.relative_to(folder).as_posix(): file
        for file in folder.rglob("*")
        if file.is_file()
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry_path in sorted(files):
            entry = zipfile.ZipInfo(entry_path, FIXED_TIME)
            entry.create_system = UNIX
            entry.external_attr = READABLE_FILE
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, files[entry_path].read_bytes())
    print(f"{path.name}: {path.stat().st_size / 1_000_000:.1f} MB (Lambda takes 50 MB)")
    return path


def code_sha256(path: Path) -> str:
    """A zip's SHA-256 as Lambda gives a function's CodeSha256."""
    return base64.b64encode(hashlib.sha256(path.read_bytes()).digest()).decode()
