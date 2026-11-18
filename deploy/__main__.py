"""The runbook's command line: uv run --env-file .env -m deploy <step>, one step at a
time, in the order deploy/RUNBOOK.md gives."""

import argparse
import sys
from collections.abc import Callable

from deploy import supabase
from deploy.settings import MissingSettings

Step = Callable[[argparse.Namespace], None]


def steps() -> dict[str, tuple[str, Step]]:
    """Each step by its command, with what it does."""
    return {
        "supabase": ("Step 1: the reviewers' Auth users", lambda _: supabase.run()),
    }


def parser() -> argparse.ArgumentParser:
    """The command line, a command for each step."""
    command_line = argparse.ArgumentParser(prog="deploy", description=__doc__)
    commands = command_line.add_subparsers(dest="step", required=True)
    for name, (help_text, run) in steps().items():
        commands.add_parser(name, help=help_text).set_defaults(run=run)
    return command_line


def main(arguments: list[str]) -> int:
    """Run the step named, saying in one line what's missing when it can't start."""
    chosen = parser().parse_args(arguments)
    try:
        chosen.run(chosen)
    except MissingSettings as missing:
        print(missing)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
