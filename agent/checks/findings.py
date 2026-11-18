"""What a check tool finds: a candidate finding, with the rule it breaks, where,
what was expected and paid, the shortfall in cents where money is owed, and the
citation it rests on. The rule codes and the version's tunable parameters are
here too, since every check reads them."""

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

MISSING_FIELD = "form.missing_field"
UNSIGNED = "form.unsigned"
PROJECT_MISMATCH = "form.project_mismatch"
INACTIVE = "registration.inactive"
BASE_SHORT = "rate.base_short"
FRINGE_SHORT = "rate.fringe_short"
OVERTIME = "overtime.underpaid"
HOURS_TOTAL = "arithmetic.hours_total"
GROSS = "arithmetic.gross"
UNREGISTERED = "apprentice.unregistered"
RATIO = "apprentice.ratio"
LATE = "timeliness.late"
GAP = "sequence.gap"
CHANGED = "classification.changed"
MISMATCH = "classification.mismatch"
RULES = (
    MISSING_FIELD,
    UNSIGNED,
    PROJECT_MISMATCH,
    INACTIVE,
    BASE_SHORT,
    FRINGE_SHORT,
    OVERTIME,
    HOURS_TOTAL,
    GROSS,
    UNREGISTERED,
    RATIO,
    LATE,
    GAP,
    CHANGED,
    MISMATCH,
)
# The rules a check alone decides: the agent raises them only from its findings.
CHECK_DECIDES = (LATE, GAP)


@dataclass(frozen=True)
class Finding:
    """A candidate finding. A rule about the whole payroll has no worker or line."""

    rule: str
    worker_id: str | None
    line_no: int | None
    expected: str
    actual: str
    shortfall_cents: int | None
    citation: str

    def record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Parameters:
    """The checks' tunable parameters, from the payroll agent's version: a line's
    shortfall or arithmetic difference at or under the rounding tolerance is no
    finding."""

    rounding_tolerance_cents: int

    @classmethod
    def read(cls, parameters: dict[str, Any]) -> "Parameters":
        return cls(parameters["rounding_tolerance_cents"])

    def owed(self, cents: int) -> bool:
        """Whether a difference in cents is over the tolerance."""
        return cents > self.rounding_tolerance_cents


def dollars(cents: int) -> str:
    return f"${Decimal(cents) / 100:,.2f}"


def hourly(cents: int) -> str:
    return f"{dollars(cents)}/h"


def hours(found: Decimal) -> str:
    return f"{found:.2f} h"
