"""What the Copilot's reads take: a period by name, which the app resolves from
the business date, and the filters of a search of the queue, each left out as
null for any, as the app's routes take them."""

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from agent.app_terms import Status


class LastWeek(BaseModel):
    """The latest payroll week ending before the business date."""

    kind: Literal["last_week"]


class ThisMonth(BaseModel):
    """Every week ending in the business date's month."""

    kind: Literal["this_month"]


class LastWeeks(BaseModel):
    """The latest number of payroll weeks ending before the business date."""

    kind: Literal["last_weeks"]
    count: int = Field(ge=1, le=52)


class Between(BaseModel):
    """The weeks ending from one Sunday to another, both included, as a tool gave
    them."""

    kind: Literal["between"]
    first: date = Field(description="A week ending, a Sunday")
    last: date = Field(description="A week ending, a Sunday")


# A period by name, which the app resolves from the business date.
Period = Annotated[
    LastWeek | ThisMonth | LastWeeks | Between, Field(discriminator="kind")
]
CaseFlag = Literal["screening", "agent_failed"]


class CaseFilters(BaseModel):
    """What to find the queue's cases by, any left out matching every case."""

    project_id: str | None = None
    subcontractor_id: str | None = None
    status: Status | None = None
    period: Period | None = None
    has_open_exceptions: bool | None = None
    flag: CaseFlag | None = Field(
        default=None, description="Flagged by the screening, or failed twice"
    )


# Every case in the reviewer's scope.
EVERY_CASE = CaseFilters()


class ExposureFilters(BaseModel):
    """Whose underpayment to total, any left out meaning every one in scope."""

    project_id: str | None = None
    subcontractor_id: str | None = None
    period: Period | None = None


class PeriodFilters(BaseModel):
    """A period, and the project to keep to, or every project in scope."""

    period: Period
    project_id: str | None = None


# Every exposure in the reviewer's scope.
ALL_EXPOSURE = ExposureFilters()


def body(filters: BaseModel) -> dict[str, Any]:
    """A request's body: every filter, null where the model left one out, and a
    period as the app reads it."""
    return filters.model_dump(mode="json")
