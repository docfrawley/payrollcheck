"""The check tools against both labelled sets: each label of their rules found on
its case with its worker, line and shortfall to the cent, nothing else on any
payroll, correction or decoy but the two decoys that need the payroll agent's
judgment."""

import pytest

from agent.check_inputs import read_inputs
from agent.checks import CHECKS
from agent.checks.findings import CHANGED, PROJECT_MISMATCH, Finding, Parameters
from agent.checks.inputs import CheckInputs
from agent.tests.payroll_records import labels, lookup, records

EXACT = Parameters(0)
# The decoys a check finds for the payroll agent to judge: a classification change
# with a note, and a contractor's name that isn't the one on our records.
JUDGED = {"classification_note": CHANGED, "name_variant": PROJECT_MISMATCH}
# A hidden instruction in the contractor's name makes it differ from our records.
# The screening flags the case before any check runs.
HIDDEN = {"contractor_name": PROJECT_MISMATCH}


def findings(inputs: CheckInputs) -> list[Finding]:
    return [found for _, check in CHECKS for found in check(inputs, EXACT)]


def found_on(inputs: CheckInputs) -> list[tuple]:
    return sorted(
        (f.rule, f.worker_id, f.line_no, f.shortfall_cents) for f in findings(inputs)
    )


def expected_on(name: str, case_id: str) -> list[tuple]:
    labelled = [
        (x["rule"], x["worker_id"], x["line_no"], x["expected_shortfall_cents"])
        for x in labels(name)
        if x["case_id"] == case_id
    ]
    return sorted(labelled)


def judged(name: str, case_id: str) -> list[tuple[str, str | None]]:
    found = records(name)
    decoys = [
        (JUDGED[d["kind"]], d.get("worker"))
        for d in found.decoys
        if d["case"] == case_id and d["kind"] in JUDGED
    ]
    hidden = [
        (HIDDEN[h["column"]], None)
        for h in found.hidden_instructions
        if h["case"] == case_id and h["column"] in HIDDEN
    ]
    return decoys + hidden


@pytest.mark.parametrize("name", ["development", "held_out"])
def test_each_first_submission_has_its_labels_and_nothing_else(name):
    found_records = records(name)
    for case_id in found_records.cases:
        found = found_on(found_records.inputs(case_id))
        decoys = judged(name, case_id)
        plain = [f for f in found if (f[0], f[1]) not in decoys]
        assert plain == expected_on(name, case_id), case_id
        assert sorted((f[0], f[1]) for f in found if f not in plain) == sorted(
            decoys
        ), case_id


@pytest.mark.parametrize("name", ["development", "held_out"])
def test_every_later_submission_has_nothing(name):
    found_records = records(name)
    for case_id, case in found_records.cases.items():
        for entry in case["submissions"][1:]:
            inputs = found_records.inputs(case_id, entry["number"])
            assert found_on(inputs) == [], (case_id, entry["number"])


DEVELOPMENT = "development"


def first_line(edit):
    """An edit of the latest submission's first line."""

    def edited(case):
        edit(case["submissions"][-1]["lines"][0])

    return edited


def certified(**changes):
    def edited(case):
        case["submissions"][-1]["certification"].update(changes)

    return edited


def run(check_name: str, inputs: CheckInputs, tolerance: int = 0) -> list[Finding]:
    [check] = [check for name, check in CHECKS if name == check_name]
    return check(inputs, Parameters(tolerance))


def test_the_check_tools_in_order():
    assert [name for name, _ in CHECKS] == [
        "check_form",
        "check_contractor_registration",
        "check_rates",
        "check_overtime",
        "check_arithmetic",
        "check_apprentices",
        "check_timeliness",
        "check_classification",
    ]


def test_the_form_check_finds_blank_unsigned_and_mismatched_fields():
    inputs = records(DEVELOPMENT).inputs(
        "PC-0101",
        edit=certified(fein="", signed_on=None, project_id="PRJ-02"),
    )
    blank, unsigned, mismatch = run("check_form", inputs)
    assert (blank.rule, blank.actual) == ("form.missing_field", "Blank: fein")
    assert blank.citation == "MW-562 payroll certification"
    assert (unsigned.rule, unsigned.actual) == ("form.unsigned", "Blank: signed on")
    assert mismatch.rule == "form.project_mismatch"
    assert (mismatch.expected, mismatch.actual) == (
        "project_id: PRJ-01",
        "project_id: PRJ-02",
    )


def test_the_registration_check_cites_the_registry_record_and_the_rule():
    [found] = run(
        "check_contractor_registration", records(DEVELOPMENT).inputs("PC-0706")
    )
    assert found.rule == "registration.inactive"
    assert found.actual.startswith("Not active on 2026-10-12")
    assert found.citation == (
        "Contractor registry 941034, Delaware Valley Masonry LLC: period 2025-10-12 "
        "to 2026-10-11; Filing rules, Registered on every work date: "
        "N.J.S.A. 34:11-56.51"
    )


def test_an_unknown_registration_is_cited_as_the_registry_refused_it():
    found = records(DEVELOPMENT)
    case = found.case("PC-0101", 1)
    subcontractors = [
        s | {"registration_no": "000000"}
        for s in found.project_subcontractors("PRJ-01")
    ]
    inputs = read_inputs(
        case, found.project("PRJ-01"), subcontractors, found.history("PC-0101"), lookup
    )
    [inactive] = run("check_contractor_registration", inputs)
    assert "Contractor registry: No registration 000000 in the registry" in (
        inactive.citation
    )


def test_a_base_rate_a_cent_short_is_owed_on_every_hour_and_cites_its_row():
    inputs = records(DEVELOPMENT).inputs(
        "PC-0101", edit=first_line(lambda line: line.update(base_rate=5884))
    )
    [found] = run("check_rates", inputs)
    assert (found.rule, found.worker_id, found.line_no) == (
        "rate.base_short",
        "W-001",
        1,
    )
    assert (found.expected, found.actual, found.shortfall_cents) == (
        "$58.85/h",
        "$58.84/h",
        32,
    )
    assert found.citation == (
        "Rate determination MID-2025-11, Electrician Journeyman, row effective "
        "2025-11-03"
    )
    assert run("check_rates", inputs, tolerance=31)
    assert run("check_rates", inputs, tolerance=32) == []


def test_the_fringe_counts_cash_in_lieu():
    paid_in_cash = records(DEVELOPMENT).inputs(
        "PC-0101",
        edit=first_line(lambda line: line.update(fringe_rate=0, fringe_cash=3465)),
    )
    assert run("check_rates", paid_in_cash) == []
    short = records(DEVELOPMENT).inputs(
        "PC-0101",
        edit=first_line(lambda line: line.update(fringe_rate=0, fringe_cash=3464)),
    )
    [found] = run("check_rates", short)
    assert (found.rule, found.shortfall_cents) == ("rate.fringe_short", 32)


def test_the_pre_listed_increase_applies_from_its_date():
    def thursday_too(line):
        line["hours"][3] = "8.00"
        line["total_hours"] = "32.00"

    inputs = records(DEVELOPMENT).inputs("PC-0501", edit=first_line(thursday_too))
    [found, _] = run("check_rates", inputs)
    assert found.expected == "$58.85/h then $61.10/h"
    assert found.shortfall_cents == 8 * (6110 - 5885)
    assert found.citation == (
        "Rate determination MID-2025-11, Electrician Journeyman, rows effective "
        "2025-11-03 and 2026-10-01"
    )


def test_a_later_determination_is_ignored():
    inputs = records(DEVELOPMENT).inputs(
        "PC-0702", edit=first_line(lambda line: line.update(base_rate=1))
    )
    [found] = run("check_rates", inputs)
    assert "MID-2025-11" in found.citation
    assert "MID-2026-07" not in found.citation


def test_overtime_unpaid_on_a_long_day_is_found_to_the_tolerance():
    inputs = records(DEVELOPMENT).inputs("PC-0803")
    assert run("check_overtime", inputs) == []
    [line_no] = [
        found.line_no for found in inputs.lines if found.line.worker_id == "W-007"
    ]

    def unpaid(case):
        line = case["submissions"][-1]["lines"][line_no - 1]
        line["overtime_hours"] = "0.00"

    [found] = run("check_overtime", records(DEVELOPMENT).inputs("PC-0803", edit=unpaid))
    assert found.rule == "overtime.underpaid"
    assert (found.expected, found.actual) == (
        "2.00 h at a premium",
        "0.00 h paid as overtime",
    )
    assert found.citation.endswith(
        "its overtime rules, and the state's 40-hour weekly floor"
    )
    tolerated = run(
        "check_overtime",
        records(DEVELOPMENT).inputs("PC-0803", edit=unpaid),
        tolerance=found.shortfall_cents or 0,
    )
    assert tolerated == []


def test_a_gross_a_cent_out_is_found_at_no_tolerance_and_not_at_a_cent():
    def short(line):
        line["gross"] -= 1

    inputs = records(DEVELOPMENT).inputs("PC-0101", edit=first_line(short))
    [found] = run("check_arithmetic", inputs)
    assert (found.rule, found.shortfall_cents) == ("arithmetic.gross", 1)
    assert run("check_arithmetic", inputs, tolerance=1) == []

    def over(line):
        line["gross"] += 1

    [paid_over] = run(
        "check_arithmetic",
        records(DEVELOPMENT).inputs("PC-0101", edit=first_line(over)),
    )
    assert paid_over.shortfall_cents is None


def test_hours_that_dont_add_up_are_found_whatever_the_tolerance():
    inputs = records(DEVELOPMENT).inputs(
        "PC-0101", edit=first_line(lambda line: line.update(total_hours="33.00"))
    )
    found = run("check_arithmetic", inputs, tolerance=1000)
    assert [f.rule for f in found] == ["arithmetic.hours_total"]
    assert found[0].citation == (
        "MW-562 payroll register: the daily hours add up to the total"
    )


def test_an_unregistered_apprentice_is_owed_the_journeyman_rate():
    [found] = run("check_apprentices", records(DEVELOPMENT).inputs("PC-1210"))
    assert (found.rule, found.worker_id) == ("apprentice.unregistered", "W-064")
    assert found.citation.startswith(
        "Apprentice registrations: W-064 not a registered apprentice on 2026-11-16"
    )
    assert "Rate determination MON-2026-01, Carpenter Apprentice" in found.citation
    tolerated = run(
        "check_apprentices",
        records(DEVELOPMENT).inputs("PC-1210"),
        tolerance=found.shortfall_cents or 0,
    )
    assert [f.rule for f in tolerated] == []


def test_the_apprentice_ratio_cites_its_filing_rule():
    found = run("check_apprentices", records(DEVELOPMENT).inputs("PC-1201"))
    [ratio] = [f for f in found if f.rule == "apprentice.ratio"]
    assert ratio.expected == "Electrician: 2 apprentices for every 3 journeymen"
    assert ratio.citation == (
        "Filing rules, Apprentices within the craft's ratio: N.J.A.C. 12:60-6.3"
    )


def test_late_and_out_of_sequence_payrolls_cite_their_filing_rules():
    late = records(DEVELOPMENT).inputs(
        "PC-0101", edit=certified(wage_payment_date="2026-08-01")
    )
    [found] = run("check_timeliness", late)
    assert found.rule == "timeliness.late"
    assert found.citation == (
        "Filing rules, Due within 10 days of paying the wages: N.J.S.A. "
        "34:11-56.29(b)(2); N.J.A.C. 12:60-5.1(c)(1)(i)"
    )
    [gap] = run(
        "check_timeliness",
        records(DEVELOPMENT).inputs("PC-0101", edit=certified(payroll_no=2)),
    )
    assert (gap.rule, gap.expected) == (
        "sequence.gap",
        "Payroll No. 1, from 1 in the week ending 2026-09-06",
    )
    assert (
        gap.citation
        == 'Filing rules, Payroll numbers in sequence: MW-562 "Payroll No."'
    )


def as_laborer(base_rate: int):
    return first_line(
        lambda line: line.update(
            classification="Laborer Journeyman", base_rate=base_rate
        )
    )


def test_a_lower_paid_craft_owes_the_established_crafts_rates():
    inputs = records(DEVELOPMENT).inputs("PC-0101", edit=as_laborer(5785))
    [found] = run("check_classification", inputs)
    assert (found.rule, found.actual) == (
        "classification.mismatch",
        "Laborer Journeyman",
    )
    assert found.expected == "Electrician Journeyman, $58.85/h and $34.65/h fringe"
    assert found.shortfall_cents == 32 * 100
    assert found.citation == (
        "Our worker records, the established craft; Rate determination MID-2025-11, "
        "Electrician Journeyman, row effective 2025-11-03"
    )
    assert run("check_rates", inputs) == []
    assert run("check_classification", inputs, tolerance=3200) == []


def test_a_lower_paid_craft_paid_the_established_rates_owes_nothing():
    inputs = records(DEVELOPMENT).inputs("PC-0101", edit=as_laborer(5885))
    assert inputs.lines[0].misclassified
    assert run("check_classification", inputs) == []


def test_a_classification_the_rates_dont_have_is_a_mismatch_with_no_money():
    inputs = records(DEVELOPMENT).inputs(
        "PC-0101",
        edit=first_line(lambda line: line.update(classification="Welder Journeyman")),
    )
    assert inputs.lines[0].claimed is None
    [found] = run("check_classification", inputs)
    assert (found.rule, found.shortfall_cents) == ("classification.mismatch", None)
    assert found.expected == "Electrician Journeyman"
    assert run("check_rates", inputs) == run("check_overtime", inputs) == []


def test_a_change_from_last_week_is_found_with_its_note_for_the_agent_to_judge():
    [found] = run("check_classification", records(DEVELOPMENT).inputs("PC-1202"))
    assert found.rule == "classification.changed"
    assert found.expected == "Carpenter Journeyman, as last week"
    assert "Acting foreman this week" in found.actual
    assert found.citation == "Last week's payroll of record"


def test_a_no_work_week_payroll_has_no_lines_and_nothing_found():
    inputs = records(DEVELOPMENT).inputs("PC-0415")
    assert inputs.certification.no_work_week
    assert inputs.lines == ()
    assert findings(inputs) == []
