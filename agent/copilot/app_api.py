"""The PayrollCheck backend's API for the Copilot: one function for each operation it
uses, each taking the reviewer's sign-in first and sending it, never the agent's
key, and the app's refusal, which each raises. Its reads of cases are the
Copilot's own, under /copilot/, which withhold a flagged case's text. It has no
way to sign off, send back or override a case, to the settings, the labelled
sets, the rounds or anything only the agent may do."""

from typing import Any, Literal, TypedDict

from agent import connection
from agent.app_terms import EvaluationSet
from agent.connection import call_as
from agent.context_tools import Sources

CardKind = Literal[
    "cases", "subcontractors", "projects", "context", "work", "memory", "action"
]
CardStatus = Literal["done", "refused", "failed"]
# The app's refusal of a request, which each function raises.
Refused = connection.Refused
# A turn the Copilot is still working on, as the app records it.
WORKING = "working"


def get_signed_in_reviewer(sign_in: str) -> dict[str, Any]:
    return call_as(sign_in, "GET", "/me")


def get_conversation(sign_in: str, conversation_id: str) -> dict[str, Any]:
    return call_as(sign_in, "GET", f"/copilot/conversations/{conversation_id}")


def get_copilot_model(sign_in: str) -> dict[str, Any]:
    return call_as(sign_in, "GET", "/copilot/model")


class CardStart(TypedDict):
    """A card as a step starts: its tool, its kind, its main input and what was
    asked."""

    tool: str
    kind: CardKind
    input: str
    asked: str


class CardResult(TypedDict):
    """How a step ended: what came back, or why it was refused or failed, and the
    files an answer came from."""

    status: CardStatus
    answer: str | None
    reason: str | None
    sources: Sources


def start_copilot_step(sign_in: str, turn_id: str, card: CardStart) -> dict[str, Any]:
    return call_as(sign_in, "POST", f"/copilot/turns/{turn_id}/steps", json=card)


def finish_copilot_step(
    sign_in: str, turn_id: str, step_id: int, result: CardResult
) -> dict[str, Any]:
    return call_as(
        sign_in, "POST", f"/copilot/turns/{turn_id}/steps/{step_id}/finish", json=result
    )


def finish_turn(
    sign_in: str, turn_id: str, answer: str, model_calls: int, cost: float
) -> dict[str, Any]:
    body = {"answer": answer, "model_calls": model_calls, "cost": cost}
    return call_as(sign_in, "POST", f"/copilot/turns/{turn_id}/finish", json=body)


def fail_turn(sign_in: str, turn_id: str, reason: str) -> dict[str, Any]:
    body = {"reason": reason}
    return call_as(sign_in, "POST", f"/copilot/turns/{turn_id}/failure", json=body)


def get_business_date(sign_in: str) -> dict[str, Any]:
    return call_as(sign_in, "GET", "/business-date")


def find_cases(sign_in: str, filters: dict[str, Any]) -> dict[str, Any]:
    return call_as(sign_in, "POST", "/copilot/cases", json=filters)


def read_case(sign_in: str, case_id: str) -> dict[str, Any]:
    return call_as(sign_in, "GET", f"/copilot/cases/{case_id}")


def get_exceptions(sign_in: str, case_id: str) -> dict[str, Any]:
    return call_as(sign_in, "GET", f"/copilot/cases/{case_id}/exceptions")


def exposure_summary(sign_in: str, filters: dict[str, Any]) -> dict[str, Any]:
    return call_as(sign_in, "POST", "/copilot/exposure", json=filters)


def filings_status(sign_in: str, filters: dict[str, Any]) -> dict[str, Any]:
    return call_as(sign_in, "POST", "/copilot/filings", json=filters)


def classification_changes(sign_in: str, filters: dict[str, Any]) -> dict[str, Any]:
    return call_as(sign_in, "POST", "/copilot/classification-changes", json=filters)


def find_subcontractors(sign_in: str, name: str) -> list[dict[str, Any]]:
    return call_as(sign_in, "GET", "/subcontractors", params={"name": name})


def find_projects(sign_in: str, name: str) -> list[dict[str, Any]]:
    return call_as(sign_in, "GET", "/copilot/projects", params={"name": name})


def draft_notice(sign_in: str, case_id: str) -> dict[str, Any]:
    return call_as(sign_in, "POST", f"/copilot/cases/{case_id}/notice-draft")


def get_latest_dispatch(sign_in: str) -> dict[str, Any] | None:
    return call_as(sign_in, "GET", "/dispatches/latest")


def list_evaluations(sign_in: str) -> list[dict[str, Any]]:
    return call_as(sign_in, "GET", "/evaluations")


def get_run(sign_in: str, run_id: str) -> dict[str, Any]:
    return call_as(sign_in, "GET", f"/runs/{run_id}")


def start_dispatch(sign_in: str, agents: int) -> dict[str, Any]:
    return call_as(sign_in, "POST", "/dispatches", json={"agents": agents})


def start_evaluation(
    sign_in: str, evaluation_set: EvaluationSet, agents: int
) -> dict[str, Any]:
    body = {"evaluation_set": evaluation_set, "agents": agents}
    return call_as(sign_in, "POST", "/evaluations", json=body)
