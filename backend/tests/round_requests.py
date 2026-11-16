"""Requests the backend's tests send to play out a round of the improver, as the
agent and the dashboard do."""

from sqlalchemy import select, update

from backend.database import SCREENING, engine, labels, runs
from backend.models import LABELLED_SET
from backend.tests.case_requests import flag, record_findings, report, start
from backend.tests.dashboard_reads import read
from backend.tests.rows import newest_round
from backend.tests.run_requests import get_evaluation
from backend.tests.sign_in import DANA, signed_in

# Who each reviewer signs in as, by their id.
EMAILS = {
    "HND-01": DANA,
    "HND-02": "marcus.oyelaran@payrollcheck.example",
}

CHANGE = {
    "instructions": "# Working a case\n\nA rule for stolen phones.\n",
    "model": "openai/gpt-6-luna",
    "reasoning_effort": "low",
    "reason": "Two misclassifications were missed",
}
ALL = 100  # more cases than any set holds
RECIPE = {
    "recipe": "1. Read the results.\n2. Improve the recipe.\n",
    "reason": "Shorter",
}


ROUNDS = "/api/improvement/rounds"


def start_round(client, reviewer_id="HND-01"):
    """Start a round as a reviewer does, and return the start's answer."""
    return client.post(ROUNDS, headers=signed_in(EMAILS[reviewer_id]))


def create_round(client, reviewer_id="HND-01"):
    """Start a round as a reviewer does, which the app creates, and return it as
    the agent reads it, or the start's refusal."""
    started = start_round(client, reviewer_id)
    if started.status_code != 202:
        return started
    return client.get(round_path(newest_round()))


def round_path(round_id):
    return f"/api/rounds/{round_id}"


def fail_round(client, round_id, reason="RuntimeError: The improver broke"):
    """Stop a round whose work failed, as the agent does."""
    return client.post(f"{round_path(round_id)}/failure", json={"reason": reason})


def propose_change(client, round_id, **change):
    return client.post(f"{round_path(round_id)}/proposals/change", json=CHANGE | change)


def propose_recipe(client, round_id):
    return client.post(f"{round_path(round_id)}/proposals/recipe", json=RECIPE)


def review_path(round_id, proposal_id):
    return f"{ROUNDS}/{round_id}/proposals/{proposal_id}"


def approve(client, round_id, proposal_id, reviewer_id="HND-01"):
    """Approve a proposal as a reviewer does, and return the answer."""
    return client.post(
        f"{review_path(round_id, proposal_id)}/approval",
        headers=signed_in(EMAILS[reviewer_id]),
    )


def reject(client, round_id, proposal_id, reviewer_id="HND-01"):
    """Reject a proposal as a reviewer does, with a reason, and return the answer."""
    return client.post(
        f"{review_path(round_id, proposal_id)}/rejection",
        json={"reason": "Keep each rule general"},
        headers=signed_in(EMAILS[reviewer_id]),
    )


def review(client, round_id, proposal_id, verdict="approved", reviewer_id="HND-01"):
    """Approve or reject a proposal as a reviewer does on the Improvement page, and
    return it with its review as the agent reads it, or the refusal."""
    answer = approve if verdict == "approved" else reject
    reviewed = answer(client, round_id, proposal_id, reviewer_id)
    if reviewed.status_code != 202:
        return reviewed
    return client.get(f"{round_path(round_id)}/proposals/{proposal_id}")


def approved_change(client, round_id, **change):
    """Propose a change, approve it as Dana and make it a version under test."""
    proposal = propose_change(client, round_id, **change).json()
    review(client, round_id, proposal["proposal_id"])
    return client.post(f"{round_path(round_id)}/version").json()["number"]


def improver_call(client, round_id, cost):
    return client.post(
        f"{round_path(round_id)}/model-calls",
        json={"input_tokens": 1000, "output_tokens": 200, "cost": cost},
    )


def round_evaluation(client, round_id):
    """Ask for a round's next evaluation, on the set the backend chooses."""
    return client.post(f"/api/runs/rounds/{round_id}/evaluations")


def improvement(client):
    return read(client, "/api/improvement").json()


def stop_round(client, round_id, email=DANA):
    return client.post(f"{ROUNDS}/{round_id}/stop", headers=signed_in(email))


def into_round(round_id, *evaluations):
    """Make evaluations a round's, as if the round had run them."""
    with engine().begin() as db:
        db.execute(
            update(runs)
            .where(runs.c.run_id.in_([e["run_id"] for e in evaluations]))
            .values(round_id=round_id)
        )


def labels_of(evaluation_set):
    """The labels of an evaluation's set, by case."""
    with engine().connect() as db:
        query = (
            select(labels)
            .where(labels.c.labelled_set == LABELLED_SET[evaluation_set])
            .order_by(labels.c.label_id)
        )
        found: dict[str, list] = {}
        for row in db.execute(query).mappings():
            found.setdefault(row["case_id"], []).append(row)
        return found


def as_finding(label):
    """A check's finding that catches a label, to the cent."""
    return {
        "rule": label["rule"],
        "worker_id": label["worker_id"],
        "line_no": label["line_no"],
        "expected": "As the rules require",
        "actual": "As the payroll states",
        "shortfall_cents": label["expected_shortfall_cents"],
        "citation": "The rule",
    }


def work_copy(client, copy_id, found):
    """Work a copy as the agent would: flag it for a screening label, or record
    the labels given as one check's findings, raise them all and report."""
    start(client, copy_id, thread_id=copy_id)
    if any(label["rule"] == SCREENING for label in found):
        flag(client, copy_id)
        return
    findings = [as_finding(label) for label in found]
    candidates = record_findings(client, copy_id, findings=findings).json()
    ids = [c["candidate_id"] for c in candidates]
    report(client, copy_id, raised=ids, notice="Please correct and resubmit.")


def work_copies(client, run, caught):
    """Work the first `caught` of an evaluation's labelled copies, each with its
    labels caught to the cent, or flagged where the screening should flag it. The
    rest are left as they were copied, raising nothing and missing what they
    hold."""
    every = labels_of(run["evaluation_set"])
    labelled = [
        (copy["case_id"], every[copy["case_id"].rsplit("-E", 1)[0]])
        for copy in run["cases"]
        if copy["case_id"].rsplit("-E", 1)[0] in every
    ]
    for copy_id, found in labelled[:caught]:
        work_copy(client, copy_id, found)


def play_out(client, round_id, caught=0, finish=True):
    """Create one of a round's evaluations, work its copies with the labels of
    `caught` of its labelled copies caught, and finish it, as the agent's service
    would. Return the evaluation."""
    run = round_evaluation(client, round_id).json()
    work_copies(client, run, caught)
    if finish:
        client.post(f"/api/runs/{run['run_id']}/finish")
    return get_evaluation(client, run["run_id"])
