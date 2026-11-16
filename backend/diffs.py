"""What differs between two versions: the lines of two texts, such as two versions
of the payroll agent's instructions or of the improver's recipe, with two lines of
context, as Python's difflib finds them, and the check tools' parameters that
changed."""

import difflib
from typing import Any

from backend.models import Diff, DiffLine, DiffLineKind, ParameterChange
from backend.parameters import PARAMETERS

CONTEXT = 2
KINDS = {" ": DiffLineKind.CONTEXT, "+": DiffLineKind.ADDED, "-": DiffLineKind.REMOVED}


def diff(old: str, new: str) -> Diff:
    """Return the hunks of lines that differ from the old text to the new, with the
    lines added and removed counted."""
    lines = difflib.unified_diff(
        old.splitlines(), new.splitlines(), lineterm="", n=CONTEXT
    )
    hunks: list[list[DiffLine]] = []
    # The first two lines name the two texts, which have no names here.
    for line in list(lines)[2:]:
        if line.startswith("@@"):
            hunks.append([])
        else:
            hunks[-1].append(DiffLine(kind=KINDS[line[0]], text=line[1:]))
    changed = [line.kind for hunk in hunks for line in hunk]
    return Diff(
        added=changed.count(DiffLineKind.ADDED),
        removed=changed.count(DiffLineKind.REMOVED),
        hunks=hunks,
    )


def parameter_changes(
    before: dict[str, Any], after: dict[str, Any]
) -> list[ParameterChange]:
    """Return each parameter in the catalogue whose value differs between two
    versions, with its value before and after."""
    return [
        ParameterChange(
            **allowed.labelled(),
            before=before[allowed.name],
            after=after[allowed.name],
        )
        for allowed in PARAMETERS
        if before[allowed.name] != after[allowed.name]
    ]
