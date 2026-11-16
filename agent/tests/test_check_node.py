"""The check node on the direct route, with the real context layer on a local port:
the candidates it records for a labelled case are what the check tools find on the
committed records, field for field."""

import pytest

from agent import harness
from agent.checks import CHECKS
from agent.checks.findings import Parameters
from agent.tests.payroll_records import records
from agent.tests.records import case_of
from agent.tests.stubs import agent_on, stub, work

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
