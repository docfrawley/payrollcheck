"""The Copilot's loop: its lookups and actions, each a card, refusals passed on to
the model, one tool at a time, a turn's model calls limited, a failed turn and a
message after it, and the reviewer's sign-in on every request it sends."""

import itertools
import json

import pytest
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from agent.connection import Refused
from agent.copilot import app_api, turns
from agent.copilot.tools import COPILOT_TOOLS, KINDS
from agent.gateway import GATEWAY_URL
from agent.tests.copilot_driver import Copilot
from agent.tests.stubs import USAGE, call, stub
from backend.tests.case_requests import awaiting_review, finding
from backend.tests.copilot_requests import latest, started
from backend.tests.run_requests import another_running_dispatch, fail_run, run_path
from backend.tests.sign_in import DANA, MARCUS, OTHER_KEY, token

WHY = "Why does PC-1201 need me?"
ANSWER = "PC-1201 has one open exception: a base rate $0.32 short."
TERM = "No Work Week"
RATE = {
    "craft": "electrician",
    "classification": "journeyman",
    "county": "Middlesex",
    "award_date": "2026-04-15",
    "work_date": "2026-11-23",
}


def cards_of(turn):
    return [(card["tool"], card["input"], card["status"]) for card in turn["steps"]]


def test_the_loop(client, copilot: Copilot):
    awaiting_review(client, "PC-1201", finding())
    copilot.model = stub(
        call("get_case", case_id="PC-1201"),
        call("list_steps", case_id="PC-1201"),
        call("lookup_payroll_term", term=TERM),
        ANSWER,
    )
    conversation = copilot.ask(WHY)
    [turn] = conversation["turns"]
    assert cards_of(turn) == [
        ("get_case", "PC-1201", "done"),
        ("list_steps", "PC-1201", "done"),
        ("lookup_payroll_term", TERM, "done"),
    ]
    assert all(card["finished_at"] and card["seconds"] >= 0 for card in turn["steps"])
    [source] = turn["steps"][2]["sources"]
    assert set(source) == {"file", "system", "owner", "reviewed"}
    assert source["file"] == "payroll_glossary.yaml"
    case = json.loads(copilot.model.prompts[1][-1].text)
    assert (case["case_id"], case["status"], case["open_exceptions"]) == (
        "PC-1201",
        "awaiting_review",
        1,
    )
    assert (turn["status"], turn["answer"], turn["model_calls"]) == ("done", ANSWER, 4)
    assert turn["cost"] == pytest.approx(4 * USAGE["cost"])


def test_the_model_knows_who_it_works_for(copilot: Copilot):
    copilot.model = stub("Hello, Dana.")
    copilot.ask("Hello")
    [system, *_] = copilot.model.prompts[0]
    assert isinstance(system, SystemMessage)
    assert "You work for Dana Whitfield, the compliance manager," in system.text
    assert "You never sign off a case or send one back" in system.text
    copilot.model = stub("Hello, Marcus.")
    copilot.ask("Hello", email=MARCUS)
    [system, *_] = copilot.model.prompts[0]
    assert "You work for Marcus Oyelaran, a compliance reviewer," in system.text


def test_a_refusal_goes_back_to_the_model(copilot: Copilot):
    another_running_dispatch()
    copilot.model = stub(call("start_dispatch", agents=10), "A dispatch is running.")
    [turn] = copilot.ask("Work the queue with 10 agents")["turns"]
    [card] = turn["steps"]
    assert (card["tool"], card["kind"], card["status"], card["reason"]) == (
        "start_dispatch",
        "action",
        "refused",
        "A dispatch is running",
    )
    refusal = copilot.model.prompts[1][-1]
    assert isinstance(refusal, ToolMessage)
    assert refusal.text == "Refused: A dispatch is running"


def run_started(client, copilot: Copilot) -> dict:
    """The run the model was told it started, as the agent reads it."""
    started = json.loads(copilot.model.prompts[1][-1].text)
    run = client.get(run_path(started["run_id"])).json()
    assert started == {"run_id": run["run_id"], "number": run["number"]}
    fail_run(client, run["run_id"])
    return run


def test_starts_with_the_agents_asked_for_or_three(client, copilot: Copilot):
    copilot.model = stub(call("start_dispatch", agents=10), "Started.")
    copilot.ask("Work the queue with 10 agents")
    run = run_started(client, copilot)
    assert (run["kind"], run["agents"]) == ("dispatch", 10)
    copilot.model = stub(call("start_dispatch"), "Started.")
    copilot.ask("Work the queue", email=MARCUS)
    assert run_started(client, copilot)["agents"] == 3
    for evaluation_set in ("development", "held_out", "tiny"):
        copilot.model = stub(
            call("start_evaluation", evaluation_set=evaluation_set),
            "Started.",
        )
        copilot.ask(f"Evaluate the {evaluation_set} set")
        run = run_started(client, copilot)
        assert (run["kind"], run["evaluation_set"], run["agents"]) == (
            "evaluation",
            evaluation_set,
            3,
        )


def test_an_evaluation_of_no_such_set_goes_back_to_the_model(copilot: Copilot):
    [start_evaluation] = [t for t in COPILOT_TOOLS if t.name == "start_evaluation"]
    assert set(start_evaluation.args) == {"evaluation_set", "agents"}
    copilot.model = stub(
        call("start_evaluation", evaluation_set="everything", agents=3),
        "Which set?",
    )
    [turn] = copilot.ask("Evaluate everything")["turns"]
    [card] = turn["steps"]
    assert (card["tool"], card["status"]) == ("start_evaluation", "refused")
    assert "'development', 'held_out' or 'tiny'" in card["reason"]


def test_one_tool_at_a_time_in_order(client, copilot: Copilot):
    awaiting_review(client, "PC-1201", finding())
    calls = [
        call("get_case", case_id="PC-1201"),
        call("get_subcontractor", subcontractor_id="SUB-01"),
        call("lookup_payroll_term", term=TERM),
    ]
    together = AIMessage(content="", tool_calls=[c.tool_calls[0] for c in calls])
    copilot.model = stub(together, ANSWER)
    [turn] = copilot.ask(WHY)["turns"]
    assert [card["tool"] for card in turn["steps"]] == [
        "get_case",
        "get_subcontractor",
        "lookup_payroll_term",
    ]
    for before, after in itertools.pairwise(turn["steps"]):
        assert before["finished_at"] <= after["started_at"]
    assert copilot.model.bound_with[-1] == {"parallel_tool_calls": False}


def test_a_turn_makes_25_model_calls_at_most(copilot: Copilot):
    copilot.model = stub(*[call("get_settings") for _ in range(26)])
    conversation = copilot.ask("Keep looking")
    [turn] = conversation["turns"]
    assert (turn["status"], turn["failure"]) == (
        "failed",
        "TooManyModelCalls: The Copilot made 25 model calls without finishing",
    )
    assert len(copilot.model.prompts) == 25
    copilot.model = stub("Hello again.")
    later = copilot.ask("Hello", conversation["conversation_id"])["turns"][-1]
    assert (later["status"], later["model_calls"]) == ("done", 1)


def test_a_failed_turn_and_a_message_after_it(copilot: Copilot, monkeypatch):
    def broken(sign_in):
        raise RuntimeError("The queue broke\nwith a long story")

    monkeypatch.setattr(app_api, "list_cases", broken)
    asked = call("list_cases")
    copilot.model = stub(asked)
    conversation = copilot.ask("What's in the queue?")
    [turn] = conversation["turns"]
    [card] = turn["steps"]
    assert (card["status"], card["reason"]) == (
        "failed",
        "RuntimeError: The queue broke",
    )
    assert (turn["status"], turn["failure"]) == (
        "failed",
        "RuntimeError: The queue broke",
    )
    copilot.model = stub("Here it is.")
    copilot.ask("Try again", conversation["conversation_id"])
    sent = copilot.model.prompts[0]
    closed, message = sent[-2], sent[-1]
    assert isinstance(closed, ToolMessage)
    assert (closed.tool_call_id, closed.text) == (
        asked.tool_calls[0]["id"],
        "This step stopped before it finished",
    )
    assert message.text == "Try again"
    calls = {c["id"] for m in sent if isinstance(m, AIMessage) for c in m.tool_calls}
    answered = {m.tool_call_id for m in sent if isinstance(m, ToolMessage)}
    assert calls <= answered


def test_a_last_reply_with_no_text_fails_the_turn(copilot: Copilot):
    copilot.model = stub(AIMessage(content=""))
    [turn] = copilot.ask("Hello")["turns"]
    assert (turn["status"], turn["failure"]) == (
        "failed",
        "NoAnswer: The Copilot finished without an answer",
    )


def test_who_is_signed_in_comes_first(copilot: Copilot):
    copilot.model = stub()
    conversation = started(copilot.dashboard)
    turn_id = latest(conversation)["turn_id"]
    with pytest.raises(Refused) as refused:
        turns.the_turn(
            token(DANA, key=OTHER_KEY), conversation["conversation_id"], turn_id
        )
    assert refused.value.status_code == 401
    with pytest.raises(Refused) as refused:
        turns.the_turn(token(MARCUS), conversation["conversation_id"], turn_id)
    assert refused.value.status_code == 404
    with pytest.raises(turns.NotThisTurn):
        turns.the_turn(token(DANA), conversation["conversation_id"], "turn-0")
    assert copilot.model.prompts == []


def test_the_gateway_route_for_the_context_layer(
    copilot: Copilot, gateway, monkeypatch
):
    monkeypatch.setenv(GATEWAY_URL, gateway.url)
    copilot.model = stub(call("lookup_payroll_term", term=TERM), "Read.")
    [turn] = copilot.ask("What's a No Work Week?")["turns"]
    assert gateway.names == ["payrollcheck-context___lookup_payroll_term"]
    assert all(c.signed for c in gateway.calls)
    assert cards_of(turn) == [("lookup_payroll_term", TERM, "done")]


def test_the_copilots_tools(copilot: Copilot):
    copilot.model = stub("Hello.")
    copilot.ask("Hello")
    [bound] = copilot.model.bound_tools
    named = [getattr(t, "name", None) or t.model_config["title"] for t in bound]
    assert named == [
        "list_cases",
        "get_case",
        "list_steps",
        "what_needs_a_reviewer",
        "find_subcontractors",
        "get_subcontractor",
        "get_wage_rate",
        "check_registration",
        "check_apprentice",
        "get_filing_rules",
        "lookup_payroll_term",
        "get_latest_dispatch",
        "list_evaluations",
        "get_settings",
        "wait_for_run",
        "start_dispatch",
        "start_evaluation",
    ]
    for tool in COPILOT_TOOLS:
        assert tool.description, tool.name
        assert "\n" not in tool.description, tool.name
    assert KINDS == {
        "list_cases": "cases",
        "get_case": "cases",
        "list_steps": "cases",
        "what_needs_a_reviewer": "cases",
        "find_subcontractors": "subcontractors",
        "get_subcontractor": "subcontractors",
        "get_wage_rate": "context",
        "check_registration": "context",
        "check_apprentice": "context",
        "get_filing_rules": "context",
        "lookup_payroll_term": "context",
        "get_latest_dispatch": "work",
        "list_evaluations": "work",
        "get_settings": "work",
        "wait_for_run": "work",
        "search_memory": "memory",
        "start_dispatch": "action",
        "start_evaluation": "action",
    }


def test_the_lookups_each_with_a_card(copilot: Copilot):
    copilot.model = stub(
        AIMessage(
            content="",
            tool_calls=[
                {"name": "find_subcontractors", "args": {"name": "garden"}, "id": "f"}
            ],
        ),
        call("get_subcontractor", subcontractor_id="SUB-01"),
        call("list_cases"),
        call("get_latest_dispatch"),
        call("list_evaluations"),
        call("get_settings"),
        "Garden State Electric works on three projects.",
    )
    [turn] = copilot.ask("Tell me about Garden State Electric")["turns"]
    assert [(c["tool"], c["kind"], c["status"]) for c in turn["steps"]] == [
        ("find_subcontractors", "subcontractors", "done"),
        ("get_subcontractor", "subcontractors", "done"),
        ("list_cases", "cases", "done"),
        ("get_latest_dispatch", "work", "done"),
        ("list_evaluations", "work", "done"),
        ("get_settings", "work", "done"),
    ]
    found = copilot.model.prompts[1][-1]
    assert json.loads(found.text) == [
        {"subcontractor_id": "SUB-01", "legal_name": "Garden State Electric LLC"}
    ]
    subcontractor = json.loads(copilot.model.prompts[2][-1].text)
    assert subcontractor["legal_name"] == "Garden State Electric LLC"
    assert "PC-1201" in [c["case_id"] for c in subcontractor["cases"]]
    queue = {c["case_id"]: c for c in json.loads(copilot.model.prompts[3][-1].text)}
    assert queue["PC-0311"]["status"] == "returned_to_sub"


def test_the_five_payroll_lookups_each_with_a_card_and_its_sources(copilot: Copilot):
    copilot.model = stub(
        call("get_wage_rate", question=RATE),
        call("check_registration", registration_no="177511", date="2026-11-23"),
        call("check_apprentice", worker_id="W-059", date="2026-10-19"),
        call("get_filing_rules"),
        call("lookup_payroll_term", term=TERM),
        "Looked up.",
    )
    [turn] = copilot.ask("What's the electrician's rate in Middlesex?")["turns"]
    assert [(c["tool"], c["kind"], c["status"]) for c in turn["steps"]] == [
        ("get_wage_rate", "context", "done"),
        ("check_registration", "context", "done"),
        ("check_apprentice", "context", "done"),
        ("get_filing_rules", "context", "done"),
        ("lookup_payroll_term", "context", "done"),
    ]
    assert [[s["file"] for s in c["sources"]][0] for c in turn["steps"]] == [
        "rate_determinations.yaml",
        "contractor_registry.yaml",
        "apprentice_registrations.yaml",
        "filing_rules.yaml",
        "payroll_glossary.yaml",
    ]
    rate = json.loads(copilot.model.prompts[1][-1].text)
    assert rate["row"]["effective"] == "2026-10-01"
    assert turn["steps"][1]["input"] == "177511 2026-11-23"


def test_a_lookup_the_context_layer_refuses_goes_back_to_the_model(copilot: Copilot):
    copilot.model = stub(
        call("check_registration", registration_no="000000", date="2026-11-23"),
        "No such registration.",
    )
    [turn] = copilot.ask("Is 000000 registered?")["turns"]
    [card] = turn["steps"]
    assert (card["tool"], card["status"]) == ("check_registration", "refused")
    assert card["reason"].endswith("No registration 000000 in the registry")
    refusal = copilot.model.prompts[1][-1]
    assert refusal.text.startswith("Refused: ")
    assert refusal.text.endswith("No registration 000000 in the registry")
    assert turn["status"] == "done"


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("pay_case", {"case_id": "PC-1201"}),
        ("sign_off_case", {"case_id": "PC-1201"}),
        ("send_back_case", {"case_id": "PC-1201", "note": "Fix line 1."}),
        ("check_success_criteria", {}),
    ],
)
def test_a_tool_the_copilot_doesnt_have_goes_back_to_the_model(
    client, copilot: Copilot, tool, args
):
    awaiting_review(client, "PC-1201", finding())
    copilot.model = stub(call(tool, **args), "I can't.")
    [turn] = copilot.ask("Do it")["turns"]
    assert turn["steps"] == []
    assert f"{tool} is not a valid tool" in copilot.model.prompts[1][-1].text
    assert client.get("/api/cases/PC-1201").json()["status"] == "awaiting_review"


def test_a_call_with_bad_inputs_goes_back_to_the_model(copilot: Copilot):
    copilot.model = stub(call("get_case"), "Ok.")
    [turn] = copilot.ask("Look at a case")["turns"]
    [card] = turn["steps"]
    assert (card["tool"], card["status"]) == ("get_case", "refused")
    assert "case_id" in card["reason"]
    assert copilot.model.prompts[1][-1].text.startswith("Refused: ")


def test_the_model_is_the_one_the_app_names(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    model = turns.copilot_model(token(DANA))
    assert (model.model_name, model.reasoning_effort) == ("openai/gpt-6-luna", "low")


def test_a_sign_in_that_runs_out_partway_leaves_the_turn_for_the_app_to_stop(
    copilot: Copilot, monkeypatch
):
    """Once the sign-in runs out, the app refuses every call made with it, so the
    Copilot can't mark the card or the turn failed: the turn stops at once, with
    no more model calls, and the app shows it working until it reads as stopped."""
    call_as = app_api.call_as
    ran_out = False

    def runs_out_at_the_queue(sign_in: str, method: str, path: str, **request):
        nonlocal ran_out
        ran_out = ran_out or path == "/cases"
        if ran_out:
            raise Refused(401, "The sign-in isn't valid. Please sign in again.")
        return call_as(sign_in, method, path, **request)

    monkeypatch.setattr(app_api, "call_as", runs_out_at_the_queue)
    copilot.model = stub(call("list_cases"), "Never asked.")
    with pytest.raises(Refused):
        copilot.ask("What's in the queue?")
    conversation = copilot.read(copilot.last_payload()["conversation_id"])
    [turn] = conversation["turns"]
    [card] = turn["steps"]
    assert (turn["status"], card["status"]) == ("working", "working")
    assert len(copilot.model.prompts) == 1


def test_a_case_outside_the_reviewers_projects_isnt_found(copilot: Copilot):
    """Marcus's sign-in sees only his projects: PC-1217 is on the road
    resurfacing, Priya's, so the app answers as if it didn't exist."""
    copilot.model = stub(call("get_case", case_id="PC-1217"), "I can't find it.")
    [turn] = copilot.ask("What's on PC-1217?", email=MARCUS)["turns"]
    [card] = turn["steps"]
    assert (card["tool"], card["status"], card["reason"]) == (
        "get_case",
        "refused",
        "Case PC-1217 not found",
    )
    refusal = copilot.model.prompts[1][-1]
    assert refusal.text == "Refused: Case PC-1217 not found"
