import subprocess

import pytest

from deploy import commands
from deploy.settings import REPO


def test_a_command_runs_from_the_repo_and_stops_the_step_when_it_fails(monkeypatch):
    ran: list[tuple[list[str], object]] = []

    def run(command, cwd, check):
        ran.append((command, cwd))
        assert check

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(commands.shutil, "which", lambda name: f"/bin/{name}")
    commands.run(["npm", "run", "build"])
    assert ran == [(["/bin/npm", "run", "build"], REPO)]


def test_a_command_that_isnt_installed_says_so(monkeypatch):
    monkeypatch.setattr(commands.shutil, "which", lambda name: None)
    with pytest.raises(FileNotFoundError, match="agentcore isn't installed"):
        commands.run(["agentcore", "deploy"])
