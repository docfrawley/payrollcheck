"""The business date in force: the app's "today", the setting when it has one, or
the real date in New Jersey, and its operation for every signed-in reviewer, which
the header of every page shows."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Connection

from backend.dependencies import Database, SignedInReviewer
from backend.lookups import current_settings

router = APIRouter()

# Our projects are in New Jersey, so the real date is the date there, wherever the
# backend runs; on AWS the clock is in UTC.
NEW_JERSEY = ZoneInfo("America/New_York")


class BusinessDate(BaseModel):
    business_date: date
    real_date: bool


def real_date() -> date:
    """Today in New Jersey."""
    return datetime.now(NEW_JERSEY).date()


def business_date_in_force(db: Connection) -> BusinessDate:
    """The setting, or the real date when there is none."""
    setting = current_settings(db).business_date
    return BusinessDate(business_date=setting or real_date(), real_date=setting is None)


def business_date(db: Connection) -> date:
    return business_date_in_force(db).business_date


@router.get(
    "/api/business-date",
    operation_id="get_business_date",
    dependencies=[SignedInReviewer],
)
def get_business_date(db: Database) -> BusinessDate:
    """Get the business date in force, and whether it is the real date."""
    return business_date_in_force(db)
