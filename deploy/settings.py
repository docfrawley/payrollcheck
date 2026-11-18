"""The settings the runbook reads from .env, by name, and the file agentcore deploy
reads, agentcore/.env.local. No value is ever printed."""

import os
from collections.abc import Mapping
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOCAL_ENV = REPO / "agentcore" / ".env.local"

DATABASE_URL = "DATABASE_URL"
SUPABASE_URL = "VITE_SUPABASE_URL"
SUPABASE_PUBLISHABLE_KEY = "VITE_SUPABASE_PUBLISHABLE_KEY"
SUPABASE_ADMIN_KEY = "SUPABASE_SECRET_KEY"
REVIEWERS_SIGN_IN = "REVIEWER_PASSWORD"
OPENROUTER_API_KEY = "OPENROUTER_API_KEY"
API_KEY = "PAYROLLCHECK_API_KEY"

# Supabase's session pooler, which the laptop uses, and its transaction pooler, which
# Lambda and Runtime use, since each of their sessions opens connections of its own.
SESSION_POOLER = ":5432/"
TRANSACTION_POOLER = ":6543/"


class MissingSettings(Exception):
    """Settings a step needs that .env doesn't have, or doesn't have as it needs."""


def required(*names: str) -> dict[str, str]:
    """The settings a step needs, from the environment, or MissingSettings naming
    every one that's missing."""
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise MissingSettings(f"Add {', '.join(missing)} to .env")
    return {name: os.environ[name] for name in names}


def pooled(database_url: str) -> str:
    """The database's address on Supabase's transaction pooler."""
    if SESSION_POOLER not in database_url:
        raise MissingSettings(f"{DATABASE_URL} isn't on Supabase's session pooler")
    return database_url.replace(SESSION_POOLER, TRANSACTION_POOLER)


def write_local(values: Mapping[str, str], path: Path = LOCAL_ENV) -> None:
    """Put each setting in agentcore/.env.local, replacing its line or adding one and
    keeping every other line, readable only by the user, and say whether it changed."""
    for name, value in values.items():
        if any(character in value for character in '"\n'):
            raise ValueError(f"{name} can't be written to {path.name} as it is")
    before = path.read_text() if path.exists() else ""
    kept = [
        line
        for line in before.splitlines()
        if line.split("=", 1)[0].strip() not in values
    ]
    lines = [*kept, *(f'{name}="{value}"' for name, value in values.items())]
    after = "\n".join(lines) + "\n"
    shown = f"{', '.join(values)} in {path.parent.name}/{path.name}"
    if sorted(after.splitlines()) == sorted(before.splitlines()):
        print(f"{shown}: unchanged")
        return
    path.write_text(after)
    path.chmod(0o600)
    print(f"{shown}: {'updated' if before else 'created'}")
