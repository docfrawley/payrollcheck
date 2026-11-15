"""What a registration says on a date."""

from datetime import date

from context import registrations

PERIODS = [
    (date(2025, 10, 12), date(2026, 10, 11)),
    (date(2026, 10, 18), date(2027, 10, 17)),
]
LEVELS = [(2, date(2025, 9, 2)), (3, date(2026, 10, 19))]


def test_a_registration_before_after_and_between_its_periods():
    assert registrations.period_on(PERIODS, date(2025, 1, 6)) is None
    assert not registrations.active_on(PERIODS, date(2025, 1, 6))
    assert registrations.active_on(PERIODS, date(2026, 10, 11))
    assert not registrations.active_on(PERIODS, date(2026, 10, 14))
    assert registrations.period_on(PERIODS, date(2026, 10, 14)) == PERIODS[0]
    assert registrations.active_on(PERIODS, date(2026, 10, 18))


def test_an_apprentices_level_by_date_and_none_before_registration():
    assert registrations.level_on(LEVELS, date(2025, 1, 6)) is None
    assert registrations.level_on(LEVELS, date(2026, 10, 18)) == 2
    assert registrations.level_on(LEVELS, date(2026, 10, 19)) == 3
