"""Send-back notices: each submission's notice, as the payroll agent drafted it and
as a reviewer edited it, both kept, and who sent it and when. A reviewer saves an
edit without sending it, and Send back sends the edit, or the draft when there is
none. The Copilot saves a new draft for a reviewer, never over a reviewer's edit
that hasn't been sent."""

from typing import NamedTuple

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
from backend.wording import in_words

NOTHING_TO_SEND = (
    "{case_id} has no notice to send: write one for its subcontractor first"
)
UNSENT_EDIT = "{case_id}'s notice has {name}'s edit of {day}. Edit it on the case page."
CHANGED = (
    "{case_id}'s notice has changed since the page showed it. Read it again before "
    "you send it."
)
COPILOT = "PayrollCheck Copilot for {name}"
# The payroll agent's own drafts, which the judge and the improver read.
BY_THE_AGENT = notices.c.drafted_for.is_(None)


class ToSend(NamedTuple):
    """A notice as it goes out: its text, and the draft it came from."""

    text: str
    draft: str | None
    drafted_by: str | None


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


def save_draft(db: Connection, case: RowMapping, text: str, reviewer: Reviewer) -> str:
    """Keep the Copilot's draft, for a reviewer, of the latest submission's notice
    in place of the old, clearing an edit that was sent, which the outbox keeps,
    and return who it is by; or raise a 409 when a reviewer's edit hasn't been
    sent, which is never overwritten."""
    row = db.execute(select(notices).where(*latest(case))).mappings().first()
    if row is not None and unsent(row):
        message = UNSENT_EDIT.format(
            case_id=case["case_id"],
            name=row["edited_by"],
            day=in_words(row["edited_at"]),
        )
        raise HTTPException(409, message)
    drafted_by = COPILOT.format(name=reviewer.name)
    draft = {
        "draft": text,
        "drafted_by": drafted_by,
        "drafted_at": now(),
        "drafted_for": reviewer.name,
        "edited_text": None,
        "edited_by": None,
        "edited_at": None,
        "sent_by": None,
        "sent_at": None,
    }
    if row is None:
        db.execute(
            insert(notices).values(
                case_id=case["case_id"],
                submission_no=case["latest_submission_no"],
                **draft,
            )
        )
    else:
        db.execute(update(notices).where(*latest(case)).values(**draft))
    return drafted_by


def unsent(row: RowMapping) -> bool:
    """Whether a notice holds a reviewer's edit made since it was last sent."""
    edited = row["edited_at"]
    return edited is not None and (row["sent_at"] is None or edited > row["sent_at"])


def notice_to_send(db: Connection, case: RowMapping, shown: str) -> ToSend:
    """The notice a send sends: the reviewer's edit, or the draft, with the draft;
    or a 422 when there is neither, or a 409 when it isn't what the reviewer was
    shown, as when the Copilot drafted it again meanwhile."""
    row = db.execute(select(notices).where(*latest(case))).mappings().first()
    text: str = (row["edited_text"] or row["draft"] or "") if row else ""
    if row is None or not text.strip():
        raise HTTPException(422, NOTHING_TO_SEND.format(case_id=case["case_id"]))
    if text != shown:
        raise HTTPException(409, CHANGED.format(case_id=case["case_id"]))
    return ToSend(text, row["draft"], row["drafted_by"])


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
        .where(
            notices.c.case_id.in_(case_ids), notices.c.draft.is_not(None), BY_THE_AGENT
        )
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
        BY_THE_AGENT,
        notices.c.edited_text != notices.c.draft,
    )
    total = db.execute(select(func.count()).where(*edited)).scalar_one()
    query = (
        select(notices).where(*edited).order_by(notices.c.edited_at.desc()).limit(most)
    )
    return total, [NoticeEdit(**row) for row in db.execute(query).mappings()]
