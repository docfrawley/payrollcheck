from datetime import UTC, datetime

import pytest
from botocore.stub import ANY

from agent.tests.gateway_stand_in import GatewayStandIn
from agent.tests.local_server import serving
from backend.database import conversations, copilot_turns, engine
from data.payroll_world.expected_answers import QUESTIONS
from deploy import names, resources, smoke

MARCUS = "HND-02"
ANSWER = "Garden State Electric has $198.75 flagged this month, all on PC-1009."
EXPECTED = {"case_ids": ["PC-1009"], "flagged_cents": 19875}


@pytest.fixture(scope="module")
def gateway():
    """The agent tests' stand-in Gateway, whose Policy refuses the app's get_case."""
    stand_in = GatewayStandIn()
    with serving(stand_in.asgi()) as address:
        stand_in.url = f"{address}/mcp"
        yield stand_in


def test_a_tool_the_gateway_allows_answers_signed_as_the_operator(aws, gateway):
    gateway.reset()
    answered, text = smoke.call_by_name(
        aws, gateway.url, "payrollcheck-context___get_filing_rules", {}
    )
    assert answered
    assert "due_days" in text
    assert [call.signed for call in gateway.calls] == [True]


def test_a_tool_the_policy_refuses_is_refused_by_name(aws, gateway):
    gateway.reset()
    gateway.refused.add("payrollcheck-app___get_case")
    answered, text = smoke.call_by_name(
        aws, gateway.url, "payrollcheck-app___get_case", {"case_id": "PC-1201"}
    )
    assert not answered
    assert smoke.POLICY_DENIED in text.lower()
    assert [call.name for call in gateway.calls] == ["payrollcheck-app___get_case"]


def test_an_answer_must_name_the_expected_cases_and_total():
    assert smoke.missing_from(ANSWER, EXPECTED) == []
    assert smoke.missing_from("Nothing is flagged.", EXPECTED) == ["PC-1009", "$198.75"]


def test_the_latest_finished_turn_is_the_reviewers(database):
    with engine().begin() as db:
        db.execute(
            conversations.insert().values(
                conversation_id="conversation-1",
                reviewer_id=MARCUS,
                title="Garden State Electric",
                turns=2,
                created_at="2026-11-23T09:00:00",
            )
        )
        for number, status, answer in ((1, "done", "First"), (2, "failed", None)):
            db.execute(
                copilot_turns.insert().values(
                    turn_id=f"turn-{number}",
                    conversation_id="conversation-1",
                    number=number,
                    message="How much?",
                    status=status,
                    started_at=f"2026-11-23T09:0{number}:00",
                    answer=answer,
                )
            )
    turn = smoke.latest_turn("marcus.oyelaran@payrollcheck.example")
    assert (turn["turn_id"], turn["reviewer_id"]) == ("turn-1", MARCUS)
    with pytest.raises(RuntimeError, match="no answer"):
        smoke.latest_turn("priya.raman@payrollcheck.example")


@pytest.fixture
def answered(monkeypatch):
    def with_answer(text):
        monkeypatch.setattr(
            smoke,
            "latest_turn",
            lambda _: {
                "message": QUESTIONS[1],
                "answer": text,
                "reviewer_id": MARCUS,
                "conversation_id": "conversation-1",
            },
        )
        monkeypatch.setattr(
            resources, "find_memory", lambda _: {"id": "copilot-memory-1"}
        )

    return with_answer


def events(count):
    return {
        "events": [
            {
                "memoryId": "copilot-memory-1",
                "actorId": MARCUS,
                "sessionId": "conversation-1",
                "eventId": f"event-{n}",
                "eventTimestamp": "2026-11-23T09:01:00Z",
                "payload": [],
            }
            for n in range(count)
        ]
    }


def test_the_copilots_answer_and_memory_pass(aws, stub, answered, capsys):
    answered(ANSWER)
    stub("bedrock-agentcore").add_response(
        "list_events",
        events(2),
        {
            "memoryId": "copilot-memory-1",
            "actorId": MARCUS,
            "sessionId": "conversation-1",
        },
    )
    smoke.copilot(aws)
    assert "The answer names PC-1009 and the total" in capsys.readouterr().out


def test_an_answer_missing_the_total_fails(aws, stub, answered):
    answered("PC-1009 has some underpayment.")
    stub("bedrock-agentcore").add_response("list_events", events(2))
    with pytest.raises(RuntimeError, match=r"\$198.75"):
        smoke.copilot(aws)


def test_an_answer_to_another_question_fails(aws, monkeypatch, answered):
    answered(ANSWER)
    monkeypatch.setattr(
        smoke, "latest_turn", lambda _: {"message": QUESTIONS[0], "answer": ANSWER}
    )
    with pytest.raises(RuntimeError, match="latest question"):
        smoke.copilot(aws)


def test_a_conversation_the_memory_never_got_fails(aws, stub, answered):
    answered(ANSWER)
    stub("bedrock-agentcore").add_response("list_events", events(0))
    with pytest.raises(RuntimeError, match="Memory has none"):
        smoke.copilot(aws)


def test_a_functions_invocations_are_its_start_lines(aws, stub):
    start = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)
    end = datetime(2026, 11, 23, 9, 1, tzinfo=UTC)
    stub("logs").add_response(
        "filter_log_events",
        {
            "events": [
                {"message": "START RequestId: 1"},
                {"message": "START RequestId: 2"},
            ]
        },
        {
            "logGroupName": names.log_group(names.APP_FUNCTION),
            "startTime": int(start.timestamp() * 1000),
            "endTime": int(end.timestamp() * 1000),
            "filterPattern": '"START RequestId"',
        },
    )
    assert smoke.invocations(aws, names.APP_FUNCTION, start, end) == 2


@pytest.fixture
def probed(monkeypatch, no_pauses):
    """The probe against outcomes and log counts a test gives."""

    def with_outcomes(allowed, refused, ran):
        monkeypatch.setattr(
            resources, "find_gateway", lambda _: {"gatewayUrl": "https://gw/mcp"}
        )
        outcomes = iter([allowed, refused])
        monkeypatch.setattr(smoke, "call_by_name", lambda *_: next(outcomes))
        monkeypatch.setattr(
            smoke, "invocations", lambda _, function, *__: ran[function]
        )

    return with_outcomes


def test_the_policy_probe_passes_when_the_app_is_never_reached(
    aws, probed, no_pauses, capsys
):
    probed(
        (True, "{}"),
        (
            False,
            "Tool Execution Denied: Tool call not allowed due to policy enforcement",
        ),
        {names.CONTEXT_FUNCTION: 1, names.APP_FUNCTION: 0},
    )
    smoke.probe(aws)
    shown = capsys.readouterr().out
    assert "payrollcheck-app___get_case: refused" in shown
    assert "never reached the app" in shown
    assert no_pauses == [60]


@pytest.mark.parametrize(
    ("outcome", "why"),
    [
        (
            (
                (True, "{}"),
                (True, "{}"),
                {"payrollcheck-context": 1, "payrollcheck-app": 1},
            ),
            "allowlist",
        ),
        (
            (
                (False, "no"),
                (False, "no"),
                {"payrollcheck-context": 0, "payrollcheck-app": 0},
            ),
            "allowlist",
        ),
        (
            (
                (True, "{}"),
                (False, "Unknown tool payrollcheck-app___get_case"),
                {"payrollcheck-context": 1, "payrollcheck-app": 0},
            ),
            "allowlist",
        ),
        (
            (
                (True, "{}"),
                (False, smoke.POLICY_DENIED),
                {"payrollcheck-context": 1, "payrollcheck-app": 1},
            ),
            "logs",
        ),
    ],
)
def test_the_policy_probe_fails_on_anything_else(aws, probed, outcome, why):
    probed(*outcome)
    with pytest.raises(RuntimeError, match=why):
        smoke.probe(aws)


def test_the_engines_decisions_are_counted(aws, stub, monkeypatch, capsys):
    monkeypatch.setattr(
        resources, "find_policy_engine", lambda _: {"policyEngineId": "engine-1"}
    )
    cloudwatch = stub("cloudwatch")
    for metric, total in (("AllowDecisions", 40.0), ("DenyDecisions", 1.0)):
        cloudwatch.add_response(
            "get_metric_statistics",
            {"Label": "x", "Datapoints": [{"Sum": total}]},
            {
                "Namespace": "AWS/Bedrock-AgentCore",
                "MetricName": metric,
                "Dimensions": [
                    {"Name": "OperationName", "Value": "AuthorizeAction"},
                    {"Name": "Mode", "Value": "ENFORCE"},
                    {"Name": "PolicyEngine", "Value": "engine-1"},
                ],
                "StartTime": ANY,
                "EndTime": ANY,
                "Period": 3600,
                "Statistics": ["Sum"],
            },
        )
    smoke.decisions(aws)
    assert capsys.readouterr().out == "AllowDecisions: 40\nDenyDecisions: 1\n"


def test_the_smoke_check_needs_what_it_checks(aws, monkeypatch):
    monkeypatch.setattr(resources, "find_gateway", lambda _: None)
    monkeypatch.setattr(resources, "find_policy_engine", lambda _: None)
    monkeypatch.setattr(resources, "find_memory", lambda _: None)
    monkeypatch.setattr(
        smoke,
        "latest_turn",
        lambda _: {"message": QUESTIONS[1], "answer": ""},
    )
    for part, step in (
        ("policy", "step 4"),
        ("decisions", "step 5"),
        ("copilot", "step 6"),
    ):
        with pytest.raises(RuntimeError, match=step):
            smoke.run(aws, part)
