"""The context layer's payroll files and their lookups, against the files in
context/."""

from datetime import date

import pytest

from context import payroll_files, wage_rules
from context.sources import SYNTHETIC, Refused


@pytest.mark.parametrize("file", payroll_files.FILES)
def test_every_payroll_file_names_its_source_and_says_it_is_synthetic(file):
    read = payroll_files.FILES[file]
    assert read["source"]["file"] == file
    assert set(read["source"]) == {"file", "system", "owner", "reviewed"}
    assert read["notice"] == SYNTHETIC


LINCOLN_AWARD = date(2026, 4, 15)
DELAWARE_VALLEY = "941034"
RATE_SOURCE = payroll_files.FILES[payroll_files.RATE_DETERMINATIONS]["source"]


def wage_rate(work_date: date, award: date = LINCOLN_AWARD, craft="electrician"):
    return payroll_files.get_wage_rate(
        craft, "journeyman", "Middlesex", award, work_date
    )


def test_the_wage_rate_before_and_after_the_pre_listed_increase():
    before = wage_rate(date(2026, 9, 30))
    after = wage_rate(date(2026, 10, 1))
    assert before["determination"] == {
        "id": "MID-2025-11",
        "area": "Middlesex",
        "issued": "2025-11-03",
    }
    assert before["row"] == {
        "effective": "2025-11-03",
        "wage_cents": 5885,
        "fringe_cents": 3465,
        "total_cents": 9350,
    }
    assert after["row"]["effective"] == "2026-10-01"
    assert after["row"]["total_cents"] == 9650
    assert after["sources"] == [RATE_SOURCE]
    craft = after["craft_rules"]
    assert craft["craft"] == "electrician"
    assert craft["name"] == "Electrician"
    assert craft["statewide"] is False
    assert craft["apprentice_ratio"] == {"apprentices": 2, "journeymen": 3}
    assert craft["overtime_rules"][0]["when"] == "daily_over"
    assert len(craft["apprentice_schedule"]) == 5
    assert wage_rules.craft_rules(craft) == payroll_files.RATES.crafts["electrician"]


def test_a_later_determination_isnt_returned_for_an_earlier_award():
    rate = wage_rate(date(2026, 11, 23))
    assert rate["determination"]["id"] == "MID-2025-11"
    later = wage_rate(date(2026, 11, 23), award=date(2026, 8, 3))
    assert later["determination"]["id"] == "MID-2026-07"


def test_a_statewide_crafts_rate_is_the_statewide_determinations():
    rate = payroll_files.get_wage_rate(
        "laborer", "foreman", "Ocean", date(2026, 6, 10), date(2026, 11, 2)
    )
    assert rate["determination"]["area"] == "STATEWIDE"
    laborer_wage, foreman_premium = 4495, 250
    assert rate["row"]["wage_cents"] == laborer_wage + foreman_premium


@pytest.mark.parametrize(
    ("craft", "classification", "county", "award", "reason"),
    [
        ("welder", "journeyman", "Middlesex", LINCOLN_AWARD, "No craft welder"),
        (
            "electrician",
            "helper",
            "Middlesex",
            LINCOLN_AWARD,
            "No classification helper",
        ),
        (
            "electrician",
            "apprentice",
            "Middlesex",
            LINCOLN_AWARD,
            "percentage of the journeyman",
        ),
        ("electrician", "journeyman", "Atlantis", LINCOLN_AWARD, "No county Atlantis"),
        (
            "electrician",
            "journeyman",
            "Middlesex",
            date(2024, 1, 2),
            "No Middlesex determination",
        ),
    ],
)
def test_an_unknown_rate_is_refused_with_its_reason(
    craft, classification, county, award, reason
):
    with pytest.raises(Refused, match=reason):
        payroll_files.get_wage_rate(
            craft, classification, county, award, date(2026, 11, 2)
        )


def test_a_work_date_before_the_determinations_rows_is_refused():
    with pytest.raises(Refused, match="no electrician rate on or before 2024-06-03"):
        wage_rate(date(2024, 6, 3), award=date(2025, 6, 2))


def test_a_registration_before_its_expiry_while_it_lapsed_and_after_its_renewal():
    before = payroll_files.check_registration(DELAWARE_VALLEY, date(2026, 10, 9))
    lapsed = payroll_files.check_registration(DELAWARE_VALLEY, date(2026, 10, 14))
    renewed = payroll_files.check_registration(DELAWARE_VALLEY, date(2026, 10, 19))
    assert before["holder"] == "Delaware Valley Masonry LLC"
    assert (before["status"], before["expiry"]) == ("active", "2026-10-11")
    assert (lapsed["status"], lapsed["expiry"]) == ("not active", "2026-10-11")
    assert (renewed["status"], renewed["effective"]) == ("active", "2026-10-18")
    assert renewed["sources"][0]["file"] == "contractor_registry.yaml"
    before = payroll_files.check_registration(DELAWARE_VALLEY, date(2025, 1, 6))
    assert (before["status"], before["effective"]) == ("not active", None)
    with pytest.raises(Refused, match="No registration 000000"):
        payroll_files.check_registration("000000", date(2026, 10, 19))


def test_a_registered_apprentice_at_their_level_and_the_unregistered_one():
    early = payroll_files.check_apprentice("W-059", date(2026, 10, 16))
    later = payroll_files.check_apprentice("W-059", date(2026, 10, 19))
    assert early["registered"]
    assert (early["level"], early["wage_percent"]) == (2, 49)
    assert (later["level"], later["fringe_percent"]) == (3, 58)
    assert early["sponsor"] == "Central Jersey Electrical JATC"
    assert early["sources"][0]["file"] == "apprentice_registrations.yaml"
    not_yet = payroll_files.check_apprentice("W-059", date(2025, 1, 6))
    assert not_yet["registered"] is False
    assert not_yet["registered_on"] == "2025-09-02"
    assert "level" not in not_yet
    unregistered = payroll_files.check_apprentice("W-064", date(2026, 11, 20))
    assert unregistered["registered"] is False
    assert unregistered["sources"][0]["file"] == "apprentice_registrations.yaml"
    held_out = payroll_files.check_apprentice("W-536", date(2026, 11, 2))
    assert held_out["registered"]
    assert held_out["level"] == 2


def test_the_filing_rules_and_a_payroll_term_whatever_its_case():
    rules = payroll_files.get_filing_rules()
    assert rules["due_days"] == 10
    assert {rule["rule"] for rule in rules["rules"]} >= {
        "due_date",
        "sequence",
        "correction",
    }
    assert rules["sources"][0]["file"] == "filing_rules.yaml"
    term = payroll_files.lookup_payroll_term("  no work WEEK ")
    assert term["term"] == "No Work Week"
    assert term["sources"][0]["file"] == "payroll_glossary.yaml"
    unknown = payroll_files.lookup_payroll_term("zeppelin")
    assert unknown["answer"].startswith(
        'The payroll glossary doesn\'t define "zeppelin"'
    )
    assert "MW-562" in unknown["terms"]


def test_a_statewide_crafts_rate_in_a_county_with_no_determinations():
    rate = payroll_files.get_wage_rate(
        "laborer", "journeyman", "Essex", date(2026, 6, 10), date(2026, 11, 2)
    )
    assert rate["determination"]["id"] == "STW-2026-01"
