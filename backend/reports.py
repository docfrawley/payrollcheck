"""An exception report checked against the attempt's candidates and recorded with
its notice: the guarantee that no exception carries a shortfall no check tool
found. Each refusal is a 422 that says what's wrong, so the agent can put it
right."""

from fastapi import HTTPException
from sqlalchemy import Connection, RowMapping, insert, update

from backend.candidates import attempts_candidates, checks_run_on
from backend.database import candidates, exceptions, notices, now
from backend.models import (
    AddedException,
    ExceptionReport,
    ExceptionSource,
    ExceptionStatus,
)
from backend.rule_codes import CHECKS, RULES

NO_CANDIDATE = (
    "No check found {rule}{where} with a shortfall of {cents} cents: an exception "
    "with a shortfall must be one a check tool found"
)
UNKNOWN_CANDIDATE = "Candidate {candidate_id} isn't one of this attempt's findings"
MONEY_RULE = (
    "A {rule} exception{where} carries money: it must be one a check tool found, "
    "raised by its candidate id"
)
TWICE = "Candidate {candidate_id} is both raised and dismissed, or listed twice"
NOT_JUDGED = "Raise or dismiss every finding: candidates {ids} are neither"
BLANK_NOTICE = "A report with exceptions needs a draft send-back notice"
CHECKS_NOT_RUN = "Run every check before reporting: {checks} hasn't run on this attempt"


def where(found: AddedException) -> str:
    return f" for {found.worker_id} on line {found.line_no}" if found.worker_id else ""


def matching(found: AddedException, attempt: dict[int, RowMapping]) -> int | None:
    """The candidate an added exception with a shortfall is, by its rule, worker,
    line and shortfall, or none."""
    for candidate_id, candidate in attempt.items():
        if (
            candidate["rule"],
            candidate["worker_id"],
            candidate["line_no"],
            candidate["shortfall_cents"],
        ) == (found.rule, found.worker_id, found.line_no, found.shortfall_cents):
            return candidate_id
    return None


def judged_candidates(
    report: ExceptionReport, attempt: dict[int, RowMapping]
) -> tuple[list[int], list[AddedException]]:
    """The candidates the report raises, an added exception with a shortfall
    counted as the candidate it matches, and the exceptions it adds of its own.
    Raise a 422 for a shortfall no candidate has, a rule that carries money added
    with none, an unknown or repeated candidate, or a candidate neither raised nor
    dismissed."""
    raised, added = list(report.raised), []
    for found in report.added:
        if found.shortfall_cents is None and RULES[found.rule].money:
            message = MONEY_RULE.format(rule=found.rule, where=where(found))
            raise HTTPException(422, message)
        if found.shortfall_cents is None:
            added.append(found)
            continue
        candidate_id = matching(found, attempt)
        if candidate_id is None:
            message = NO_CANDIDATE.format(
                rule=found.rule, where=where(found), cents=found.shortfall_cents
            )
            raise HTTPException(422, message)
        raised.append(candidate_id)
    judged = raised + [d.candidate_id for d in report.dismissed]
    for candidate_id in judged:
        if candidate_id not in attempt:
            raise HTTPException(
                422, UNKNOWN_CANDIDATE.format(candidate_id=candidate_id)
            )
        if judged.count(candidate_id) > 1:
            raise HTTPException(422, TWICE.format(candidate_id=candidate_id))
    left = sorted(set(attempt) - set(judged))
    if left:
        raise HTTPException(422, NOT_JUDGED.format(ids=", ".join(map(str, left))))
    return raised, added


def record_report(db: Connection, case: RowMapping, report: ExceptionReport) -> None:
    """Record a report the guarantee allows: the candidates raised as exceptions,
    the dismissals with their reasons, the agent's own exceptions with no money,
    and the draft notice. Every check must have run on the attempt first."""
    ran = checks_run_on(db, case["case_id"], case["thread_id"])
    not_run = [check for check in CHECKS if check not in ran]
    if not_run:
        raise HTTPException(422, CHECKS_NOT_RUN.format(checks=", ".join(not_run)))
    attempt = attempts_candidates(db, case)
    raised, added = judged_candidates(report, attempt)
    if (raised or added) and not report.notice.strip():
        raise HTTPException(422, BLANK_NOTICE)
    case_id, submission_no = case["case_id"], case["latest_submission_no"]
    rows = [
        {
            **{
                field: attempt[candidate_id][field]
                for field in (
                    "rule",
                    "severity",
                    "worker_id",
                    "line_no",
                    "expected",
                    "actual",
                    "shortfall_cents",
                    "citation",
                )
            },
            "candidate_id": candidate_id,
            "source": ExceptionSource.CHECK,
        }
        for candidate_id in raised
    ] + [
        found.model_dump()
        | {
            "severity": RULES[found.rule].severity,
            "candidate_id": None,
            "source": ExceptionSource.AGENT,
        }
        for found in added
    ]
    if rows:
        db.execute(
            insert(exceptions),
            [
                row
                | {
                    "case_id": case_id,
                    "submission_no": submission_no,
                    "raised_by": report.raised_by,
                    "status": ExceptionStatus.OPEN,
                }
                for row in rows
            ],
        )
    for dismissal in report.dismissed:
        db.execute(
            update(candidates)
            .where(candidates.c.candidate_id == dismissal.candidate_id)
            .values(dismissed_because=dismissal.reason)
        )
    if report.notice.strip():
        db.execute(
            insert(notices).values(
                case_id=case_id,
                submission_no=submission_no,
                draft=report.notice.strip(),
                drafted_by=report.raised_by,
                drafted_at=now(),
            )
        )
