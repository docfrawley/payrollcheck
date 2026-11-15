"""Builds PayrollCheck's synthetic world and writes every file made from it, the
same on every run: npm run generate, or uv run -m data.generate. It imports nothing
from the app."""

from pathlib import Path

from context.payroll_files import RATE_DETERMINATIONS
from context.sources import FOLDER
from data.payroll_world import determinations
from data.payroll_world.writing import write_yaml

ROOT = Path(__file__).parent.parent


def generate(root: Path = ROOT) -> None:
    """Write every generated file under the root: the repo's, or another folder's
    to compare with it."""
    context = root / FOLDER.name
    write_yaml(
        context / RATE_DETERMINATIONS,
        determinations.ABOUT,
        determinations.rate_determinations(),
    )


if __name__ == "__main__":
    generate()
