"""Working an evaluation's copies through the API as the payroll agent would, for
the tests that score them and grade their notices."""

from backend.tests.case_requests import record_findings, report, start


def original(copy_id):
    return copy_id.rsplit("-E", 1)[0]


def raise_these(client, copy_id, findings, notice="Please correct and resubmit."):
    start(client, copy_id, thread_id=copy_id)
    candidates = record_findings(client, copy_id, findings=findings).json()
    ids = [c["candidate_id"] for c in candidates]
    return report(client, copy_id, raised=ids, notice=notice if ids else "")


FALSE = {
    "rule": "form.missing_field",
    "worker_id": None,
    "line_no": None,
    "expected": "Every required field filled in",
    "actual": "Blank: fein",
    "shortfall_cents": None,
    "citation": "MW-562 payroll certification",
}
