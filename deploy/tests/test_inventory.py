import pytest

from deploy import inventory, names, resources
from deploy.tests.conftest import ACCOUNT

OURS = names.TAGS
RUNTIME_LOGS = "/aws/bedrock-agentcore/runtimes/payrollcheck_x-DEFAULT"


def found(kind, name, tags, deleted, **shown):
    """A resource that keeps its name in deleted when it's deleted."""
    return inventory.Found(kind, name, tags, lambda: deleted.append(name), **shown)


@pytest.fixture
def account(monkeypatch):
    """An account holding the Gateway and two roles, one of them not tagged for us,
    keeping what the teardown deletes."""
    deleted: list[str] = []
    there = [
        found("Runtime", names.AGENT_RUNTIME, {}, deleted, shown="arn:runtime/agent"),
        found(
            "Gateway",
            names.GATEWAY,
            OURS,
            deleted,
            shown="https://gw/mcp",
            then=["its target payrollcheck-app"],
        ),
        found("Role", names.APP_ROLE, OURS, deleted),
        found("Role", names.GATEWAY_ROLE, {}, deleted),
    ]
    monkeypatch.setattr(inventory, "everything", lambda _: there)
    monkeypatch.setattr(inventory, "runtime_log_groups", lambda _: [])
    return deleted


def test_show_lists_what_is_there_with_its_values(aws, account, capsys):
    inventory.show(aws)
    assert capsys.readouterr().out.splitlines() == [
        f"Runtime:             {names.AGENT_RUNTIME}  arn:runtime/agent",
        f"Gateway:             {names.GATEWAY}  https://gw/mcp",
        "                       with its target payrollcheck-app",
        f"Role:                {names.APP_ROLE}",
        f"Role:                {names.GATEWAY_ROLE}",
    ]


def test_show_says_when_nothing_is_there(aws, monkeypatch, capsys):
    monkeypatch.setattr(inventory, "everything", lambda _: [])
    inventory.show(aws)
    assert capsys.readouterr().out == "Nothing of PayrollCheck's is there yet\n"


def test_without_yes_the_teardown_deletes_nothing(aws, account, capsys):
    inventory.tear_down(aws, yes=False)
    assert account == []
    shown = capsys.readouterr().out.splitlines()
    assert shown == [
        f"Left: Role {names.GATEWAY_ROLE}, which isn't tagged for PayrollCheck",
        f"Left: Runtime {names.AGENT_RUNTIME}, since its stack is left",
        f"Would delete: Gateway {names.GATEWAY}",
        f"Would delete: Role {names.APP_ROLE}",
        "Nothing was deleted. Run the teardown again with --yes to delete these.",
    ]


def test_with_yes_it_deletes_only_whats_named_and_tagged_for_us(aws, account, capsys):
    inventory.tear_down(aws, yes=True)
    assert account == [names.GATEWAY, names.APP_ROLE]
    shown = capsys.readouterr().out
    assert f"Left: Role {names.GATEWAY_ROLE}" in shown
    assert "CDKToolkit" in shown
    assert "Supabase project" in shown


def test_a_role_is_deleted_with_its_inline_policies(aws, stub):
    iam = stub("iam")
    iam.add_response(
        "list_role_tags",
        {"Tags": names.tag_list()},
        {"RoleName": names.CONTEXT_ROLE},
    )
    iam.add_response(
        "list_role_policies",
        {"PolicyNames": [f"{names.CONTEXT_ROLE}-logging"]},
        {"RoleName": names.CONTEXT_ROLE},
    )
    iam.add_response(
        "delete_role_policy",
        {},
        {"RoleName": names.CONTEXT_ROLE, "PolicyName": f"{names.CONTEXT_ROLE}-logging"},
    )
    iam.add_response("delete_role", {}, {"RoleName": names.CONTEXT_ROLE})
    (role,) = inventory.find_role(aws, names.CONTEXT_ROLE)
    assert role.tags == OURS
    role.delete()


def test_a_role_thats_not_there_isnt_found(aws, stub):
    stub("iam").add_client_error("list_role_tags", "NoSuchEntity")
    assert inventory.find_role(aws, names.APP_ROLE) == []


def test_a_function_is_found_with_its_url_and_its_log_group(aws, stub):
    lambda_ = stub("lambda")
    logs = stub("logs")
    arn = f"arn:aws:lambda:us-east-1:{ACCOUNT}:function:{names.APP_FUNCTION}"
    group = names.log_group(names.APP_FUNCTION)
    group_arn = f"arn:aws:logs:us-east-1:{ACCOUNT}:log-group:{group}"
    lambda_.add_response("get_function", {"Configuration": {"FunctionArn": arn}})
    lambda_.add_response("list_tags", {"Tags": OURS}, {"Resource": arn})
    lambda_.add_response(
        "get_function_url_config",
        {
            "FunctionUrl": "https://app.lambda-url.us-east-1.on.aws/",
            "FunctionArn": arn,
            "AuthType": "NONE",
            "CreationTime": "2026-11-18",
            "LastModifiedTime": "2026-11-18",
        },
    )
    logs.add_response(
        "describe_log_groups",
        {"logGroups": [{"logGroupName": group, "arn": f"{group_arn}:*"}]},
        {"logGroupNamePrefix": group},
    )
    logs.add_response(
        "list_tags_for_resource", {"tags": OURS}, {"resourceArn": group_arn}
    )
    lambda_.add_response("delete_function", {}, {"FunctionName": names.APP_FUNCTION})
    logs.add_response("delete_log_group", {}, {"logGroupName": group})
    function, log_group = inventory.find_function(aws, names.APP_FUNCTION)
    assert function.shown == "https://app.lambda-url.us-east-1.on.aws"
    assert (log_group.kind, log_group.tags) == ("Log group", OURS)
    function.delete()
    log_group.delete()


def test_a_function_thats_not_there_isnt_found(aws, stub):
    stub("lambda").add_client_error("get_function", "ResourceNotFoundException")
    stub("logs").add_response("describe_log_groups", {"logGroups": []})
    assert inventory.find_function(aws, names.CONTEXT_FUNCTION) == []


def test_the_stack_goes_as_eds_did_through_the_cli_with_its_credentials(
    aws, stub, monkeypatch
):
    ran: list[list[str]] = []
    monkeypatch.setattr(inventory.commands, "run", ran.append)
    stack = {
        "StackName": names.STACK,
        "CreationTime": "2026-11-18T00:00:00Z",
        "StackStatus": "CREATE_COMPLETE",
        "Tags": names.tag_list(),
    }
    bootstrap = stack | {"StackName": "CDKToolkit", "Tags": []}
    stub("cloudformation").add_response(
        "describe_stacks", {"Stacks": [stack, bootstrap, stack | {"StackName": "x"}]}
    )
    found_stack, found_bootstrap = inventory.find_stack(aws)
    assert (found_stack.kind, found_stack.tags) == ("Stack", OURS)
    assert (found_bootstrap.kind, found_bootstrap.name) == (
        "CDK bootstrap",
        "CDKToolkit",
    )
    found_stack.delete()
    assert ran == [
        ["agentcore", "remove", "all", "--yes"],
        ["agentcore", "deploy", "--yes"],
        ["git", "checkout", "--", "agentcore/agentcore.json"],
    ]


def test_everything_is_found_in_the_order_aws_can_delete_it(aws, monkeypatch):
    for finder, kind in [
        ("find_stack", "Stack"),
        ("find_runtimes", "Runtime"),
        ("find_gateway", "Gateway"),
        ("find_policy_engine", "Policy engine"),
        ("find_key_provider", "Credential provider"),
        ("find_memory", "Memory"),
    ]:
        monkeypatch.setattr(
            inventory, finder, lambda _, kind=kind: [found(kind, kind, OURS, [])]
        )
    monkeypatch.setattr(
        inventory, "find_function", lambda _, name: [found("Function", name, OURS, [])]
    )
    monkeypatch.setattr(
        inventory, "find_role", lambda _, name: [found("Role", name, OURS, [])]
    )
    assert [(each.kind, each.name) for each in inventory.everything(aws)] == [
        ("Stack", "Stack"),
        ("Runtime", "Runtime"),
        ("Gateway", "Gateway"),
        ("Policy engine", "Policy engine"),
        ("Credential provider", "Credential provider"),
        ("Memory", "Memory"),
        ("Function", names.APP_FUNCTION),
        ("Function", names.CONTEXT_FUNCTION),
        ("Role", names.APP_ROLE),
        ("Role", names.CONTEXT_ROLE),
        ("Role", names.GATEWAY_ROLE),
    ]


def test_the_gateway_goes_after_its_targets(aws, monkeypatch, no_pauses):
    calls: list[str] = []
    targets = [[{"targetId": "T1", "name": "payrollcheck-app"}]] * 2 + [
        [{"targetId": "T1", "name": "payrollcheck-app"}],
        [],
    ]

    class Control:
        def delete_gateway_target(self, **inputs):
            calls.append(f"target {inputs['targetId']}")

        def delete_gateway(self, **inputs):
            calls.append(f"gateway {inputs['gatewayIdentifier']}")

        def list_tags_for_resource(self, **_):
            return {"tags": OURS}

    found = {
        "gatewayId": "gw-1",
        "gatewayArn": "arn:gw",
        "name": names.GATEWAY,
        "gatewayUrl": "https://gw/mcp",
    }
    gateways = [found, found, None]
    monkeypatch.setattr(resources, "control", lambda _: Control())
    monkeypatch.setattr(resources, "find_gateway", lambda _: gateways.pop(0))
    monkeypatch.setattr(resources, "find_targets", lambda *_: targets.pop(0))
    (gateway,) = inventory.find_gateway(aws)
    assert gateway.then == ["its target payrollcheck-app"]
    gateway.delete()
    assert calls == ["target T1", "gateway gw-1"]
    assert no_pauses == [3, 3]
    assert gateways == []


def test_the_engine_goes_after_its_policies(aws, monkeypatch, no_pauses):
    calls: list[str] = []
    one = [{"policyId": "P1", "name": "payrollcheck_allow_app_get_case"}]
    policies = [one, one, []]

    class Control:
        def delete_policy(self, **inputs):
            calls.append(f"policy {inputs['policyId']}")

        def delete_policy_engine(self, **inputs):
            calls.append(f"engine {inputs['policyEngineId']}")

        def list_tags_for_resource(self, **_):
            return {"tags": OURS}

    monkeypatch.setattr(resources, "control", lambda _: Control())
    monkeypatch.setattr(
        resources,
        "find_policy_engine",
        lambda _: {
            "policyEngineId": "e-1",
            "policyEngineArn": "arn:e",
            "name": names.POLICY_ENGINE,
        },
    )
    monkeypatch.setattr(resources, "find_policies", lambda *_: policies.pop(0))
    (engine,) = inventory.find_policy_engine(aws)
    assert engine.shown == "1 permits"
    engine.delete()
    assert calls == ["policy P1", "engine e-1"]


def test_the_memory_the_key_provider_and_the_runtimes_are_found(aws, monkeypatch):
    deleted: list[str] = []

    class Control:
        def list_tags_for_resource(self, **_):
            return {"tags": OURS}

        def delete_memory(self, **inputs):
            deleted.append(inputs["memoryId"])

        def delete_api_key_credential_provider(self, **inputs):
            deleted.append(inputs["name"])

    monkeypatch.setattr(resources, "control", lambda _: Control())
    monkeypatch.setattr(
        resources, "find_memory", lambda _: {"id": "memory-1", "arn": "arn:memory"}
    )
    monkeypatch.setattr(
        resources,
        "listed",
        lambda *_: [{"name": names.KEY_PROVIDER, "credentialProviderArn": "arn:k"}],
    )
    monkeypatch.setattr(
        resources,
        "find_runtime",
        lambda _, name: {"agentRuntimeArn": f"arn:{name}"},
    )
    (memory,) = inventory.find_memory(aws)
    (provider,) = inventory.find_key_provider(aws)
    memory.delete()
    provider.delete()
    assert deleted == ["memory-1", names.KEY_PROVIDER]
    assert [r.shown for r in inventory.find_runtimes(aws)] == [
        f"arn:{names.AGENT_RUNTIME}",
        f"arn:{names.COPILOT_RUNTIME}",
    ]


def test_the_runtimes_own_log_groups_are_left_and_named(aws, stub, capsys):
    stub("logs").add_response(
        "describe_log_groups",
        {"logGroups": [{"logGroupName": RUNTIME_LOGS}]},
        {"logGroupNamePrefix": "/aws/bedrock-agentcore/runtimes/payrollcheck"},
    )
    inventory.left_by_hand(aws)
    assert f"Left: log group {RUNTIME_LOGS}" in capsys.readouterr().out
