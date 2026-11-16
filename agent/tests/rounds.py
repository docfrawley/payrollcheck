"""Rounds of the improver the tests work through the agent's service: a stub
improver that follows a script of tool calls, and stub payroll agents that raise
the check tools' findings once their instructions hold the improver's rule."""

from agent.tests.stubs import (
    NOTICE,
    StubModel,
    call,
    candidates_in,
    report,
    stub,
)
from backend.first_version import INSTRUCTIONS

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


def propose(instructions=VERSION_1 + RULE, **model):
    return call(
        "propose_change",
        instructions=instructions,
        reason="It dismissed findings that were breaches.",
        **(LUNA | model),
    )


def improver(*replies):
    """A stub improver with a script of replies, across its stretches."""
    return stub(*replies)


def whole_round():
    """The improver's replies in a round with one rejection: it reads the results,
    proposes a change, proposes another after the rejection, runs the evaluation,
    proposes a recipe and ends."""
    return improver(
        call("read_results"),
        propose(VERSION_1 + "\nA rule for PC-0311.\n"),
        propose(),
        call("run_evaluation"),
        call("propose_recipe", recipe="1. Read the results.\n", reason="Shorter"),
        "The round is done.",
    )
