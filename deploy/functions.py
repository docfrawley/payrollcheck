"""Step 2, Lambda: the app with the dashboard as one function behind a public Function
URL, and the context layer as a function behind a Function URL with IAM auth, each
with its log group and role, as Ed's deploy_app and deploy_context made them."""

import json
from contextlib import suppress
from pathlib import Path
from typing import Any

from backend import agent_service, copilot_service
from deploy import commands, names, packaging, resources, settings, waits
from deploy.aws import POLICY_VERSION, Aws

LAMBDA_TRUST = {
    "Version": POLICY_VERSION,
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}
RETENTION_DAYS = 7
# A Function URL anyone may call, and one only callers allowed to invoke it may.
PUBLIC = "NONE"
SIGNED = "AWS_IAM"
UPDATED = "function_updated_v2"
RUNTIME = f"python{packaging.PYTHON}"
PUBLIC_ACCESS = [
    {
        "StatementId": "public-url",
        "Action": "lambda:InvokeFunctionUrl",
        "FunctionUrlAuthType": PUBLIC,
    },
    {
        "StatementId": "public-invoke",
        "Action": "lambda:InvokeFunction",
        "InvokedViaFunctionUrl": True,
    },
]
APP_SETTINGS = {
    "Runtime": RUNTIME,
    "Handler": "backend.main.handler",
    "Timeout": 30,
    "MemorySize": 1024,
}
CONTEXT_SETTINGS = {
    "Runtime": RUNTIME,
    "Handler": "context.server.handler",
    "Timeout": 30,
    "MemorySize": 512,
}
# The function's settings that the Runtimes step adds, which this step keeps.
RUNTIMES = (agent_service.RUNTIME, copilot_service.RUNTIME)


def make_log_group(aws: Aws, name: str) -> None:
    """A log group that keeps its logs for 7 days, tagged for the project."""
    logs = aws.client("logs")
    try:
        logs.create_log_group(logGroupName=name, tags=names.TAGS)
        print(f"Log group {name}: created")
    except logs.exceptions.ResourceAlreadyExistsException:
        print(f"Log group {name}: unchanged")
    logs.put_retention_policy(logGroupName=name, retentionInDays=RETENTION_DAYS)


def make_role(aws: Aws, role_name: str, log_group: str, description: str) -> str:
    """A role Lambda runs a function as, which may write to its log group and do
    nothing else. Returns its ARN."""
    iam = aws.client("iam")
    try:
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(LAMBDA_TRUST),
            Description=description,
            Tags=names.tag_list(),
        )["Role"]
        print(f"Role {role_name}: created")
    except iam.exceptions.EntityAlreadyExistsException:
        role = iam.get_role(RoleName=role_name)["Role"]
        print(f"Role {role_name}: unchanged")
    logging = {
        "Version": POLICY_VERSION,
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": aws.arn("logs", f"log-group:{log_group}:*"),
            }
        ],
    }
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=f"{role_name}-logging",
        PolicyDocument=json.dumps(logging),
    )
    return role["Arn"]


def variables_of(current: dict[str, Any]) -> dict[str, str]:
    """A function's environment as Lambda reports it, which leaves out an empty one."""
    return current.get("Environment", {}).get("Variables", {})


def differs(current: dict[str, Any], wanted: dict[str, Any]) -> bool:
    """Whether any of the settings wanted differs from the function's."""
    reported = current | {"Environment": {"Variables": variables_of(current)}}
    return any(reported.get(key) != value for key, value in wanted.items())


def create_function(
    aws: Aws, name: str, zip_path: Path, wanted: dict[str, Any]
) -> None:
    """Create a function, trying again while its new role can't be used by Lambda."""
    functions = aws.client("lambda")
    zip_bytes = zip_path.read_bytes()
    waits.retry(
        lambda: functions.create_function(
            FunctionName=name, Code={"ZipFile": zip_bytes}, Tags=names.TAGS, **wanted
        ),
        lambda error: isinstance(
            error, functions.exceptions.InvalidParameterValueException
        ),
        tries=10,
        every=3,
        message="Waiting for the new role to reach Lambda",
    )
    functions.get_waiter("function_active_v2").wait(FunctionName=name)
    print(f"Function {name}: created")


def update_function(
    aws: Aws, current: dict[str, Any], zip_path: Path, wanted: dict[str, Any]
) -> None:
    """Update a function's code when its zip differs from Lambda's, and its settings
    when they differ, and leave it alone when neither does."""
    functions = aws.client("lambda")
    name = current["FunctionName"]
    changed = []
    if current["CodeSha256"] != packaging.code_sha256(zip_path):
        functions.update_function_code(FunctionName=name, ZipFile=zip_path.read_bytes())
        functions.get_waiter(UPDATED).wait(FunctionName=name)
        changed.append("code")
    if differs(current, wanted):
        functions.update_function_configuration(FunctionName=name, **wanted)
        functions.get_waiter(UPDATED).wait(FunctionName=name)
        changed.append("settings")
    done = f"updated {' and '.join(changed)}" if changed else "unchanged"
    print(f"Function {name}: {done}")


def deploy_function(
    aws: Aws, name: str, zip_path: Path, wanted: dict[str, Any]
) -> None:
    """Create the function, or update it in place."""
    functions = aws.client("lambda")
    try:
        current = functions.get_function(FunctionName=name)["Configuration"]
    except functions.exceptions.ResourceNotFoundException:
        create_function(aws, name, zip_path, wanted)
    else:
        update_function(aws, current, zip_path, wanted)


def function_url(aws: Aws, name: str, auth_type: str) -> str:
    """The function's URL, made the first time, without its closing slash."""
    functions = aws.client("lambda")
    try:
        url = resources.function_url(aws, name)
        print(f"Function URL of {name}: unchanged")
    except functions.exceptions.ResourceNotFoundException:
        url = functions.create_function_url_config(
            FunctionName=name, AuthType=auth_type
        )["FunctionUrl"].rstrip("/")
        print(f"Function URL of {name}: created")
    return url


def allow_the_public(aws: Aws) -> None:
    """Let anyone call the app through its Function URL, and nothing else."""
    functions = aws.client("lambda")
    for statement in PUBLIC_ACCESS:
        with suppress(functions.exceptions.ResourceConflictException):
            functions.add_permission(
                FunctionName=names.APP_FUNCTION, Principal="*", **statement
            )


def app_environment(aws: Aws) -> dict[str, str]:
    """The app's environment: the database on the transaction pooler, Supabase's
    address and the agent's key, and the runtimes' ARNs when it already has them."""
    found = settings.required(
        settings.DATABASE_URL, settings.SUPABASE_URL, settings.API_KEY
    )
    environment = {
        settings.DATABASE_URL: settings.pooled(found[settings.DATABASE_URL]),
        settings.SUPABASE_URL: found[settings.SUPABASE_URL],
        settings.API_KEY: found[settings.API_KEY],
    }
    functions = aws.client("lambda")
    try:
        current = functions.get_function(FunctionName=names.APP_FUNCTION)
    except functions.exceptions.ResourceNotFoundException:
        return environment
    variables = variables_of(current["Configuration"])
    return environment | {
        name: variables[name] for name in RUNTIMES if name in variables
    }


def point_the_app_at(aws: Aws, runtimes: dict[str, str]) -> None:
    """Add the runtimes' ARNs to the app's environment, unless it has them."""
    functions = aws.client("lambda")
    current = functions.get_function(FunctionName=names.APP_FUNCTION)["Configuration"]
    variables = variables_of(current) | runtimes
    if variables == variables_of(current):
        print(f"Function {names.APP_FUNCTION}'s runtimes: unchanged")
        return
    functions.update_function_configuration(
        FunctionName=names.APP_FUNCTION, Environment={"Variables": variables}
    )
    functions.get_waiter(UPDATED).wait(FunctionName=names.APP_FUNCTION)
    print(f"Function {names.APP_FUNCTION}'s runtimes: updated")


def deploy_app(aws: Aws, environment: dict[str, str]) -> str:
    """The app, with the dashboard npm run build made, on Lambda behind its public
    Function URL. Returns the URL."""
    zip_path = packaging.build(
        "lambda",
        "server",
        {"backend": "backend", "data": "data", "dashboard/dist": "dashboard/dist"},
    )
    log_group = names.log_group(names.APP_FUNCTION)
    make_log_group(aws, log_group)
    role = make_role(
        aws,
        names.APP_ROLE,
        log_group,
        "The role the PayrollCheck app runs as on Lambda",
    )
    wanted = APP_SETTINGS | {"Role": role, "Environment": {"Variables": environment}}
    deploy_function(aws, names.APP_FUNCTION, zip_path, wanted)
    url = function_url(aws, names.APP_FUNCTION, PUBLIC)
    allow_the_public(aws)
    return url


def deploy_context(aws: Aws) -> str:
    """The context layer on Lambda behind an IAM Function URL. Returns the URL."""
    zip_path = packaging.build("context", "context", {"context": "context"})
    log_group = names.log_group(names.CONTEXT_FUNCTION)
    make_log_group(aws, log_group)
    role = make_role(
        aws,
        names.CONTEXT_ROLE,
        log_group,
        "The role PayrollCheck's context layer runs as on Lambda",
    )
    wanted = CONTEXT_SETTINGS | {"Role": role, "Environment": {"Variables": {}}}
    deploy_function(aws, names.CONTEXT_FUNCTION, zip_path, wanted)
    return function_url(aws, names.CONTEXT_FUNCTION, SIGNED)


def run(aws: Aws) -> None:
    """Step 2: build the dashboard, then the app and the context layer on Lambda."""
    settings.required(settings.SUPABASE_PUBLISHABLE_KEY)
    environment = app_environment(aws)
    commands.run(["npm", "run", "build"])
    print(f"The app: {deploy_app(aws, environment)}")
    print(f"The context layer: {deploy_context(aws)}")
