"""An error manifest: the errors seeded on a world's clean payrolls, each a case, a
rule, a worker for a rule about a line, and how the payroll is corrupted; the
decoys, payrolls that look wrong but are clean; the hidden instructions, each in a
text cell; which history cases are left Returned to sub; which last-week filings
are left missing; and the tiny set. It is read against its world, and an entry the
generator can't apply is refused as it is read."""

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from data.payroll_world.filings import Filing, filings
from data.payroll_world.lifecycle import waits
from data.payroll_world.rules import (
    CASE_RULES,
    CORRECTED_RESUBMISSION,
    LINE_DECOYS,
    LINE_RULES,
    PAYROLL_DECOYS,
)
from data.payroll_world.template import FREE_TEXT, LINE
from data.payroll_world.world import World

NAMED = ("case", "rule", "kind", "worker", "hours")


@dataclass(frozen=True)
class Error:
    """One seeded error: the hours its line is worked, when it gives them, and what
    else its corruption needs, such as cut_cents."""

    case: str
    rule: str
    worker: str | None
    hours: tuple[Decimal, ...] | None = None
    given: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decoy:
    """A decoy: the worker whose line it shapes, or an empty string when it shapes
    the whole payroll, the hours it gives the line, and what else it needs."""

    case: str
    kind: str
    worker: str
    hours: tuple[Decimal, ...] | None = None
    given: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HiddenInstruction:
    """An instruction hidden in a text cell: of the payroll's certification, or of
    a worker's line."""

    case: str
    column: str
    worker: str | None
    text: str


@dataclass(frozen=True)
class Manifest:
    errors: tuple[Error, ...]
    decoys: dict[str, Decoy]
    hidden_instructions: dict[str, HiddenInstruction]
    still_returned: frozenset[str]
    missing: frozenset[str]
    tiny: tuple[str, ...]

    def errors_on(self, case_id: str) -> list[Error]:
        return [error for error in self.errors if error.case == case_id]


class ManifestError(ValueError):
    """A manifest entry that can't be applied, with what's wrong with it."""


def hours(entry: dict[str, Any]) -> tuple[Decimal, ...] | None:
    given = entry.get("hours")
    return None if given is None else tuple(Decimal(str(h)) for h in given)


def given(entry: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entry.items() if k not in NAMED}


def error(entry: dict[str, Any]) -> Error:
    rule, worker = entry["rule"], entry.get("worker")
    if rule not in LINE_RULES + CASE_RULES:
        raise ManifestError(f"{entry['case']}: no rule {rule}")
    if (rule in LINE_RULES) != (worker is not None):
        raise ManifestError(
            f"{entry['case']}: {rule} needs a worker only for a line rule"
        )
    return Error(entry["case"], rule, worker, hours(entry), given(entry))


def decoy(entry: dict[str, Any]) -> Decoy:
    kind, worker = entry["kind"], entry.get("worker")
    if kind not in LINE_DECOYS + PAYROLL_DECOYS:
        raise ManifestError(f"{entry['case']}: no decoy {kind}")
    if (kind in LINE_DECOYS) != (worker is not None):
        raise ManifestError(f"{entry['case']}: {kind} needs a worker only on a line")
    return Decoy(entry["case"], kind, worker or "", hours(entry), given(entry))


def hidden_instruction(entry: dict[str, Any]) -> HiddenInstruction:
    column, worker = entry["column"], entry.get("worker")
    if column not in FREE_TEXT:
        raise ManifestError(f"{entry['case']}: {column} isn't a free text cell")
    if (column in LINE) != (worker is not None):
        raise ManifestError(f"{entry['case']}: {column} needs a worker only on a line")
    return HiddenInstruction(entry["case"], column, worker, entry["text"])


def check(manifest: Manifest, world: World) -> None:
    """Refuse what the world can't take: a case that isn't an expected filing, a
    clean case seeded with an error or left missing, a resubmission or a missing
    filing outside the waiting cases, and a case left Returned to sub with no error
    or none to return."""
    expected: dict[str, Filing] = {f.case_id: f for f in filings(world)}
    seeded = {e.case for e in manifest.errors}
    clean = [*manifest.decoys, *manifest.hidden_instructions]
    named = [
        *seeded,
        *clean,
        *manifest.still_returned,
        *manifest.missing,
        *manifest.tiny,
    ]
    if unknown := sorted(set(named) - set(expected)):
        raise ManifestError(f"Not expected filings: {unknown}")
    if clashing := sorted(
        set(clean) & (seeded | manifest.missing) | seeded & manifest.missing
    ):
        raise ManifestError(f"Cases with a clash of entries: {clashing}")
    if set(manifest.decoys) & set(manifest.hidden_instructions):
        raise ManifestError("A case has both a decoy and a hidden instruction")
    for decoy in manifest.decoys.values():
        if decoy.kind == CORRECTED_RESUBMISSION and not waits(
            world, expected[decoy.case]
        ):
            raise ManifestError(
                f"{decoy.case}: a resubmission decoy goes in a waiting case"
            )
    for case in manifest.missing:
        if expected[case].week != world.spec.weeks:
            raise ManifestError(
                f"{case}: only a filing in the last week can be missing"
            )
    for case in manifest.still_returned:
        if case not in seeded or waits(world, expected[case]):
            raise ManifestError(
                f"{case}: only a history case with errors stays returned"
            )


def read_manifest(path: Path, world: World) -> Manifest:
    """A world's manifest from its file, refusing an entry it can't apply."""
    found = yaml.safe_load(path.read_text(encoding="utf-8"))
    decoys = [decoy(entry) for entry in found["decoys"]]
    hidden = [hidden_instruction(entry) for entry in found["hidden_instructions"]]
    manifest = Manifest(
        tuple(error(entry) for entry in found["errors"]),
        {d.case: d for d in decoys},
        {h.case: h for h in hidden},
        frozenset(found["still_returned"]),
        frozenset(found["missing"]),
        tuple(found["tiny"]),
    )
    if len(manifest.decoys) != len(decoys) or len(manifest.hidden_instructions) != len(
        hidden
    ):
        raise ManifestError("A case has two decoys or two hidden instructions")
    check(manifest, world)
    return manifest
