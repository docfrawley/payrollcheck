"""Uploading a payroll on a project's page in the tests, as a reviewer does, and the
seeded payrolls to upload."""

from backend.seeding import DATA
from backend.tests.sign_in import DANA, signed_in


def upload(client, project_id, subcontractor_id, payroll, headers=None):
    """Upload a payroll CSV, its file's name and text, for a subcontractor on a
    project's page, as Dana unless the headers say otherwise."""
    file_name, content = payroll
    body = {
        "subcontractor_id": subcontractor_id,
        "file_name": file_name,
        "content": content,
    }
    return client.post(
        f"/api/projects/{project_id}/payrolls",
        json=body,
        headers=headers or signed_in(DANA),
    )


def seeded_payroll(case_id, submission_no=1):
    """A seeded case's submission as the CSV it was uploaded as, and its name."""
    file_name = f"{case_id}-{submission_no}.csv"
    path = DATA / "development" / "payrolls" / file_name
    return file_name, path.read_text(encoding="utf-8")
