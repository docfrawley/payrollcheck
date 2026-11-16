"""Send-back notices: each submission's notice, as the payroll agent drafted it and
as a reviewer edited it, both kept, and who sent it and when. A reviewer saves an
edit without sending it, and Send back sends the edit, or the draft when there is
none."""

from fastapi import HTTPException
from sqlalchemy import (
    ColumnElement,
    Connection,
    RowMapping,
    func,
    insert,
    select,
    update,
)

from backend.database import notices, now
from backend.models import Reviewer

NOTHING_TO_SEND = (
    "{case_id} has no notice to send: write one for its subcontractor first"
)


def latest(case: RowMapping) -> tuple[ColumnElement[bool], ...]:
    """The latest submission's notice."""
    return (
        notices.c.case_id == case["case_id"],
        notices.c.submission_no == case["latest_submission_no"],
    )


def save_notice(
    db: Connection, case: RowMapping, text: str, reviewer: Reviewer
) -> None:
    """Keep the reviewer's edit of the latest submission's notice beside the
    agent's draft, or as a notice of its own where the agent drafted none."""
    edit = {"edited_text": text, "edited_by": reviewer.name, "edited_at": now()}
    saved = db.execute(update(notices).where(*latest(case)).values(**edit))
    if saved.rowcount == 0:
        db.execute(
            insert(notices).values(
                case_id=case["case_id"],
                submission_no=case["latest_submission_no"],
                **edit,
            )
        )


def notice_to_send(db: Connection, case: RowMapping) -> str:
    """The text Send back sends: the reviewer's edit, or the agent's draft, or a
    422 when there is neither."""
    query = select(func.coalesce(notices.c.edited_text, notices.c.draft, ""))
    text = db.execute(query.where(*latest(case))).scalar_one_or_none() or ""
    if not text.strip():
        raise HTTPException(422, NOTHING_TO_SEND.format(case_id=case["case_id"]))
    return text


def mark_sent(
    db: Connection, case: RowMapping, reviewer: Reviewer, sent_at: str
) -> None:
    """Record who sent the latest submission's notice, by name, and when."""
    db.execute(
        update(notices)
        .where(*latest(case))
        .values(sent_by=reviewer.name, sent_at=sent_at)
    )
