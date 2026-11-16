"""The app's words for its records, as the payroll agent and the Copilot both read
them: where a case stands, the kinds of run, where a run stands, and the sets an
evaluation works."""

from enum import StrEnum
from typing import Literal

RunKind = Literal["dispatch", "evaluation"]
DISPATCH: RunKind = "dispatch"
EVALUATION: RunKind = "evaluation"
RunStatus = Literal["running", "finished", "stopped"]
RUNNING: RunStatus = "running"
STOPPED: RunStatus = "stopped"
EvaluationSet = Literal["development", "held_out", "tiny"]


class Status(StrEnum):
    """Where a case stands."""

    RECEIVED = "received"
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    ACCEPTED = "accepted"
    RETURNED_TO_SUB = "returned_to_sub"
