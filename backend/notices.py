"""Send-back notices: each submission's notice, as the payroll agent drafted it and
as a reviewer edited it, both kept, and who sent it and when. A reviewer saves an
edit without sending it, and Send back sends the edit, or the draft when there is
none."""

from fastapi import HTTPException
from sqlalchemy import (
    ColumnElement,
    Connection,
    RowMapping,
    and_,
    func,
    insert,
    select,
    update,
)

from backend.database import cases, notices, now
from backend.models import NoticeEdit, Reviewer

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
    query = select(func.coalesce(notices.c.edited_text, notices.c.draft))
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


def drafts_of(db: Connection, case_ids: list[str]) -> dict[str, str]:
    """The agent's draft of each case's latest submission's notice, where it wrote
    one, in one query."""
    query = (
        select(notices.c.case_id, notices.c.draft)
        .join(
            cases,
            and_(
                cases.c.case_id == notices.c.case_id,
                cases.c.latest_submission_no == notices.c.submission_no,
            ),
        )
        .where(notices.c.case_id.in_(case_ids), notices.c.draft.is_not(None))
    )
    return {case_id: draft for case_id, draft in db.execute(query)}


def edited_between(
    db: Connection, start: str, end: str, most: int
) -> tuple[int, list[NoticeEdit]]:
    """How many of the agent's drafts a reviewer rewrote from one moment up to
    another, and the newest of them, each beside the edit."""
    edited = (
        notices.c.edited_at >= start,
        notices.c.edited_at < end,
        notices.c.draft.is_not(None),
        notices.c.edited_text != notices.c.draft,
    )
    total = db.execute(select(func.count()).where(*edited)).scalar_one()
    query = (
        select(notices).where(*edited).order_by(notices.c.edited_at.desc()).limit(most)
    )
    return total, [NoticeEdit(**row) for row in db.execute(query).mappings()]
