"""The business date: the app's today, which every signed-in reviewer reads and
only the compliance manager changes or resets to the real date."""

from datetime import UTC, datetime

from backend import business_date as business_dates
from backend.business_date import NEW_JERSEY
from backend.tests.dashboard_reads import settings_page
from backend.tests.settings_requests import change_settings
from backend.tests.sign_in import DANA, MARCUS, PRIYA, signed_in

BUSINESS_DATE = "/api/business-date"


def business_date(client, email=DANA):
    return client.get(BUSINESS_DATE, headers=signed_in(email))


def test_every_reviewer_reads_the_seeded_business_date(dashboard):
    for email in (MARCUS, PRIYA, DANA):
        answer = business_date(dashboard, email)
        assert answer.status_code == 200
        assert answer.json() == {"business_date": "2026-11-23", "real_date": False}
    assert dashboard.get(BUSINESS_DATE).status_code == 401


def test_the_compliance_manager_changes_it_and_the_history_says_who(dashboard):
    assert change_settings(dashboard, business_date="2026-11-30").status_code == 200
    assert business_date(dashboard, MARCUS).json()["business_date"] == "2026-11-30"
    newest = settings_page(dashboard)["changes"][0]
    assert (newest["business_date"], newest["changed_by"]) == (
        "2026-11-30",
        "Dana Whitfield",
    )
    assert newest["changed_at"]


def test_reset_to_the_real_date(dashboard):
    assert change_settings(dashboard, business_date=None).status_code == 200
    assert business_date(dashboard).json() == {
        "business_date": datetime.now(NEW_JERSEY).date().isoformat(),
        "real_date": True,
    }
    assert settings_page(dashboard)["current"]["business_date"] is None


def test_a_reviewer_is_refused_the_change(dashboard):
    refused = change_settings(dashboard, MARCUS, business_date="2026-11-30")
    assert refused.status_code == 403
    assert refused.json()["detail"] == (
        "Only the compliance manager can change the settings. Marcus Oyelaran can't."
    )
    assert business_date(dashboard).json()["business_date"] == "2026-11-23"


def test_a_business_date_that_isnt_a_date_is_refused(dashboard):
    for bad in ("2026-13-01", "next monday"):
        assert change_settings(dashboard, business_date=bad).status_code == 422


def test_the_real_date_is_new_jerseys_where_utc_is_already_tomorrow(monkeypatch):
    # 11:30 pm in New Jersey on Nov 23 is 4:30 am on Nov 24 in UTC.
    late = datetime(2026, 11, 24, 4, 30, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return late.astimezone(tz)

    monkeypatch.setattr(business_dates, "datetime", Clock)
    assert business_dates.real_date().isoformat() == "2026-11-23"
