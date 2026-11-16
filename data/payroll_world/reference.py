"""What every reference file the generator writes for the context layer says of
itself: the system it stands for, its owner and the date it was reviewed."""

OWNER = "Compliance manager"
REVIEWED = "2026-11-02"


def source(system: str) -> dict[str, str]:
    return {"system": system, "owner": OWNER, "reviewed": REVIEWED}
