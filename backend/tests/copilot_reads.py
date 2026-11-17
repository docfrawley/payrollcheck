"""The Copilot's reads as the backend's tests send them, as a reviewer, with every
filter left out sent as null, as the Copilot's tools send them, and the expected
answers to its six questions."""

from backend.seeding import DATA
from backend.tests.sign_in import MARCUS, signed_in
from data.payroll_world.expected_answers import answer_to, read_expected

READS = "/api/copilot"
CASE_FILTERS = (
    "project_id",
    "subcontractor_id",
    "status",
    "period",
    "has_open_exceptions",
    "flag",
)
EXPOSURE_FILTERS = ("project_id", "subcontractor_id", "period")
LAST_WEEK = {"kind": "last_week"}
THIS_MONTH = {"kind": "this_month"}
LAST_FOUR_WEEKS = {"kind": "last_weeks", "count": 4}


def with_nulls(names, **given):
    return {name: None for name in names} | given


def ask(client, path, body, email=MARCUS):
    return client.post(f"{READS}{path}", json=body, headers=signed_in(email))


def read(client, path, email=MARCUS):
    return client.get(f"{READS}{path}", headers=signed_in(email))


def find_cases(client, email=MARCUS, **filters):
    return ask(client, "/cases", with_nulls(CASE_FILTERS, **filters), email)


def exposure(client, email=MARCUS, **filters):
    return ask(client, "/exposure", with_nulls(EXPOSURE_FILTERS, **filters), email)


def filings(client, period, email=MARCUS, project_id=None):
    body = {"period": period, "project_id": project_id}
    return ask(client, "/filings", body, email)


def classification_changes(client, period, email=MARCUS, project_id=None):
    body = {"period": period, "project_id": project_id}
    return ask(client, "/classification-changes", body, email)


def expected_answer(number):
    """The expected answer to the Copilot's question of this number, from 1."""
    return answer_to(read_expected(DATA), number)
