"""Who may call each of the backend's operations: anyone, the agent with its key, a
signed-in reviewer or the agent, or a signed-in reviewer alone."""

from backend.tests.settings_requests import STARTING

ROUND = "/api/improvement/rounds/round-1"
PROPOSAL = f"{ROUND}/proposals/proposal-1"

OPEN = {"health"}

# Every operation only the agent's side calls.
AGENT_OPERATIONS = {
    "start_case",
    "record_step",
    "record_model_call",
    "record_work_time",
    "record_check_findings",
    "record_screening_flag",
    "record_exception_report",
    "fail_case",
    "get_version",
    "get_current_version",
    "get_screening",
    "record_run_heartbeat",
    "fail_run",
    "create_round_evaluation",
    "record_run_cases",
    "finish_run",
    "get_round",
    "get_proposal",
    "record_round_heartbeat",
    "fail_round",
    "get_improver_view",
    "record_change_proposal",
    "record_recipe_proposal",
    "create_version",
    "create_recipe",
    "record_verdict",
    "record_improver_call",
    "finish_round",
}

# The reads both the dashboard and the agent use, with a path each answers, the
# run's once a dispatch has started.
SHARED_READS = {
    "list_cases": "/api/cases",
    "get_case": "/api/cases/PC-1201",
    "get_payroll_history": "/api/cases/PC-1201/history",
    "get_project": "/api/projects/PRJ-01",
    "list_subcontractors": "/api/projects/PRJ-01/subcontractors",
    "get_agent_api": "/api/agent/openapi.json",
    "get_run": "/api/runs/{run_id}",
}

CONVERSATION = "/api/copilot/conversations/conversation-1"
TURN = "/api/copilot/turns/turn-1"

# Every operation only a signed-in reviewer may use, with a body it would accept.
REVIEWER_OPERATIONS = {
    "get_signed_in_reviewer": ("GET", "/api/me", None),
    "list_steps": ("GET", "/api/cases/PC-1202/steps", None),
    "list_projects": ("GET", "/api/projects", None),
    "upload_payroll": (
        "POST",
        "/api/projects/PRJ-01/payrolls",
        {"subcontractor_id": "SUB-01", "file_name": "p.csv", "content": ""},
    ),
    "get_configuration": ("GET", "/api/configuration", None),
    "get_version_details": ("GET", "/api/configuration/versions/1", None),
    "get_settings": ("GET", "/api/settings", None),
    "change_settings": ("PUT", "/api/settings", STARTING),
    "get_latest_dispatch": ("GET", "/api/dispatches/latest", None),
    "start_dispatch": ("POST", "/api/dispatches", {"agents": 3}),
    "list_evaluations": ("GET", "/api/evaluations", None),
    "get_evaluation": ("GET", "/api/evaluations/run-1", None),
    "start_evaluation": (
        "POST",
        "/api/evaluations",
        {"evaluation_set": "tiny", "agents": 5},
    ),
    "sign_off_case": ("POST", "/api/cases/PC-1202/sign-off", None),
    "send_back_case": ("POST", "/api/cases/PC-1202/send-back", None),
    "list_rules": ("GET", "/api/rules", None),
    "save_notice": (
        "PUT",
        "/api/cases/PC-1202/notice",
        {"text": "Please correct line 1 and resubmit."},
    ),
    "dismiss_exception": (
        "POST",
        "/api/cases/PC-1202/exceptions/1/dismissal",
        {"reason": "A false positive"},
    ),
    "restore_exception": (
        "POST",
        "/api/cases/PC-1202/exceptions/1/restoration",
        {"reason": "Dismissed by mistake"},
    ),
    "add_exception": (
        "POST",
        "/api/cases/PC-1202/exceptions",
        {
            "rule": "sequence.gap",
            "worker_id": None,
            "line_no": None,
            "expected": "Payroll 12",
            "actual": "Payroll 14",
            "shortfall_cents": None,
            "reason": "The agent missed the gap",
        },
    ),
    "get_improvement": ("GET", "/api/improvement", None),
    "get_recipe": ("GET", "/api/improvement/recipes/1", None),
    "start_round": ("POST", "/api/improvement/rounds", None),
    "stop_round": ("POST", f"{ROUND}/stop", None),
    "approve_proposal": ("POST", f"{PROPOSAL}/approval", None),
    "reject_proposal": ("POST", f"{PROPOSAL}/rejection", {"reason": "Too broad"}),
    "find_subcontractors": ("GET", "/api/subcontractors?name=garden", None),
    "get_subcontractor": ("GET", "/api/subcontractors/SUB-01", None),
    "list_conversations": ("GET", "/api/copilot/conversations", None),
    "start_conversation": (
        "POST",
        "/api/copilot/conversations",
        {"message": "What needs me today?"},
    ),
    "get_conversation": ("GET", CONVERSATION, None),
    "send_message": (
        "POST",
        f"{CONVERSATION}/messages",
        {"message": "And the latest dispatch?"},
    ),
    "get_copilot_model": ("GET", "/api/copilot/model", None),
    "start_copilot_step": (
        "POST",
        f"{TURN}/steps",
        {"tool": "get_case", "kind": "cases", "input": "PC-1201", "asked": "{}"},
    ),
    "finish_copilot_step": (
        "POST",
        f"{TURN}/steps/1/finish",
        {"status": "done", "answer": "{}", "reason": None, "sources": []},
    ),
    "finish_turn": (
        "POST",
        f"{TURN}/finish",
        {"answer": "Nothing needs you.", "model_calls": 2, "cost": 0.001},
    ),
    "fail_turn": ("POST", f"{TURN}/failure", {"reason": "It broke"}),
}
