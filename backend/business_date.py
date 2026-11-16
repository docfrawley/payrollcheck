"""The business date in force: the app's "today", the setting when it has one, or
the real date."""

from datetime import date

from sqlalchemy import Connection

from backend.lookups import current_settings


def business_date(db: Connection) -> date:
    setting = current_settings(db).business_date
    return date.fromisoformat(setting) if setting else date.today()
