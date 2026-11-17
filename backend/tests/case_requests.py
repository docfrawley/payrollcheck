"""Requests the backend's tests send to work a case, as the agent does, and to
review it, as a reviewer does."""

from backend.rule_codes import CHECKS
from backend.tests.sign_in import DANA, signed_in

# Who raises the exceptions the tests record, as the payroll agent says it.
MAKER = "PayrollCheck Agent, version 1"
NOTICE = "Please correct the base rate for W-001 on line 1 and resubmit."


def start(client, case_id, thread_id="t-1"):
    return client.post(f"/api/cases/{case_id}/start", json={"thread_id": thread_id})


def record_step(client, case_id, kind, content, sources=()):
    """Record a step as the agent does, with the context files a lookup came from,
    and none for any other step."""
    body = {"kind": kind, "content": content, "sources": list(sources)}
    return client.post(f"/api/cases/{case_id}/steps", json=body)


def finding(rule="rate.base_short", worker_id="W-001", line_no=1, **changes):
    """A check tool's finding, as the agent records it: a base rate short unless
    told otherwise."""
    return {
        "rule": rule,
        "worker_id": worker_id,
        "line_no": line_no,
        "expected": "$58.85/h",
        "actual": "$58.84/h",
        "shortfall_cents": 32,
        "citation": "Rate determination MID-2025-11, Electrician Journeyman",
    } | changes


def record_findings(client, case_id, check="check_rates", findings=()):
    body = {"check": check, "findings": list(findings)}
    return client.post(f"/api/cases/{case_id}/candidates", json=body)


def flag(client, case_id, reason="It says to skip the rate check."):
    return client.post(f"/api/cases/{case_id}/screening-flag", json={"reason": reason})


def run_the_other_checks(client, case_id):
    """Record every check the attempt hasn't run as finding nothing, as the check
    node runs them all before the model reports."""
    case = client.get(f"/api/cases/{case_id}").json()
    for check in CHECKS:
        if check not in case.get("checks_run", CHECKS):
            record_findings(client, case_id, check=check)


def report(client, case_id, raised=(), notice="", **judged):
    """Record an exception report as the payroll agent does, with any dismissed or
    added exceptions given, once every check has run."""
    run_the_other_checks(client, case_id)
    body = {
        "raised": list(raised),
        "dismissed": list(judged.get("dismissed", ())),
        "added": list(judged.get("added", ())),
        "notice": notice,
        "raised_by": MAKER,
    }
    return client.post(f"/api/cases/{case_id}/report", json=body)


def awaiting_review(client, case_id, *findings):
    """Start a case, record the findings given as one check's, raise them all and
    report, which leaves the case awaiting review, and return it."""
    start(client, case_id)
    candidates = record_findings(client, case_id, findings=findings).json()
    ids = [c["candidate_id"] for c in candidates]
    return report(client, case_id, raised=ids, notice=NOTICE if ids else "").json()


def fail(client, case_id, reason="The model timed out"):
    return client.post(f"/api/cases/{case_id}/failure", json={"reason": reason})


def sign_off(client, case_id, email=DANA):
    return client.post(f"/api/cases/{case_id}/sign-off", headers=signed_in(email))


def shown_notice(client, case_id, email=DANA):
    """A case's notice as its page shows it: the reviewer's edit, or the draft."""
    found = client.get(f"/api/cases/{case_id}", headers=signed_in(email)).json()
    notice = found.get("notice") or {}
    return notice.get("edited_text") or notice.get("draft") or ""


def send_back(client, case_id, email=DANA, shown=None):
    """Send a case back with its notice as the reviewer saw it: as its page shows
    it now, unless the test says what they saw."""
    text = shown_notice(client, case_id, email) if shown is None else shown
    return client.post(
        f"/api/cases/{case_id}/send-back",
        json={"text": text},
        headers=signed_in(email),
    )


def send_again(client, case_id, email=DANA, shown=None):
    """Send a returned case's notice again, as the reviewer saw it."""
    text = shown_notice(client, case_id, email) if shown is None else shown
    return client.post(
        f"/api/cases/{case_id}/notice/resend",
        json={"text": text},
        headers=signed_in(email),
    )


def save_notice(client, case_id, text, email=DANA):
    """Save an edit of a case's notice as a reviewer does, without sending it."""
    return client.put(
        f"/api/cases/{case_id}/notice", json={"text": text}, headers=signed_in(email)
    )


def record_call(client, case_id, run_id, **usage):
    body = {"input_tokens": 1200, "output_tokens": 300, "cost": 0.0042} | usage
    return client.post(
        f"/api/cases/{case_id}/model-calls", json={"run_id": run_id, **body}
    )


def record_time(client, case_id, run_id, seconds=12.5):
    return client.post(
        f"/api/cases/{case_id}/work-times",
        json={"run_id": run_id, "seconds": seconds},
    )
