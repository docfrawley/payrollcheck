"""Rounds of the improver the tests work through the agent's service: a stub
improver that follows a script of tool calls, and stub payroll agents that raise
the check tools' findings once their instructions hold the improver's rule."""

import json
from typing import Any

from langchain_core.messages import ToolMessage

from agent.tests.stubs import (
    NOTICE,
    StubModel,
    call,
    candidates_in,
    report,
    stub,
)
from backend.first_version import INSTRUCTIONS
from backend.parameters import FIRST_PARAMETERS

# What the improver adds to the payroll agent's instructions in the tests, and what
# makes the stub payroll agents raise what the checks found.
RULE = "\nA general rule: raise every finding the check tools make.\n"
VERSION_1 = (INSTRUCTIONS / "payroll.md").read_text(encoding="utf-8")
LUNA = {"model": "openai/gpt-6-luna", "reasoning_effort": "low"}


class RuleFollowingModel(StubModel):
    """A stub payroll agent that dismisses every finding of the check tools, or once
    its instructions hold the rule, raises them all."""

    def next_reply(self, messages):
        ids = [c["candidate_id"] for c in candidates_in(messages)]
        if RULE.strip() in messages[0].content:
            return report(raised=ids, notice=NOTICE if ids else "")
        reason = "It doesn't look like a breach."
        return report(dismissed=[{"candidate_id": i, "reason": reason} for i in ids])


def payroll_agents_model():
    return RuleFollowingModel(messages=iter(()))


def cited(messages):
    """The first case the improver's latest read of the results holds, as it would
    cite it, or none."""
    results = [
        m for m in messages if isinstance(m, ToolMessage) and m.name == "read_results"
    ]
    if not results:
        return []
    view = json.loads(results[-1].text)
    return [case["case_id"] for case in view["development_mistakes"]["shown"]][:1]


def propose(instructions=VERSION_1 + RULE, **changes) -> Any:
    """A reply worked out from the prompt, as the stub models take one: a change
    citing a case the results it read hold."""

    def reply(messages):
        change = {
            "instructions": instructions,
            "parameters": FIRST_PARAMETERS,
            "reason": "It dismissed findings that were breaches.",
            "case_ids": cited(messages),
        }
        return call("propose_change", change=change | LUNA | changes)

    return reply


def improver(*replies):
    """A stub improver with a script of replies, across its stretches."""
    return stub(*replies)


def whole_round():
    """The improver's replies in a round with one rejection: it reads the results,
    proposes a change, proposes another after the rejection, runs the evaluation,
    proposes a recipe and ends."""
    return improver(
        call("read_results"),
        propose(VERSION_1 + "\nA rule for weekend premiums.\n"),
        propose(),
        call("run_evaluation"),
        call("propose_recipe", recipe="1. Read the results.\n", reason="Shorter"),
        "The round is done.",
    )
