"""The outbox: each notice sent to a subcontractor, recorded with who it went to, its
subject and body, who sent it and when: one for each send, so a notice sent again
on a case Returned to sub is a record of its own. No real email is
sent: deliver is the one place a real email provider would plug in."""

from sqlalchemy import Connection, RowMapping, insert, select

from backend import notices
from backend.database import now, outbox, subcontractors
from backend.models import OutboxRecord, Reviewer
from backend.wording import in_words

SUBJECT = (
    "Certified payroll {case_id}, {project_name}, week ending {week_ending}: "
    "corrections needed"
)


def deliver(outbox_row: RowMapping) -> None:
    """Send a notice the outbox recorded. For now the record is all there is."""


def sender(reviewer: Reviewer) -> str:
    """Who a notice is from, as an email gives it."""
    return f"{reviewer.name} <{reviewer.email}>"


def send_notice(
    db: Connection, case: RowMapping, reviewer: Reviewer, shown: str
) -> None:
    """Send the case's notice as the reviewer was shown it: mark it sent, record it
    in the outbox with the draft it came from, to the subcontractor's payroll
    contact, from the reviewer, and deliver it."""
    notice = notices.notice_to_send(db, case, shown)
    sent_at = now()
    notices.mark_sent(db, case, reviewer, sent_at)
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
                body=notice.text,
                draft=notice.draft,
                drafted_by=notice.drafted_by,
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
    """A case's notices sent, newest first, each with the draft it came from."""
    query = (
        select(outbox)
        .where(outbox.c.case_id == case_id)
        .order_by(outbox.c.outbox_id.desc())
    )
    return [OutboxRecord(**row) for row in db.execute(query).mappings()]
