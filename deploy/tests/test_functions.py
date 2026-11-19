import json

import pytest
from botocore.stub import ANY

from deploy import commands, functions, names, packaging, settings
from deploy.tests.conftest import ACCOUNT

ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/{names.APP_ROLE}"
FUNCTION_ARN = f"arn:aws:lambda:us-east-1:{ACCOUNT}:function:{names.APP_FUNCTION}"
URL = "https://abc.lambda-url.us-east-1.on.aws/"
ENVIRONMENT = {"DATABASE_URL": "postgresql://x:6543/postgres"}
WANTED = functions.APP_SETTINGS | {
    "Role": ROLE_ARN,
    "Environment": {"Variables": ENVIRONMENT},
}


@pytest.fixture
def zip_path(tmp_path):
    path = tmp_path / "lambda.zip"
    path.write_bytes(b"the code")
    return path


def configuration(code_sha256, variables=ENVIRONMENT, **changes):
    """A function's configuration as Lambda reports it."""
    return {
        "FunctionName": names.APP_FUNCTION,
        "FunctionArn": FUNCTION_ARN,
        "CodeSha256": code_sha256,
        "Role": ROLE_ARN,
        "Runtime": "python3.12",
        "Handler": "backend.main.handler",
        "Timeout": 30,
        "MemorySize": 1024,
        "Environment": {"Variables": variables},
        "State": "Active",
        "LastUpdateStatus": "Successful",
    } | changes


def test_a_log_group_is_made_once_and_keeps_its_logs_a_week(aws, stub, capsys):
    logs = stub("logs")
    group = names.log_group(names.APP_FUNCTION)
    logs.add_response(
        "create_log_group", {}, {"logGroupName": group, "tags": names.TAGS}
    )
    logs.add_response(
        "put_retention_policy", {}, {"logGroupName": group, "retentionInDays": 7}
    )
    logs.add_client_error("create_log_group", "ResourceAlreadyExistsException")
    logs.add_response(
        "put_retention_policy", {}, {"logGroupName": group, "retentionInDays": 7}
    )
    functions.make_log_group(aws, group)
    functions.make_log_group(aws, group)
    assert capsys.readouterr().out.splitlines() == [
        f"Log group {group}: created",
        f"Log group {group}: unchanged",
    ]


def test_a_role_lambda_runs_as_writes_to_its_log_group_and_nothing_else(aws, stub):
    iam = stub("iam")
    group = names.log_group(names.APP_FUNCTION)
    role = {
        "Path": "/",
        "RoleName": names.APP_ROLE,
        "RoleId": "AROATESTROLEID0000000",
        "Arn": ROLE_ARN,
        "CreateDate": "2026-11-18T00:00:00Z",
    }
    iam.add_response(
        "create_role",
        {"Role": role},
        {
            "RoleName": names.APP_ROLE,
            "AssumeRolePolicyDocument": json.dumps(functions.LAMBDA_TRUST),
            "Description": "The app's role",
            "Tags": names.tag_list(),
        },
    )
    logging = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": f"arn:aws:logs:us-east-1:{ACCOUNT}:log-group:{group}:*",
            }
        ],
    }
    iam.add_response(
        "put_role_policy",
        {},
        {
            "RoleName": names.APP_ROLE,
            "PolicyName": f"{names.APP_ROLE}-logging",
            "PolicyDocument": json.dumps(logging),
        },
    )
    iam.add_client_error("create_role", "EntityAlreadyExists")
    iam.add_response("get_role", {"Role": role}, {"RoleName": names.APP_ROLE})
    iam.add_response(
        "put_role_policy",
        {},
        {
            "RoleName": names.APP_ROLE,
            "PolicyName": f"{names.APP_ROLE}-logging",
            "PolicyDocument": json.dumps(logging),
        },
    )
    assert functions.make_role(aws, names.APP_ROLE, group, "The app's role") == ROLE_ARN
    assert functions.make_role(aws, names.APP_ROLE, group, "The app's role") == ROLE_ARN


def test_a_new_function_waits_for_its_role_to_reach_lambda(
    aws, stub, zip_path, no_pauses, capsys
):
    lambda_ = stub("lambda")
    lambda_.add_client_error(
        "get_function", "ResourceNotFoundException", http_status_code=404
    )
    lambda_.add_client_error("create_function", "InvalidParameterValueException")
    created = {
        "FunctionName": names.APP_FUNCTION,
        "Code": {"ZipFile": b"the code"},
        "Tags": names.TAGS,
        **WANTED,
    }
    lambda_.add_response("create_function", {"FunctionArn": FUNCTION_ARN}, created)
    lambda_.add_response(
        "get_function", {"Configuration": configuration("x")}, {"FunctionName": ANY}
    )
    functions.deploy_function(aws, names.APP_FUNCTION, zip_path, WANTED)
    assert no_pauses == [3]
    assert capsys.readouterr().out.splitlines() == [
        "Waiting for the new role to reach Lambda",
        f"Function {names.APP_FUNCTION}: created",
    ]


def test_a_function_with_the_same_code_and_settings_is_left_alone(
    aws, stub, zip_path, capsys
):
    lambda_ = stub("lambda")
    same = {"Configuration": configuration(packaging.code_sha256(zip_path))}
    lambda_.add_response("get_function", same, {"FunctionName": names.APP_FUNCTION})
    functions.deploy_function(aws, names.APP_FUNCTION, zip_path, WANTED)
    assert capsys.readouterr().out == f"Function {names.APP_FUNCTION}: unchanged\n"


def test_a_function_whose_code_changed_gets_the_new_code_only(
    aws, stub, zip_path, capsys
):
    lambda_ = stub("lambda")
    old = {"Configuration": configuration("old-sha")}
    lambda_.add_response("get_function", old)
    lambda_.add_response(
        "update_function_code",
        {},
        {"FunctionName": names.APP_FUNCTION, "ZipFile": b"the code"},
    )
    lambda_.add_response("get_function", old)
    functions.deploy_function(aws, names.APP_FUNCTION, zip_path, WANTED)
    assert capsys.readouterr().out == f"Function {names.APP_FUNCTION}: updated code\n"


def test_a_function_whose_settings_changed_gets_them(aws, stub, zip_path, capsys):
    lambda_ = stub("lambda")
    old = {
        "Configuration": configuration(
            packaging.code_sha256(zip_path), variables={"DATABASE_URL": "old"}
        )
    }
    lambda_.add_response("get_function", old)
    lambda_.add_response(
        "update_function_configuration",
        {},
        {"FunctionName": names.APP_FUNCTION, **WANTED},
    )
    lambda_.add_response("get_function", old)
    functions.deploy_function(aws, names.APP_FUNCTION, zip_path, WANTED)
    assert capsys.readouterr().out == (
        f"Function {names.APP_FUNCTION}: updated settings\n"
    )


def test_a_function_with_no_environment_wanting_none_is_left_alone(
    aws, stub, zip_path, capsys
):
    lambda_ = stub("lambda")
    there = configuration(packaging.code_sha256(zip_path))
    del there["Environment"]
    lambda_.add_response("get_function", {"Configuration": there})
    wanted = WANTED | {"Environment": {"Variables": {}}}
    functions.deploy_function(aws, names.APP_FUNCTION, zip_path, wanted)
    assert capsys.readouterr().out == f"Function {names.APP_FUNCTION}: unchanged\n"


def test_a_function_whose_code_and_settings_changed_gets_both(
    aws, stub, zip_path, capsys
):
    lambda_ = stub("lambda")
    old = {"Configuration": configuration("old-sha", variables={"DATABASE_URL": "x"})}
    lambda_.add_response("get_function", old)
    lambda_.add_response("update_function_code", {})
    lambda_.add_response("get_function", old)
    lambda_.add_response("update_function_configuration", {})
    lambda_.add_response("get_function", old)
    functions.deploy_function(aws, names.APP_FUNCTION, zip_path, WANTED)
    assert capsys.readouterr().out == (
        f"Function {names.APP_FUNCTION}: updated code and settings\n"
    )


def test_the_step_needs_the_dashboards_publishable_key(aws, monkeypatch):
    monkeypatch.delenv("VITE_SUPABASE_PUBLISHABLE_KEY", raising=False)
    with pytest.raises(functions.settings.MissingSettings, match="PUBLISHABLE"):
        functions.run(aws)


def test_a_function_url_is_made_the_first_time(aws, stub, capsys):
    lambda_ = stub("lambda")
    lambda_.add_client_error(
        "get_function_url_config", "ResourceNotFoundException", http_status_code=404
    )
    answer = {
        "FunctionUrl": URL,
        "FunctionArn": FUNCTION_ARN,
        "AuthType": "AWS_IAM",
        "CreationTime": "2026-11-18T00:00:00Z",
    }
    lambda_.add_response(
        "create_function_url_config",
        answer,
        {"FunctionName": names.CONTEXT_FUNCTION, "AuthType": "AWS_IAM"},
    )
    lambda_.add_response(
        "get_function_url_config", answer | {"LastModifiedTime": "2026-11-18"}
    )
    first = functions.function_url(aws, names.CONTEXT_FUNCTION, "AWS_IAM")
    second = functions.function_url(aws, names.CONTEXT_FUNCTION, "AWS_IAM")
    assert first == second == URL.rstrip("/")
    assert capsys.readouterr().out.splitlines()[-1].endswith("unchanged")


def test_the_app_is_public_through_its_url_only(aws, stub):
    lambda_ = stub("lambda")
    for statement in functions.PUBLIC_ACCESS:
        lambda_.add_response(
            "add_permission",
            {"Statement": "{}"},
            {"FunctionName": names.APP_FUNCTION, "Principal": "*", **statement},
        )
    for _ in functions.PUBLIC_ACCESS:
        lambda_.add_client_error("add_permission", "ResourceConflictException")
    functions.allow_the_public(aws)
    functions.allow_the_public(aws)


@pytest.fixture
def app_settings(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://postgres.ref:pw@pooler.supabase.com:5432/postgres"
    )
    monkeypatch.setenv("VITE_SUPABASE_URL", "https://ref.supabase.co")
    monkeypatch.setenv("PAYROLLCHECK_API_KEY", "the-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "the-judges-key")


def test_the_apps_environment_is_on_the_transaction_pooler(aws, stub, app_settings):
    stub("lambda").add_client_error(
        "get_function", "ResourceNotFoundException", http_status_code=404
    )
    assert functions.app_environment(aws) == {
        "DATABASE_URL": "postgresql://postgres.ref:pw@pooler.supabase.com:6543/postgres",
        "VITE_SUPABASE_URL": "https://ref.supabase.co",
        "PAYROLLCHECK_API_KEY": "the-key",
        "OPENROUTER_API_KEY": "the-judges-key",
    }


def test_the_app_needs_openrouters_key_for_the_judge(aws, app_settings, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    with pytest.raises(settings.MissingSettings, match="OPENROUTER_API_KEY"):
        functions.app_environment(aws)


def test_the_apps_environment_keeps_the_runtimes(aws, stub, app_settings):
    runtimes = {
        "PAYROLLCHECK_AGENT_RUNTIME": "arn:agent",
        "PAYROLLCHECK_COPILOT_RUNTIME": "arn:copilot",
    }
    there = configuration("x", variables={"DATABASE_URL": "old", **runtimes})
    stub("lambda").add_response("get_function", {"Configuration": there})
    environment = functions.app_environment(aws)
    assert environment["PAYROLLCHECK_AGENT_RUNTIME"] == "arn:agent"
    assert environment["PAYROLLCHECK_COPILOT_RUNTIME"] == "arn:copilot"
    assert environment["DATABASE_URL"].endswith(":6543/postgres")


def test_the_step_builds_the_dashboard_then_both_functions(
    aws, monkeypatch, app_settings, capsys
):
    monkeypatch.setenv("VITE_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    done: list[str] = []
    monkeypatch.setattr(functions, "app_environment", lambda _: ENVIRONMENT)
    monkeypatch.setattr(commands, "run", lambda command: done.append(" ".join(command)))

    def deploy_app(_, environment):
        done.append(f"app with {sorted(environment)}")
        return "https://app"

    monkeypatch.setattr(functions, "deploy_app", deploy_app)
    monkeypatch.setattr(functions, "deploy_context", lambda _: "https://context")
    functions.run(aws)
    assert done == ["npm run build", "app with ['DATABASE_URL']"]
    assert capsys.readouterr().out.splitlines() == [
        "The app: https://app",
        "The context layer: https://context",
    ]


def test_each_function_is_packaged_with_its_group(aws, monkeypatch, zip_path):
    built: list[tuple[str, str, dict[str, str]]] = []
    deployed: list[tuple[str, dict]] = []

    def build(name, group, folders):
        built.append((name, group, folders))
        return zip_path

    monkeypatch.setattr(packaging, "build", build)
    monkeypatch.setattr(functions, "make_log_group", lambda *_: None)
    monkeypatch.setattr(functions, "make_role", lambda *_: ROLE_ARN)
    monkeypatch.setattr(
        functions,
        "deploy_function",
        lambda _, name, path, wanted: deployed.append((name, wanted)),
    )
    monkeypatch.setattr(functions, "function_url", lambda _, name, auth: auth)
    monkeypatch.setattr(functions, "allow_the_public", lambda _: None)
    assert functions.deploy_app(aws, ENVIRONMENT) == "NONE"
    assert functions.deploy_context(aws) == "AWS_IAM"
    assert built == [
        (
            "lambda",
            "server",
            {"backend": "backend", "data": "data", "dashboard/dist": "dashboard/dist"},
        ),
        ("context", "context", {"context": "context"}),
    ]
    assert deployed == [
        (names.APP_FUNCTION, WANTED),
        (
            names.CONTEXT_FUNCTION,
            functions.CONTEXT_SETTINGS
            | {"Role": ROLE_ARN, "Environment": {"Variables": {}}},
        ),
    ]


def test_the_app_is_pointed_at_the_runtimes_once(aws, stub, capsys):
    lambda_ = stub("lambda")
    runtimes = {"PAYROLLCHECK_AGENT_RUNTIME": "arn:agent"}
    lambda_.add_response("get_function", {"Configuration": configuration("x")})
    lambda_.add_response(
        "update_function_configuration",
        {},
        {
            "FunctionName": names.APP_FUNCTION,
            "Environment": {"Variables": ENVIRONMENT | runtimes},
        },
    )
    lambda_.add_response("get_function", {"Configuration": configuration("x")})
    lambda_.add_response(
        "get_function",
        {"Configuration": configuration("x", variables=ENVIRONMENT | runtimes)},
    )
    functions.point_the_app_at(aws, runtimes)
    functions.point_the_app_at(aws, runtimes)
    assert capsys.readouterr().out.splitlines() == [
        f"Function {names.APP_FUNCTION}'s runtimes: updated",
        f"Function {names.APP_FUNCTION}'s runtimes: unchanged",
    ]
