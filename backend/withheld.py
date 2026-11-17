"""Withheld text: on a case the screening flagged, the Copilot's reads replace
everything the subcontractor wrote before they answer, so no model sees it: every
text cell of every submission (template.TEXT), the file's name, a worker id that
isn't one of our workers, each exception's and finding's expected and actual,
which can quote a cell, the screening's reason, which can quote the instruction
it found, and the case's notices, whose drafts are written from the exceptions.
Numbers, dates, our records' ids and names, rule codes, shortfalls, citations and
the reviewers' overrides pass. Pure: our records' names say which workers
are ours, and the answers which cases are flagged."""

from typing import Any

from backend.models import (
    Case,
    CaseExceptions,
    ClassificationChange,
    ClassificationChanges,
    Exposure,
    Submission,
)
from data.payroll_world.template import TEXT, WORKER_ID

WITHHELD = "[withheld: screening flag — see case page]"
SCREENED = "Flagged by the screening for an instruction in its text — see case page"
# An exception's or a finding's words, which can quote a cell.
QUOTED = {"expected": WITHHELD, "actual": WITHHELD}
# A notice's words, drafted from the exceptions.
NOTICE_TEXT = {"draft": WITHHELD, "edited_text": WITHHELD}


def worker(worker_id: str | None, ours: set[str]) -> str | None:
    """A worker id as written, if it is one of our workers'."""
    return worker_id if worker_id is None or worker_id in ours else WITHHELD


def cells(record: dict[str, Any], ours: set[str]) -> dict[str, Any]:
    """A certification or a line with what the subcontractor wrote withheld."""
    found = {key: WITHHELD if key in TEXT else value for key, value in record.items()}
    if WORKER_ID in found:
        found[WORKER_ID] = worker(found[WORKER_ID], ours)
    return found


def submission(found: Submission, ours: set[str]) -> Submission:
    """A submission with its file's name and its cells withheld."""
    return found.model_copy(
        update={
            "file_name": WITHHELD,
            "certification": cells(found.certification, ours),
            "lines": [cells(line, ours) for line in found.lines],
        }
    )


def case(found: Case) -> Case:
    """A case in full, withheld if the screening flagged it."""
    if not found.screening_flag:
        return found
    ours = {w.worker_id for w in found.workers}
    return found.model_copy(
        update={
            "screening_reason": SCREENED,
            "submissions": [submission(s, ours) for s in found.submissions],
            "exceptions": [
                e.model_copy(update=QUOTED | {"worker_id": worker(e.worker_id, ours)})
                for e in found.exceptions
            ],
            "candidates": [
                c.model_copy(update=QUOTED | {"worker_id": worker(c.worker_id, ours)})
                for c in found.candidates
            ],
            "notice": found.notice and found.notice.model_copy(update=NOTICE_TEXT),
            "sent_notices": [
                n.model_copy(update={"body": WITHHELD, "draft": WITHHELD})
                for n in found.sent_notices
            ],
        }
    )


def named(worker_id: str | None, worker_name: str | None) -> str | None:
    """A worker id beside our records' name for it, which only ours have."""
    return WITHHELD if worker_id is not None and worker_name is None else worker_id


def exceptions(found: CaseExceptions) -> CaseExceptions:
    """A case's open exceptions, withheld if the screening flagged it."""
    if not found.screening_flag:
        return found
    return found.model_copy(
        update={
            "screening_reason": SCREENED,
            "exceptions": [
                e.model_copy(
                    update=QUOTED | {"worker_id": named(e.worker_id, e.worker_name)}
                )
                for e in found.exceptions
            ],
        }
    )


def exposure(found: Exposure) -> Exposure:
    """Exposure, each flagged case's worker ids withheld where they aren't ours."""
    return found.model_copy(
        update={
            "exceptions": [
                e.model_copy(update={"worker_id": named(e.worker_id, e.worker_name)})
                if e.screening_flag
                else e
                for e in found.exceptions
            ]
        }
    )


def changes(found: ClassificationChanges) -> ClassificationChanges:
    """Classification changes, each side withheld where its case is flagged."""
    return found.model_copy(update={"changes": [change(c) for c in found.changes]})


def change(found: ClassificationChange) -> ClassificationChange:
    """A classification change: the week before's classification withheld if that
    case is flagged, and this week's, its note and an unknown worker if this one
    is."""
    update: dict[str, Any] = {}
    if found.screening_flag_before:
        update["classification_before"] = WITHHELD
    if found.screening_flag:
        update |= {
            "classification_after": WITHHELD,
            "line_notes": WITHHELD,
            "worker_id": named(found.worker_id, found.worker_name),
        }
    return found.model_copy(update=update)
