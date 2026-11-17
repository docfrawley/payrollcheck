"""The check node on the direct route, with the real context layer on a local port:
the candidates it records for a labelled case are what the check tools find on the
committed records, field for field."""

from functools import partial

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select, update

from agent import harness
from agent.checks import CHECKS
from agent.checks.findings import Parameters
from agent.tests.dispatching import new_dispatch
from agent.tests.payroll_records import records
from agent.tests.queue_setup import leave_received
from agent.tests.records import case_of
from agent.tests.stubs import agent_on, stub, work
from agent.work import work_the_run
from backend.database import engine, submissions
from backend.tests.versions import add_version

FIELDS = (
    "rule",
    "worker_id",
    "line_no",
    "expected",
    "actual",
    "shortfall_cents",
    "citation",
)


@pytest.mark.parametrize("case_id", ["PC-1203", "PC-1204", "PC-1210", "PC-1216"])
def test_the_recorded_candidates_are_the_check_tools_findings(client, case_id):
    harness.work_case(case_id, None, agent_on(stub(*work())))
    recorded = [
        tuple(c[field] for field in FIELDS)
        for c in case_of(client, case_id)["candidates"]
    ]
    inputs = records("development").inputs(case_id)
    found = [
        tuple(getattr(finding, field) for field in FIELDS)
        for _, check in CHECKS
        for finding in check(inputs, Parameters(0))
    ]
    assert recorded == found
    assert found


def forty_cents_short(case_id):
    """Pay the first worker on the case's payroll, who works 40 straight hours, a
    cent an hour under the base rate, with the gross to match, so the line is 40
    cents short."""
    with engine().begin() as db:
        query = select(submissions).where(submissions.c.case_id == case_id)
        row = db.execute(query).mappings().one()
        first, *rest = row["lines"]
        assert (first["total_hours"], first["overtime_hours"]) == ("40.00", "0.00")
        short = first | {"base_rate": first["base_rate"] - 1}
        short["gross"] = first["gross"] - 40
        db.execute(
            update(submissions)
            .where(submissions.c.case_id == case_id)
            .values(lines=[short, *rest])
        )


def rate_findings(client, case_id):
    candidates = case_of(client, case_id)["candidates"]
    return [c["shortfall_cents"] for c in candidates if c["rule"] == "rate.base_short"]


@pytest.mark.parametrize(("tolerance", "found"), [(0, [40]), (50, [])])
def test_a_run_on_a_version_gives_the_check_tools_its_tolerance(
    client, tolerance, found
):
    add_version(
        "Check the payroll.",
        verdict="kept",
        parameters={"rounding_tolerance_cents": tolerance},
    )
    forty_cents_short("PC-1202")
    leave_received("PC-1202")

    def payroll_agents(version):
        return partial(agent_on, stub(*work()), InMemorySaver(), version)

    run = new_dispatch()
    assert run["version"] == 2
    work_the_run(run, payroll_agents)
    assert rate_findings(client, "PC-1202") == found
