"""Rebuild the database from data/, with: uv run -m backend.seed"""

from backend.database import engine, location
from backend.seeding import seed


def main() -> None:
    """Rebuild the database and say what it holds."""
    db = engine()
    counts = seed(db)
    print(
        f"Seeded {counts['cases']} cases on {counts['projects']} projects, "
        f"{counts['subcontractors']} subcontractors, {counts['workers']} workers "
        f"and {counts['reviewers']} reviewers into {location(db)}, with "
        f"{counts['development_cases']} development and {counts['held_out_cases']} "
        f"held-out labelled cases and their {counts['labels']} labels, and version 1 "
        "of the configuration and of the recipe"
    )


if __name__ == "__main__":
    main()
