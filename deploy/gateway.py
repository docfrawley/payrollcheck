"""Step 4, the Gateway: its role, the Gateway, and its two targets, the app's operations
for the payroll agent, from the agent's own API document, which the deployed app
serves, with the agent's key, and the context layer's tools, as Ed's make_gateway and
put_targets made them."""

import json
from functools import partial
from typing import Any

import httpx

from agent.routes import Target
from backend import agent_api as agent_api_document
from backend.dependencies import API_KEY_HEADER
from deploy import names, resources, settings, waits
from deploy.aws import POLICY_VERSION, Aws

AGENTCORE = "bedrock-agentcore"
# Where the context layer's MCP endpoint is under its Function URL.
MCP = "/mcp"
# What a target compares on, to tell whether it needs updating.
COMPARED = ("description", "targetConfiguration", "credentialProviderConfigurations")


def gateway_trust(aws: Aws) -> dict[str, Any]:
    """Who may run as the Gateway's role: AgentCore, for our Gateway alone."""
    return {
        "Version": POLICY_VERSION,
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": aws.account},
                    "ArnLike": {
                        "aws:SourceArn": aws.arn(
                            AGENTCORE, f"gateway/{names.GATEWAY}-*"
                        )
                    },
                },
            }
        ],
    }


def make_gateway_role(aws: Aws, provider: dict[str, Any], context_arn: str) -> str:
    """The Gateway's role: it fetches the app's key and invokes the context layer.
    Returns its ARN."""
    iam = aws.client("iam")
    try:
        role = iam.create_role(
            RoleName=names.GATEWAY_ROLE,
            AssumeRolePolicyDocument=json.dumps(gateway_trust(aws)),
            Description="The role the PayrollCheck Gateway runs as",
            Tags=names.tag_list(),
        )["Role"]
        print(f"Role {names.GATEWAY_ROLE}: created")
    except iam.exceptions.EntityAlreadyExistsException:
        role = iam.get_role(RoleName=names.GATEWAY_ROLE)["Role"]
        print(f"Role {names.GATEWAY_ROLE}: unchanged")
    for name, policy in gateway_role_policies(aws, provider, context_arn).items():
        iam.put_role_policy(
            RoleName=names.GATEWAY_ROLE,
            PolicyName=name,
            PolicyDocument=json.dumps(policy),
        )
    return role["Arn"]


def gateway_role_policies(
    aws: Aws, provider: dict[str, Any], context_arn: str
) -> dict[str, dict[str, Any]]:
    """What the Gateway's role may do: fetch the app's key from AgentCore Identity,
    and invoke the context layer."""
    provider_arn = provider["credentialProviderArn"]
    directory = aws.arn(AGENTCORE, "workload-identity-directory/default")
    workload_identity = [directory, f"{directory}/workload-identity/{names.GATEWAY}-*"]
    token_vault = provider_arn.split("/apikeycredentialprovider/")[0]
    return {
        f"{names.GATEWAY_ROLE}-api-key": {
            "Version": POLICY_VERSION,
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "bedrock-agentcore:GetWorkloadAccessToken",
                    "Resource": workload_identity,
                },
                {
                    "Effect": "Allow",
                    "Action": "bedrock-agentcore:GetResourceApiKey",
                    "Resource": [provider_arn, token_vault, *workload_identity],
                },
                {
                    "Effect": "Allow",
                    "Action": "secretsmanager:GetSecretValue",
                    "Resource": provider["apiKeySecretArn"]["secretArn"],
                },
            ],
        },
        f"{names.GATEWAY_ROLE}-context": {
            "Version": POLICY_VERSION,
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["lambda:InvokeFunctionUrl", "lambda:InvokeFunction"],
                    "Resource": context_arn,
                }
            ],
        },
    }


def gateway_settings(role_arn: str) -> dict[str, Any]:
    """The Gateway's settings, which every update sends again."""
    return {
        "name": names.GATEWAY,
        "description": "PayrollCheck's app and context layer as the agent's tools",
        "roleArn": role_arn,
        "protocolType": "MCP",
        "authorizerType": "AWS_IAM",
        "exceptionLevel": "DEBUG",
    }


def make_gateway(aws: Aws, role_arn: str) -> dict[str, Any]:
    """Create the Gateway, waiting for its new role to reach AgentCore, unless it's
    there. Returns it, once it's ready."""
    control = resources.control(aws)
    gateway = resources.find_gateway(aws)
    if gateway:
        print(f"Gateway {names.GATEWAY}: unchanged")
        gateway_id = gateway["gatewayId"]
    else:
        gateway_id = waits.retry(
            lambda: control.create_gateway(
                **gateway_settings(role_arn), tags=names.TAGS
            )["gatewayId"],
            lambda error: (
                isinstance(error, control.exceptions.ValidationException)
                and waits.says("role")(error)
            ),
            tries=10,
            every=3,
            message="Waiting for the new role to reach AgentCore",
        )
        print(f"Gateway {names.GATEWAY}: created")
    ready = waits.wait_for(
        lambda: control.get_gateway(gatewayIdentifier=gateway_id),
        f"Gateway {gateway_id}",
    )
    if ready["status"] != "READY":
        raise RuntimeError(f"The Gateway is {ready['status']}")
    return ready


def agent_api(app_url: str, api_key: str, client: httpx.Client) -> dict[str, Any]:
    """The payroll agent's API document from the deployed app, with the app's
    address as its server, trying again while a new function starts."""

    def fetch() -> httpx.Response:
        response = client.get(
            f"{app_url}{agent_api_document.PATH}",
            headers={API_KEY_HEADER: api_key},
            timeout=60,
        )
        response.raise_for_status()
        return response

    response = waits.retry(
        fetch,
        lambda error: isinstance(error, httpx.HTTPError),
        tries=5,
        every=3,
        message="Waiting for the app to answer",
    )
    return response.json() | {"servers": [{"url": app_url}]}


def app_target(document: dict[str, Any], provider: dict[str, Any]) -> dict[str, Any]:
    """The app's target: the payroll agent's operations, sent with its key."""
    return {
        "name": Target.APP,
        "description": "The PayrollCheck app's operations for the payroll agent",
        "targetConfiguration": {
            "mcp": {"openApiSchema": {"inlinePayload": json.dumps(document)}}
        },
        "credentialProviderConfigurations": [
            {
                "credentialProviderType": "API_KEY",
                "credentialProvider": {
                    "apiKeyCredentialProvider": {
                        "providerArn": provider["credentialProviderArn"],
                        "credentialParameterName": API_KEY_HEADER,
                        "credentialLocation": "HEADER",
                    }
                },
            }
        ],
    }


def context_target(aws: Aws, context_url: str) -> dict[str, Any]:
    """The context layer's target: its five lookups, the Gateway's role signing for
    Lambda."""
    return {
        "name": Target.CONTEXT,
        "description": "PayrollCheck's context layer: rates, registrations and rules",
        "targetConfiguration": {
            "mcp": {"mcpServer": {"endpoint": f"{context_url}{MCP}"}}
        },
        "credentialProviderConfigurations": [
            {
                "credentialProviderType": "GATEWAY_IAM_ROLE",
                "credentialProvider": {
                    "iamCredentialProvider": {"service": "lambda", "region": aws.region}
                },
            }
        ],
    }


def put_target(aws: Aws, gateway_id: str, wanted: dict[str, Any]) -> dict[str, Any]:
    """Create a target, or update it when it differs, and try again while the
    Gateway's role can't be used yet."""
    control = resources.control(aws)
    for _ in range(20):
        targets = resources.find_targets(aws, gateway_id)
        there = [t for t in targets if t["name"] == wanted["name"]]
        if there:
            target_id = there[0]["targetId"]
            current = control.get_gateway_target(
                gatewayIdentifier=gateway_id, targetId=target_id
            )
            differing = [key for key in COMPARED if current.get(key) != wanted[key]]
            if current["status"] == "READY" and not differing:
                print(f"Target {wanted['name']}: unchanged")
                return current
            print(f"Target {wanted['name']}: updating {', '.join(differing) or 'it'}")
            control.update_gateway_target(
                gatewayIdentifier=gateway_id, targetId=target_id, **wanted
            )
        else:
            target_id = control.create_gateway_target(
                gatewayIdentifier=gateway_id, **wanted
            )["targetId"]
        target = waits.wait_for(
            partial(
                control.get_gateway_target,
                gatewayIdentifier=gateway_id,
                targetId=target_id,
            ),
            f"Target {wanted['name']}",
        )
        reasons = " ".join(target.get("statusReasons", []))
        if target["status"] == "READY" or not waits.mentions(
            reasons, "role", "Authorization"
        ):
            return target
        print("Waiting for the Gateway's role to reach AgentCore")
        waits.pause(10)
    raise RuntimeError("AgentCore could not use the Gateway's role")


def run(aws: Aws) -> None:
    """Step 4: the Gateway's role, the Gateway and its two targets."""
    api_key = settings.required(settings.API_KEY)[settings.API_KEY]
    provider = resources.key_provider(aws)
    context_arn = resources.function_arn(aws, names.CONTEXT_FUNCTION)
    role_arn = make_gateway_role(aws, provider, context_arn)
    gateway = make_gateway(aws, role_arn)
    app_url = resources.function_url(aws, names.APP_FUNCTION)
    with httpx.Client() as client:
        document = agent_api(app_url, api_key, client)
    put_target(aws, gateway["gatewayId"], app_target(document, provider))
    context_url = resources.function_url(aws, names.CONTEXT_FUNCTION)
    put_target(aws, gateway["gatewayId"], context_target(aws, context_url))
    print(f"The Gateway: {gateway['gatewayUrl']}")
