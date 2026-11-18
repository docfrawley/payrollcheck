"""The one way the runbook runs a command (uv, npm, agentcore), from the root of the
repo, found on the PATH as Windows and the Mac each name it, stopping the step if the
command fails."""

import shutil
import subprocess

from deploy.settings import REPO


def run(command: list[str]) -> None:
    """Run a command from the root of the repo, raising if it fails."""
    program = shutil.which(command[0])
    if program is None:
        raise FileNotFoundError(f"{command[0]} isn't installed, or isn't on the PATH")
    subprocess.run([program, *command[1:]], cwd=REPO, check=True)  # noqa: S603 - the runbook's own commands
