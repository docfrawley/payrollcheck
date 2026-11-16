"""The platform's settings, kept as a history of changes."""

import pytest

from backend.database import engine, models_allowed, settings
from backend.seeding import load, seed
from backend.tests.dashboard_reads import settings_page
from backend.tests.rows import count
from backend.tests.settings_requests import STARTING, change_settings
from backend.tests.sign_in import MARCUS


def test_seeding_makes_the_first_settings_and_the_models_allowed(client):
    page = settings_page(client)
    current = page["current"]
    assert {key: current[key] for key in STARTING} == STARTING
    assert current["objectives"] == {
        "catch_rate": 0.92,
        "false_per_100": 2.5,
        "shortfall_accuracy": 1.0,
        "notice_score": 0.8,
    }
    measures = ["catch_rate", "false_per_100", "shortfall_accuracy", "notice_score"]
    noise, tolerance = current["noise"], current["tolerance"]
    assert [noise[m] for m in measures] == [0.05, 1.0, 0.0, 0.1]
    assert [tolerance[m] for m in measures] == [0.05, 1.0, 0.0, 0.1]
    assert (noise["cost_per_case"], tolerance["cost_per_case"]) == (0.15, 1.0)
    assert (noise["seconds_per_case"], tolerance["seconds_per_case"]) == (0.15, 0.25)
    assert current["spending_limit"] == 5.0
    assert (current["number"], current["changed_by"]) == (1, None)
    assert [c["number"] for c in page["changes"]] == [1]
    assert page["models_allowed"] == load("models.json")
    assert count(models_allowed) == 3


def test_a_student_on_a_free_model_has_only_that_model(client, monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    seed(engine())
    assert settings_page(client)["models_allowed"] == [
        {
            "model": "openrouter/free",
            "reasoning_efforts": ["default"],
            "input_price": 0.0,
            "output_price": 0.0,
        }
    ]


def test_a_compliance_manager_changes_the_settings(client):
    response = change_settings(client, spending_limit=0.75)
    assert response.status_code == 200
    page = settings_page(client)
    current = page["current"]
    assert (current["number"], current["spending_limit"]) == (2, 0.75)
    assert current["changed_by"] == "Dana Whitfield"
    assert current["changed_at"]
    assert [c["number"] for c in page["changes"]] == [2, 1]
    assert page["changes"][1]["spending_limit"] == 5.0


def test_a_reviewer_who_isnt_the_compliance_manager_cant_change_them(client):
    response = change_settings(client, MARCUS, spending_limit=0.75)
    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Only the compliance manager can change the settings. Marcus Oyelaran can't."
    )
    assert count(settings) == 1
    unsigned = client.put("/api/settings", json=STARTING)
    assert unsigned.status_code == 401


@pytest.mark.parametrize(
    "values",
    [
        {"objectives": STARTING["objectives"] | {"catch_rate": 1.5}},
        {"objectives": STARTING["objectives"] | {"notice_score": 1.2}},
        {"objectives": {"catch_rate": 0.9}},
        {"tolerance": STARTING["tolerance"] | {"false_per_100": -1}},
        {"noise": STARTING["noise"] | {"catch_rate": -0.1}},
        {"spending_limit": 0},
        {"agents": 26},
    ],
)
def test_settings_out_of_range_are_refused(client, values):
    assert change_settings(client, **values).status_code == 422
    assert count(settings) == 1


def test_a_change_to_a_measure_is_recorded(client):
    objectives = STARTING["objectives"] | {"false_per_100": 3.0}
    noise = STARTING["noise"] | {"notice_score": 0.2}
    assert (
        change_settings(client, objectives=objectives, noise=noise).status_code == 200
    )
    current = settings_page(client)["current"]
    assert (current["objectives"], current["noise"]) == (objectives, noise)


def test_the_business_date_is_carried_through_a_change(client):
    change_settings(client, spending_limit=0.75)
    assert settings_page(client)["current"]["business_date"] == "2026-11-23"
    change_settings(client, business_date=None)
    assert settings_page(client)["current"]["business_date"] is None
