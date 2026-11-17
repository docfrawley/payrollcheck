"""The send-back notice the Copilot drafts for a reviewer, worded by the backend
from the case's records, so no model writes it: an opening naming the case, its
project and week, a paragraph for each exception open on the latest submission in
its rule's own words, with the worker, the line, what was expected and paid where
it records them, and the amount owed, then the total owed and a closing that asks
for a corrected payroll and gives no legal interpretation."""

from backend.models import CaseExceptions, OpenException
from backend.money import cents_in_dollars
from backend.rule_codes import RULES
from backend.wording import in_words

OPENING = (
    "Certified payroll {case_id}, {project_name}, week ending {week_ending}\n\n"
    "We reviewed this certified payroll and found {count} to correct before we "
    "can accept it."
)
ON_A_LINE = "{worker}, line {line_no}"
ON_A_LINE_ALONE = "Line {line_no}"
ON_THE_PAYROLL = "The payroll as a whole"
FINDING = "{number}. {name}. {where}.{compared}{owed} {asks}"
COMPARED = " We expected {expected}; the payroll shows {actual}."
OWED = " Amount owed: {amount}."
TOTAL = "In all, {amount} is owed to the workers on this payroll."
CLOSING = (
    "Please make these corrections, pay any amounts owed, and send us a corrected "
    "certified payroll for this week. If anything here is unclear, reply to this "
    "email and we will go through it with you."
)


def draft(found: CaseExceptions, project_name: str) -> str:
    """The notice for a case's open exceptions."""
    count = len(found.exceptions)
    items = "1 item" if count == 1 else f"{count} items"
    parts = [
        OPENING.format(
            case_id=found.case_id,
            project_name=project_name,
            week_ending=in_words(found.week_ending),
            count=items,
        ),
        *(finding(n, e) for n, e in enumerate(found.exceptions, start=1)),
    ]
    if found.shortfall_cents:
        parts.append(TOTAL.format(amount=found.shortfall))
    parts.append(CLOSING)
    return "\n\n".join(parts)


def finding(number: int, exception: OpenException) -> str:
    rule = RULES[exception.rule]
    cents = exception.shortfall_cents
    return FINDING.format(
        number=number,
        name=rule.name,
        where=where(exception),
        compared=compared(exception),
        owed=OWED.format(amount=cents_in_dollars(cents)) if cents else "",
        asks=rule.asks,
    )


def compared(exception: OpenException) -> str:
    """What was expected beside what was paid, where the exception records them;
    an exception carried over from our history may not."""
    if not (exception.expected.strip() and exception.actual.strip()):
        return ""
    return COMPARED.format(expected=exception.expected, actual=exception.actual)


def where(exception: OpenException) -> str:
    """Where on the payroll an exception is: a worker's line, named from our
    records where we know the worker, or the payroll as a whole."""
    if exception.line_no is None:
        return ON_THE_PAYROLL
    if exception.worker_name is None:
        return ON_A_LINE_ALONE.format(line_no=exception.line_no)
    return ON_A_LINE.format(worker=exception.worker_name, line_no=exception.line_no)
