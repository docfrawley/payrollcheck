"""What needs a reviewer, worked out in code from the queue: the cases awaiting
review, with those the screening flagged and those the agent failed apart, each
with its open exceptions and shortfall."""

from typing import Any

from agent.app_terms import Status


def needs_a_reviewer(queue: list[dict[str, Any]]) -> dict[str, Any]:
    """What in the queue needs a reviewer."""
    waiting = [c for c in queue if c["status"] == Status.AWAITING_REVIEW]
    return {
        "awaiting_review": [
            {
                "case_id": c["case_id"],
                "open_exceptions": c["open_exceptions"],
                "shortfall_cents": c["shortfall_cents"],
            }
            for c in waiting
            if not (c["screening_flag"] or c["agent_failed"])
        ],
        "screening_flagged": [c["case_id"] for c in waiting if c["screening_flag"]],
        "agent_failed": [c["case_id"] for c in waiting if c["agent_failed"]],
    }
