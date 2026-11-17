"""The judge: Jev, through OpenRouter's Decisions endpoint, grades the payroll agent's
draft send-back notice against the business's rubric, from the notice and the
exceptions it goes with, with no reference notice. The endpoint is in alpha, so
this is the one module that calls it, and the one that knows its address."""

import logging
import os
from functools import cache
from statistics import fmean

from openrouter import OpenRouter
from openrouter.components import DecisionsNoulAnswer, QuestionsTypedDict
from openrouter.utils import BackoffStrategy, RetryConfig

from backend.models import NoticeGrade, NoticeToGrade

JEV = "typesafe/jev-1.13"
# The client ignores an address set on it, so each call passes this one.
JUDGE_URL = os.getenv("JUDGE_URL", "https://openrouter.ai")
TIMEOUT_MS = 10_000
# No retries: a notice the judge can't grade at once is left ungraded.
NO_RETRIES = RetryConfig("none", BackoffStrategy(0, 0, 0, 0), False)

# The rubric's four points, each the chance that the notice keeps to it.
QUESTIONS: dict[str, QuestionsTypedDict] = {
    "covers_every_exception": {
        "type": "noul",
        "instructions": "`notice` is a general contractor's notice to a "
        "subcontractor about the exceptions in `exceptions`, found on one "
        "certified payroll. Does it cover every exception in `exceptions`?",
        "criteria": {
            "true": "Each exception is in the notice: its worker and line, or the "
            "payroll as a whole, and what is wrong.",
            "false": "At least one exception is left out, or the notice raises "
            "something that isn't in `exceptions`.",
        },
    },
    "amounts_match": {
        "type": "noul",
        "instructions": "Do the amounts in `notice` match `exceptions`?",
        "criteria": {
            "true": "Every dollar amount, rate, hour and date the notice gives is "
            "the one in `exceptions`, and every shortfall is the exception's.",
            "false": "An amount differs from `exceptions`, or the notice gives an "
            "amount that isn't there.",
        },
    },
    "plain_language": {
        "type": "noul",
        "instructions": "Is `notice` in plain language a subcontractor's payroll "
        "clerk can act on?",
        "criteria": {
            "true": "Short, plain sentences that say what is wrong, on which "
            "worker's line, and what to correct and send back.",
            "false": "Jargon, rule codes or internal terms left unexplained, or "
            "no clear statement of what to correct.",
        },
    },
    "no_legal_interpretation": {
        "type": "noul",
        "instructions": "Does `notice` keep from interpreting the law?",
        "criteria": {
            "true": "It states what the records show and the rule or rate record "
            "cited, and asks for a correction.",
            "false": "It interprets the law, gives legal advice, says what the "
            "subcontractor is liable for or threatens legal consequences.",
        },
    },
}

log = logging.getLogger(__name__)


class Ungradable(Exception):
    """The judge answered without the rubric's four points."""


@cache
def client() -> OpenRouter:
    """The OpenRouter client, which reads its key from OPENROUTER_API_KEY."""
    return OpenRouter()


def ask(notice: NoticeToGrade) -> NoticeGrade:
    """Ask Jev once to grade a notice against the rubric."""
    response = client().alpha.decisions.create(
        model=JEV,
        state=notice.model_dump(),
        questions=QUESTIONS,
        server_url=JUDGE_URL,
        timeout_ms=TIMEOUT_MS,
        retries=NO_RETRIES,
    )
    chances: dict[str, float] = {}
    for name in QUESTIONS:
        point = response.answers.get(name)
        if not isinstance(point, DecisionsNoulAnswer):
            raise Ungradable(f"The judge answered {response.answers}")
        chances[name] = point.noul
    return NoticeGrade(
        **chances, score=fmean(chances.values()), cost=response.usage.cost or 0
    )


def grade(notice: NoticeToGrade) -> NoticeGrade | None:
    """Grade a notice, or return nothing when the judge can't, such as on a
    timeout, which is logged."""
    try:
        return ask(notice)
    except Exception:  # an ungraded notice never stops an evaluation finishing
        log.exception("The judge couldn't grade the notice")
        return None
