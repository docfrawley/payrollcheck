"""Requests the backend's tests send to change the settings."""

from backend.seeding import load
from backend.tests.sign_in import DANA, signed_in

# The settings as seeded, from data/improvement.json, with the business date.
STARTING = {**load("improvement.json"), "business_date": "2026-11-23"}


def change_settings(client, email=DANA, **values):
    """Change some settings from where they started, as the reviewer with this
    email."""
    return client.put("/api/settings", json=STARTING | values, headers=signed_in(email))
