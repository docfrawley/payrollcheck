"""The context layer's five payroll lookups, which both agents have: each calls the
context layer's tool of the same name on the route in the agent's context, and
gives the model the answer and, as its artifact, a lookup step naming what was
looked up and the files the answer came from."""

import datetime
from typing import Annotated, Any, Literal, Protocol, runtime_checkable

from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field

from agent.json_text import as_json
from agent.routes import Route, Target

# The context layer's tools, by the names it serves them under.
GET_WAGE_RATE = "get_wage_rate"
CHECK_REGISTRATION = "check_registration"
CHECK_APPRENTICE = "check_apprentice"
GET_FILING_RULES = "get_filing_rules"
LOOKUP_PAYROLL_TERM = "lookup_payroll_term"
# The context files an answer came from, each with its system, owner and review
# date, and the lookup step a tool gives as its artifact.
Sources = list[dict[str, str]]
Lookup = tuple[Literal["lookup"], str, Sources]
Day = Annotated[datetime.date, "YYYY-MM-DD"]


# Checkable at run time, since an agent's context is validated when a tool reads it.
@runtime_checkable
class RouteContext(Protocol):
    """An agent's context, which holds the route its tools take."""

    route: Route


def on_context(
    runtime: ToolRuntime[RouteContext], operation: str, **inputs: Any
) -> Any:
    """Call one of the context layer's tools on the agent's route."""
    return runtime.context.route.call(Target.CONTEXT, operation, inputs)


def looked_up(answer: dict[str, Any], what: str) -> tuple[str, Lookup]:
    """A context layer's answer for the model, and a lookup step that says what
    was looked up and the files the answer came from."""
    return as_json(answer), ("lookup", what, answer["sources"])


class RateQuestion(BaseModel):
    """A day's work to find the rate for."""

    craft: str = Field(description="Such as electrician or operating_engineer")
    classification: str = Field(description="journeyman or foreman")
    county: str
    award_date: datetime.date = Field(description="The project's award date")
    work_date: datetime.date


@tool(response_format="content_and_artifact")
def get_wage_rate(
    question: RateQuestion, runtime: ToolRuntime[RouteContext]
) -> tuple[str, Lookup]:
    """Get the rate for a day's work: the award-date determination's latest row."""
    answer = on_context(runtime, GET_WAGE_RATE, **question.model_dump(mode="json"))
    what = (
        f"Rate: {question.craft} {question.classification}, {question.county}, "
        f"worked {question.work_date}"
    )
    return looked_up(answer, what)


@tool(response_format="content_and_artifact")
def check_registration(
    registration_no: str, date: Day, runtime: ToolRuntime[RouteContext]
) -> tuple[str, Lookup]:
    """Check a contractor's public works registration and its status on a date."""
    answer = on_context(
        runtime,
        CHECK_REGISTRATION,
        registration_no=registration_no,
        date=date.isoformat(),
    )
    return looked_up(answer, f"Registration {registration_no} on {date}")


@tool(response_format="content_and_artifact")
def check_apprentice(
    worker_id: str, date: Day, runtime: ToolRuntime[RouteContext]
) -> tuple[str, Lookup]:
    """Check whether a worker is a registered apprentice, and their level then."""
    answer = on_context(
        runtime, CHECK_APPRENTICE, worker_id=worker_id, date=date.isoformat()
    )
    return looked_up(answer, f"Apprentice {worker_id} on {date}")


@tool(response_format="content_and_artifact")
def get_filing_rules(runtime: ToolRuntime[RouteContext]) -> tuple[str, Lookup]:
    """Get the filing rules: when a payroll is due, its numbering, corrections."""
    return looked_up(on_context(runtime, GET_FILING_RULES), "The filing rules")


@tool(response_format="content_and_artifact")
def lookup_payroll_term(
    term: str, runtime: ToolRuntime[RouteContext]
) -> tuple[str, Lookup]:
    """Look up a payroll term in the compliance glossary: its definition."""
    answer = on_context(runtime, LOOKUP_PAYROLL_TERM, term=term)
    return looked_up(answer, f'Term "{term}"')


CONTEXT_TOOLS = [
    get_wage_rate,
    check_registration,
    check_apprentice,
    get_filing_rules,
    lookup_payroll_term,
]
