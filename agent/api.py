"""The PayrollCheck backend's API for the payroll agent and the agent's entry point: one
function for each operation they use. It has no way to the scores, the settings,
the rounds or the labels."""

from typing import Any, Literal, TypedDict, Unpack

from agent.connection import call

StepKind = Literal[
    "screening",
    "tool_call",
    "tool_result",
    "message",
    "lookup",
    "refusal",
]
# The context files a lookup came from, each with its system, owner and review date.
Sources = list[dict[str, str]]


def list_cases() -> list[dict[str, Any]]:
    return call("GET", "/cases")


def get_case(case_id: str) -> dict[str, Any]:
    return call("GET", f"/cases/{case_id}")


def get_project(project_id: str) -> dict[str, Any]:
    return call("GET", f"/projects/{project_id}")


def list_subcontractors(project_id: str) -> list[dict[str, Any]]:
    return call("GET", f"/projects/{project_id}/subcontractors")


def get_payroll_history(case_id: str) -> dict[str, Any]:
    return call("GET", f"/cases/{case_id}/history")


def get_version(number: int) -> dict[str, Any]:
    return call("GET", f"/versions/{number}")


def get_current_version() -> dict[str, Any]:
    return call("GET", "/versions/current")


def get_screening() -> dict[str, Any]:
    return call("GET", "/screening")


def start_case(case_id: str, thread_id: str) -> dict[str, Any]:
    return call("POST", f"/cases/{case_id}/start", json={"thread_id": thread_id})


def record_step(
    case_id: str, kind: StepKind, content: str, sources: Sources
) -> dict[str, Any]:
    body = {"kind": kind, "content": content, "sources": sources}
    return call("POST", f"/cases/{case_id}/steps", json=body)


def record_check_findings(
    case_id: str, check: str, findings: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    body = {"check": check, "findings": findings}
    return call("POST", f"/cases/{case_id}/candidates", json=body)


def record_screening_flag(case_id: str, reason: str) -> dict[str, Any]:
    return call("POST", f"/cases/{case_id}/screening-flag", json={"reason": reason})


class ExceptionReport(TypedDict):
    """An exception report to record, with who raises its exceptions."""

    raised: list[int]
    dismissed: list[dict[str, Any]]
    added: list[dict[str, Any]]
    notice: str
    raised_by: str


# The body's fields as keywords, as the direct route passes a tool's inputs.
def record_exception_report(
    case_id: str, **report: Unpack[ExceptionReport]
) -> dict[str, Any]:
    return call("POST", f"/cases/{case_id}/report", json=report)


def fail_case(case_id: str, reason: str) -> dict[str, Any]:
    return call("POST", f"/cases/{case_id}/failure", json={"reason": reason})


def record_model_call(
    case_id: str,
    run_id: str | None,
    input_tokens: int,
    output_tokens: int,
    cost: float,
) -> dict[str, Any]:
    body = {
        "run_id": run_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
    }
    return call("POST", f"/cases/{case_id}/model-calls", json=body)


def record_work_time(
    case_id: str, run_id: str | None, seconds: float
) -> dict[str, Any]:
    body = {"run_id": run_id, "seconds": seconds}
    return call("POST", f"/cases/{case_id}/work-times", json=body)


def get_run(run_id: str) -> dict[str, Any]:
    return call("GET", f"/runs/{run_id}")


def record_run_heartbeat(run_id: str) -> dict[str, Any]:
    return call("POST", f"/runs/{run_id}/heartbeat")


def fail_run(run_id: str, reason: str) -> dict[str, Any]:
    return call("POST", f"/runs/{run_id}/failure", json={"reason": reason})


def record_run_cases(run_id: str, case_ids: list[str]) -> dict[str, Any]:
    return call("PUT", f"/runs/{run_id}/cases", json={"case_ids": case_ids})


def finish_run(run_id: str) -> dict[str, Any]:
    return call("POST", f"/runs/{run_id}/finish")
