"""The runbook's command line: uv run --env-file .env -m deploy <step>, one step at a
time, in the order deploy/RUNBOOK.md gives."""

import argparse
import sys
from collections.abc import Callable

from deploy import (
    functions,
    gateway,
    identity,
    inventory,
    memory,
    policy,
    runtimes,
    smoke,
    supabase,
)
from deploy.aws import connect
from deploy.settings import MissingSettings

Step = Callable[[argparse.Namespace], None]


def steps() -> dict[str, tuple[str, Step]]:
    """Each step by its command, with what it does."""
    return {
        "supabase": ("Step 1: the reviewers' Auth users", lambda _: supabase.run()),
        "lambda": (
            "Step 2: the app and the context layer on Lambda",
            lambda _: functions.run(connect()),
        ),
        "identity": (
            "Step 3: the Gateway's credential and the runtimes' credentials",
            lambda _: identity.run(connect()),
        ),
        "gateway": (
            "Step 4: the Gateway and its two targets",
            lambda _: gateway.run(connect()),
        ),
        "policy": (
            "Step 5: the Policy, an allowlist enforced on the Gateway",
            lambda _: policy.run(connect()),
        ),
        "memory": ("Step 6: the Copilot's Memory", lambda _: memory.run(connect())),
        "runtimes": (
            "Step 7: the payroll agent's and the Copilot's Runtimes",
            lambda _: runtimes.run(connect()),
        ),
        "show": ("What the runbook made", lambda _: inventory.show(connect())),
        "smoke": (
            "A part of the smoke check: copilot, policy or decisions",
            lambda chosen: smoke.run(connect(), chosen.part),
        ),
        "teardown": (
            "Delete what the runbook made, only with --yes",
            lambda chosen: inventory.tear_down(connect(), yes=chosen.yes),
        ),
    }


def parser() -> argparse.ArgumentParser:
    """The command line, a command for each step."""
    command_line = argparse.ArgumentParser(prog="deploy", description=__doc__)
    commands = command_line.add_subparsers(dest="step", required=True)
    for name, (help_text, run) in steps().items():
        commands.add_parser(name, help=help_text).set_defaults(run=run)
    commands.choices["smoke"].add_argument("part", choices=smoke.PARTS)
    commands.choices["teardown"].add_argument(
        "--yes", action="store_true", help="delete them, rather than list them"
    )
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
