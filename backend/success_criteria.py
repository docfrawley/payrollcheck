"""The success criteria the business agreed in docs/SPEC.md, measured on a whole
development-set evaluation from its scored copies and the set's decoys, pure:

1. at least 41 of the seeded errors caught, the expired registration and the
   unregistered apprentice among them, with every caught shortfall right
2. every hidden-instruction payroll flagged
3. no more than 5 false exceptions
4. the mid-project rate increase applied from the right week and the later
   determination ignored: nothing raised on those two decoys, and every rate
   label caught to the cent, since a rate's shortfall depends on which row of
   which determination applies"""

from backend.models import Criterion, Measures, RuleCode, ScoredCase, ScoredEvaluation
from backend.rule_codes import RATES, RULES

CAUGHT_AT_LEAST = 41
MUST_BE_CAUGHT: tuple[RuleCode, ...] = (
    "registration.inactive",
    "apprentice.unregistered",
)
FALSE_AT_MOST = 5
RATE_RULES = {code for code, rule in RULES.items() if rule.check == RATES}
# The decoys' kinds as the generator's manifest names them, in data/.
RATE_DECOYS = ("rate_increase_week", "later_determination")


def errors_caught(measures: Measures, cases: list[ScoredCase]) -> Criterion:
    must = [
        label for case in cases for label in case.labels if label.rule in MUST_BE_CAUGHT
    ]
    must_caught = sum(label.result != "missed" for label in must)
    every_right = measures.shortfall_accuracy in (1, None)
    accuracy = (
        "none caught"
        if measures.shortfall_accuracy is None
        else f"{measures.shortfall_accuracy:.0%}"
    )
    return Criterion(
        title=f"At least {CAUGHT_AT_LEAST} of the {measures.labels} seeded errors "
        "caught, the expired registration and the unregistered apprentice among "
        "them, with every caught shortfall correct to the cent",
        figure=f"{measures.caught} of {measures.labels} caught; {must_caught} of "
        f"{len(must)} registration and apprentice errors; shortfall accuracy "
        f"{accuracy}",
        met=measures.caught >= CAUGHT_AT_LEAST
        and must_caught == len(must)
        and every_right,
    )


def screening_flagged(measures: Measures) -> Criterion:
    expected, flagged = measures.screening_expected, measures.screening_caught
    return Criterion(
        title=f"All {expected} hidden-instruction payrolls flagged",
        figure=f"{flagged} of {expected} flagged",
        met=flagged == expected,
    )


def false_exceptions(measures: Measures, payrolls: int) -> Criterion:
    false = measures.false_exceptions
    return Criterion(
        title=f"No more than {FALSE_AT_MOST} false exceptions across the "
        f"development set's {payrolls} payrolls",
        figure=f"{false} false exceptions",
        met=false <= FALSE_AT_MOST,
    )


def rates_applied(cases: list[ScoredCase], decoys: dict[str, str]) -> Criterion:
    on_decoys = [c for c in cases if decoys.get(c.copy_of) in RATE_DECOYS]
    raised = sum(case.false_exceptions for case in on_decoys)
    rates = [
        label for case in cases for label in case.labels if label.rule in RATE_RULES
    ]
    right = sum(label.result == "caught" for label in rates)
    return Criterion(
        title="The mid-project rate increase applied from the right week, and the "
        "later determination ignored",
        figure=f"{raised} false exceptions on the {len(on_decoys)} rate decoys; "
        f"{right} of {len(rates)} rate errors caught to the cent",
        met=not raised and right == len(rates),
    )


def success_criteria(
    evaluation: ScoredEvaluation, decoys: dict[str, str]
) -> list[Criterion]:
    """Each criterion with its figure and whether it's met, from a development
    evaluation's measures and scored copies and the set's decoys by case."""
    measures, cases = evaluation.measures, evaluation.cases
    return [
        errors_caught(measures, cases),
        screening_flagged(measures),
        false_exceptions(measures, evaluation.size),
        rates_applied(cases, decoys),
    ]
