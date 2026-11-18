"""What the runbook made: everything named for PayrollCheck, with its tags, as Ed's
show_resources listed it, and the teardown, which deletes only what's named and
tagged for PayrollCheck, in the order AWS needs, and only with --yes."""

from collections.abc import Callable
from dataclasses import dataclass, field

from deploy import commands, names, resources, waits
from deploy.aws import Aws

RUNTIME = "Runtime"
STACK = "Stack"
# The CDK's bootstrap stack, which agentcore deploy makes once in an account.
BOOTSTRAP_STACK = "CDKToolkit"
BOOTSTRAP = "CDK bootstrap"
SHOWN_ONLY = (RUNTIME, BOOTSTRAP)


@dataclass
class Found:
    """One resource the runbook made, or one named as if it had."""

    kind: str
    name: str
    tags: dict[str, str]
    delete: Callable[[], None]
    shown: str = ""
    then: list[str] = field(default_factory=list)


def agentcore_tags(aws: Aws, arn: str) -> dict[str, str]:
    """An AgentCore resource's tags."""
    return resources.control(aws).list_tags_for_resource(resourceArn=arn)["tags"]


def find_stack(aws: Aws) -> list[Found]:
    """The runtimes' stack, which agentcore deploy made."""
    cloudformation = aws.client("cloudformation")
    stacks = [
        stack
        for page in cloudformation.get_paginator("describe_stacks").paginate()
        for stack in page["Stacks"]
        if stack["StackName"] in (names.STACK, BOOTSTRAP_STACK)
    ]

    def delete() -> None:
        """As Ed's teardown did: the CLI takes everything out of the project, then
        deploys nothing, which deletes the stack with both runtimes and the three
        credentials it made in AgentCore Identity, secrets and all. The project's
        file is put back from git, ready for the next deploy."""
        commands.run(["agentcore", "remove", "all", "--yes"])
        commands.run(["agentcore", "deploy", "--yes"])
        commands.run(["git", "checkout", "--", "agentcore/agentcore.json"])

    return [
        Found(
            STACK,
            names.STACK,
            {t["Key"]: t["Value"] for t in stack.get("Tags", [])},
            delete,
            stack["StackStatus"],
        )
        if stack["StackName"] == names.STACK
        else Found(BOOTSTRAP, BOOTSTRAP_STACK, {}, lambda: None, stack["StackStatus"])
        for stack in stacks
    ]


def find_runtimes(aws: Aws) -> list[Found]:
    """The two runtimes, shown with their ARNs, which go with their stack."""
    found = []
    for name in (names.AGENT_RUNTIME, names.COPILOT_RUNTIME):
        runtime = resources.find_runtime(aws, name)
        if runtime:
            arn = runtime["agentRuntimeArn"]
            found.append(Found(RUNTIME, name, {}, lambda: None, arn))
    return found


def find_gateway(aws: Aws) -> list[Found]:
    """The Gateway, deleted after its targets."""
    gateway = resources.find_gateway(aws)
    if gateway is None:
        return []
    control = resources.control(aws)
    gateway_id = gateway["gatewayId"]
    targets = resources.find_targets(aws, gateway_id)

    def delete() -> None:
        for target in resources.find_targets(aws, gateway_id):
            control.delete_gateway_target(
                gatewayIdentifier=gateway_id, targetId=target["targetId"]
            )
        waits.until_gone(lambda: resources.find_targets(aws, gateway_id), "targets")
        control.delete_gateway(gatewayIdentifier=gateway_id)
        # Its policy engine can't go while the Gateway, still deleting, holds it.
        waits.until_gone(
            lambda: list(filter(None, [resources.find_gateway(aws)])), "Gateway"
        )

    return [
        Found(
            "Gateway",
            gateway["name"],
            agentcore_tags(aws, gateway["gatewayArn"]),
            delete,
            gateway["gatewayUrl"],
            [f"its target {t['name']}" for t in targets],
        )
    ]


def find_policy_engine(aws: Aws) -> list[Found]:
    """The policy engine, deleted after its policies."""
    engine = resources.find_policy_engine(aws)
    if engine is None:
        return []
    control = resources.control(aws)
    engine_id = engine["policyEngineId"]
    policies = resources.find_policies(aws, engine_id)

    def delete() -> None:
        for each in resources.find_policies(aws, engine_id):
            control.delete_policy(policyEngineId=engine_id, policyId=each["policyId"])
        waits.until_gone(lambda: resources.find_policies(aws, engine_id), "policies")
        control.delete_policy_engine(policyEngineId=engine_id)

    return [
        Found(
            "Policy engine",
            engine["name"],
            agentcore_tags(aws, engine["policyEngineArn"]),
            delete,
            f"{len(policies)} permits",
            [f"its policy {p['name']}" for p in policies],
        )
    ]


def find_key_provider(aws: Aws) -> list[Found]:
    """The Gateway's credential."""
    providers = resources.listed(
        aws, "list_api_key_credential_providers", "credentialProviders"
    )
    return [
        Found(
            "Credential provider",
            p["name"],
            agentcore_tags(aws, p["credentialProviderArn"]),
            lambda: resources.control(aws).delete_api_key_credential_provider(
                name=names.KEY_PROVIDER
            ),
        )
        for p in providers
        if p["name"] == names.KEY_PROVIDER
    ]


def find_memory(aws: Aws) -> list[Found]:
    """The Copilot's Memory."""
    memory = resources.find_memory(aws)
    if memory is None:
        return []
    return [
        Found(
            "Memory",
            memory["id"],
            agentcore_tags(aws, memory["arn"]),
            lambda: resources.control(aws).delete_memory(memoryId=memory["id"]),
            memory["id"],
        )
    ]


def find_function(aws: Aws, name: str) -> list[Found]:
    """A function, shown with its URL, and its log group."""
    functions = aws.client("lambda")
    logs = aws.client("logs")
    found = []
    try:
        arn = resources.function_arn(aws, name)
    except functions.exceptions.ResourceNotFoundException:
        arn = None
    if arn:
        tags = functions.list_tags(Resource=arn)["Tags"]
        found.append(
            Found(
                "Function",
                name,
                tags,
                lambda: functions.delete_function(FunctionName=name),
                resources.function_url(aws, name),
            )
        )
    group = names.log_group(name)
    for each in logs.describe_log_groups(logGroupNamePrefix=group)["logGroups"]:
        if each["logGroupName"] == group:
            tags = logs.list_tags_for_resource(
                resourceArn=each["arn"].removesuffix(":*")
            )["tags"]
            found.append(
                Found(
                    "Log group",
                    group,
                    tags,
                    lambda: logs.delete_log_group(logGroupName=group),
                )
            )
    return found


def find_role(aws: Aws, name: str) -> list[Found]:
    """A role the runbook made, deleted with its inline policies."""
    iam = aws.client("iam")
    try:
        tags = iam.list_role_tags(RoleName=name)["Tags"]
    except iam.exceptions.NoSuchEntityException:
        return []

    def delete() -> None:
        for policy_name in iam.list_role_policies(RoleName=name)["PolicyNames"]:
            iam.delete_role_policy(RoleName=name, PolicyName=policy_name)
        iam.delete_role(RoleName=name)

    return [Found("Role", name, {t["Key"]: t["Value"] for t in tags}, delete)]


def everything(aws: Aws) -> list[Found]:
    """What the runbook made, in the order it can be deleted."""
    return [
        *find_stack(aws),
        *find_runtimes(aws),
        *find_gateway(aws),
        *find_policy_engine(aws),
        *find_key_provider(aws),
        *find_memory(aws),
        *find_function(aws, names.APP_FUNCTION),
        *find_function(aws, names.CONTEXT_FUNCTION),
        *find_role(aws, names.APP_ROLE),
        *find_role(aws, names.CONTEXT_ROLE),
        *find_role(aws, names.GATEWAY_ROLE),
    ]


def show(aws: Aws) -> None:
    """Print what's there, by kind, with each value the next step or .env needs."""
    found = everything(aws)
    if not found:
        print("Nothing of PayrollCheck's is there yet")
    for each in found:
        shown = f"  {each.shown}" if each.shown else ""
        print(f"{each.kind + ':':<21}{each.name}{shown}")
        for part in each.then:
            print(f"{'':<21}  with {part}")


def runtime_log_groups(aws: Aws) -> list[str]:
    """The runtimes' own log groups, which Runtime makes and the runbook doesn't tag."""
    prefix = f"/aws/bedrock-agentcore/runtimes/{names.PROJECT}"
    groups = aws.client("logs").describe_log_groups(logGroupNamePrefix=prefix)
    return [group["logGroupName"] for group in groups["logGroups"]]


def tear_down(aws: Aws, *, yes: bool) -> None:
    """Delete what's named and tagged for PayrollCheck, or with no --yes say what
    would go, and say what's left for the user to remove by hand."""
    there = everything(aws)
    # The runtimes go with their stack, and the bootstrap is every project's.
    found = [each for each in there if each.kind not in SHOWN_ONLY]
    ours = [each for each in found if names.is_ours(each.name, each.tags)]
    for each in found:
        if each not in ours:
            print(f"Left: {each.kind} {each.name}, which isn't tagged for PayrollCheck")
    if not any(each.kind == STACK for each in ours):
        for each in there:
            if each.kind == RUNTIME:
                print(f"Left: {each.kind} {each.name}, since its stack is left")
    if not yes:
        for each in ours:
            print(f"Would delete: {each.kind} {each.name}")
        print("Nothing was deleted. Run the teardown again with --yes to delete these.")
        return
    for each in ours:
        each.delete()
        print(f"{each.kind} {each.name}: deleted")
    left_by_hand(aws)


def left_by_hand(aws: Aws) -> None:
    """What the teardown leaves, and how to remove each."""
    for group in runtime_log_groups(aws):
        print(f"Left: log group {group}, which Runtime made; delete it in CloudWatch")
    print(
        "Left: agentcore/.env.local, and the CLI's own state of the deploy in "
        "agentcore/.cli/ and agentcore/aws-targets.json, which git ignores."
    )
    print(
        "Left: the CDK bootstrap, the CDKToolkit stack and its cdk-* bucket, which "
        "agentcore deploy made for every project in the account. Empty the bucket, "
        "then delete the stack in CloudFormation, if nothing else uses it."
    )
    print("Left: the Supabase project. Pause or delete it in Supabase's dashboard.")
