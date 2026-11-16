"""Setting the test queue up, straight in the backend's tables."""

from sqlalchemy import delete, select, tuple_, update

from backend.database import SCREENING, cases, engine, labelled_cases, labels


def leave_received(*case_ids):
    """Leave every case but the ones named awaiting review, out of the agent's way."""
    with engine().begin() as db:
        db.execute(update(cases).values(status="awaiting_review"))
        db.execute(
            update(cases).where(cases.c.case_id.in_(case_ids)).values(status="received")
        )


def fewer_labelled_cases(per_set):
    """Keep only the first few labelled cases of each set with an exception label,
    so a round's whole-set evaluations work a few copies each."""
    with engine().begin() as db:
        kept = []
        for labelled_set in ("development", "held_out"):
            query = (
                select(labels.c.case_id)
                .where(
                    labels.c.labelled_set == labelled_set,
                    labels.c.rule != SCREENING,
                )
                .distinct()
                .order_by(labels.c.case_id)
                .limit(per_set)
            )
            kept += [(labelled_set, case_id) for case_id in db.execute(query).scalars()]
        db.execute(
            delete(labelled_cases).where(
                tuple_(labelled_cases.c.labelled_set, labelled_cases.c.case_id).not_in(
                    kept
                )
            )
        )
