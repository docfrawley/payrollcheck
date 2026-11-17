"""What needs a reviewer, worked out in code from the cases in their scope: those
awaiting review with open exceptions, each with its count and outstanding
shortfall in dollars, those awaiting review with none, which need only a
sign-off, those the screening flagged, those the agent failed, and those Received,
still waiting for a dispatch."""

from typing import Any

from agent.app_terms import Status


def needs_a_reviewer(found: dict[str, Any]) -> dict[str, Any]:
    """What needs a reviewer, from the app's answer to a search of every case."""
    cases = found["cases"]
    waiting = [c for c in cases if c["status"] == Status.AWAITING_REVIEW]
    unflagged = [c for c in waiting if not (c["screening_flag"] or c["agent_failed"])]
    return {
        "with_open_exceptions": [
            {
                "case_id": c["case_id"],
                "open_exceptions": c["open_exceptions"],
                "shortfall": c["shortfall"],
            }
            for c in unflagged
            if c["open_exceptions"]
        ],
        "to_sign_off": [c["case_id"] for c in unflagged if not c["open_exceptions"]],
        "screening_flagged": [c["case_id"] for c in waiting if c["screening_flag"]],
        "agent_failed": [c["case_id"] for c in waiting if c["agent_failed"]],
        "received": [c["case_id"] for c in cases if c["status"] == Status.RECEIVED],
    }
