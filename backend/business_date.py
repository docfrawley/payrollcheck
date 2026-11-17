"""The business date in force: the app's "today", the setting when it has one, or
the real date, and its operation for every signed-in reviewer, which the header of
every page shows."""

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Connection

from backend.dependencies import Database, SignedInReviewer
from backend.lookups import current_settings

router = APIRouter()


class BusinessDate(BaseModel):
    business_date: date
    real_date: bool


def business_date_in_force(db: Connection) -> BusinessDate:
    """The setting, or the real date when there is none."""
    setting = current_settings(db).business_date
    return BusinessDate(
        business_date=setting or date.today(), real_date=setting is None
    )


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
