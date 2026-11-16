"""The outbox: each notice sent to a subcontractor, recorded with who it went to, its
subject and body, who sent it and when, one for each submission. No real email is
sent: deliver is the one place a real email provider would plug in."""

from datetime import date

from sqlalchemy import Connection, RowMapping, insert, select

from backend.database import notices, outbox, subcontractors
from backend.models import OutboxRecord, Reviewer

SUBJECT = (
    "Certified payroll {case_id}, {project_name}, week ending {week_ending}: "
    "corrections needed"
)


def deliver(outbox_row: RowMapping) -> None:
    """Send a notice the outbox recorded. For now the record is all there is."""


def in_words(day: str) -> str:
    """A date as the subject gives it, such as Nov 22, 2026."""
    found = date.fromisoformat(day)
    return f"{found:%b} {found.day}, {found.year}"


def sender(reviewer: Reviewer) -> str:
    """Who a notice is from, as an email gives it."""
    return f"{reviewer.name} <{reviewer.email}>"


def send(
    db: Connection, case: RowMapping, body: str, reviewer: Reviewer, sent_at: str
) -> None:
    """Record a notice to the case's subcontractor's payroll contact in the outbox,
    from the reviewer, and deliver it."""
    to = db.execute(
        select(subcontractors.c.contact_email).where(
            subcontractors.c.subcontractor_id == case["subcontractor_id"]
        )
    ).scalar_one()
    subject = SUBJECT.format(
        case_id=case["case_id"],
        project_name=case["project_name"],
        week_ending=in_words(case["week_ending"]),
    )
    row = (
        db.execute(
            insert(outbox)
            .values(
                case_id=case["case_id"],
                submission_no=case["latest_submission_no"],
                to_address=to,
                subject=subject,
                body=body,
                sent_by=sender(reviewer),
                sent_at=sent_at,
            )
            .returning(outbox)
        )
        .mappings()
        .one()
    )
    deliver(row)


def sent_to(db: Connection, case_id: str) -> list[OutboxRecord]:
    """A case's notices sent, newest first, each with the agent's draft of it."""
    query = (
        select(outbox, notices.c.draft)
        .outerjoin(
            notices,
            (notices.c.case_id == outbox.c.case_id)
            & (notices.c.submission_no == outbox.c.submission_no),
        )
        .where(outbox.c.case_id == case_id)
        .order_by(outbox.c.outbox_id.desc())
    )
    return [OutboxRecord(**row) for row in db.execute(query).mappings()]
