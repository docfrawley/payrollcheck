import json

import httpx
import pytest
from botocore.stub import ANY

from deploy import gateway, names
from deploy.tests.conftest import ACCOUNT

PROVIDER_ARN = (
    f"arn:aws:bedrock-agentcore:us-east-1:{ACCOUNT}:token-vault/default/"
    "apikeycredentialprovider/payrollcheck-app-key"
)
PROVIDER = {
    "credentialProviderArn": PROVIDER_ARN,
    "apiKeySecretArn": {
        "secretArn": f"arn:aws:secretsmanager:us-east-1:{ACCOUNT}:secret:k"
    },
}
CONTEXT_ARN = f"arn:aws:lambda:us-east-1:{ACCOUNT}:function:payrollcheck-context"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/{names.GATEWAY_ROLE}"
APP_URL = "https://app.lambda-url.us-east-1.on.aws"
GATEWAY_ID = "payrollcheck-gateway-a1b2"
ROLE = {
    "Path": "/",
    "RoleName": names.GATEWAY_ROLE,
    "RoleId": "AROATESTROLEID0000000",
    "Arn": ROLE_ARN,
    "CreateDate": "2026-11-18T00:00:00Z",
}
GATEWAY = {
    "gatewayArn": f"arn:aws:bedrock-agentcore:us-east-1:{ACCOUNT}:gateway/{GATEWAY_ID}",
    "gatewayId": GATEWAY_ID,
    "gatewayUrl": "https://gw.example/mcp",
    "createdAt": "2026-11-18T00:00:00Z",
    "updatedAt": "2026-11-18T00:00:00Z",
    "status": "READY",
    "name": names.GATEWAY,
    "roleArn": ROLE_ARN,
    "protocolType": "MCP",
    "authorizerType": "AWS_IAM",
}


def test_the_gateways_role_fetches_the_key_and_invokes_the_context_layer_only(aws):
    policies = gateway.gateway_role_policies(aws, PROVIDER, CONTEXT_ARN)
    api_key, context = policies.values()
    directory = (
        f"arn:aws:bedrock-agentcore:us-east-1:{ACCOUNT}:"
        "workload-identity-directory/default"
    )
    assert api_key["Statement"][1] == {
        "Effect": "Allow",
        "Action": "bedrock-agentcore:GetResourceApiKey",
        "Resource": [
            PROVIDER_ARN,
            f"arn:aws:bedrock-agentcore:us-east-1:{ACCOUNT}:token-vault/default",
            directory,
            f"{directory}/workload-identity/{names.GATEWAY}-*",
        ],
    }
    assert (
        api_key["Statement"][2]["Resource"] == PROVIDER["apiKeySecretArn"]["secretArn"]
    )
    assert context["Statement"] == [
        {
            "Effect": "Allow",
            "Action": ["lambda:InvokeFunctionUrl", "lambda:InvokeFunction"],
            "Resource": CONTEXT_ARN,
        }
    ]


def test_only_agentcore_runs_as_the_gateways_role_and_only_for_our_gateway(aws):
    statement = gateway.gateway_trust(aws)["Statement"][0]
    assert statement["Principal"] == {"Service": "bedrock-agentcore.amazonaws.com"}
    assert statement["Condition"] == {
        "StringEquals": {"aws:SourceAccount": ACCOUNT},
        "ArnLike": {
            "aws:SourceArn": (
                f"arn:aws:bedrock-agentcore:us-east-1:{ACCOUNT}:gateway/"
                f"{names.GATEWAY}-*"
            )
        },
    }


def test_the_gateways_role_is_made_once_with_its_two_policies(aws, stub, capsys):
    iam = stub("iam")
    policies = gateway.gateway_role_policies(aws, PROVIDER, CONTEXT_ARN)
    iam.add_response(
        "create_role",
        {"Role": ROLE},
        {
            "RoleName": names.GATEWAY_ROLE,
            "AssumeRolePolicyDocument": json.dumps(gateway.gateway_trust(aws)),
            "Description": ANY,
            "Tags": names.tag_list(),
        },
    )
    puts = [
        {
            "RoleName": names.GATEWAY_ROLE,
            "PolicyName": name,
            "PolicyDocument": json.dumps(document),
        }
        for name, document in policies.items()
    ]
    for put in puts:
        iam.add_response("put_role_policy", {}, put)
    iam.add_client_error("create_role", "EntityAlreadyExists")
    iam.add_response("get_role", {"Role": ROLE}, {"RoleName": names.GATEWAY_ROLE})
    for put in puts:
        iam.add_response("put_role_policy", {}, put)
    assert gateway.make_gateway_role(aws, PROVIDER, CONTEXT_ARN) == ROLE_ARN
    assert gateway.make_gateway_role(aws, PROVIDER, CONTEXT_ARN) == ROLE_ARN
    assert capsys.readouterr().out.splitlines() == [
        f"Role {names.GATEWAY_ROLE}: created",
        f"Role {names.GATEWAY_ROLE}: unchanged",
    ]


def gateway_listing(*gateway_names):
    return {
        "items": [
            {
                "gatewayId": GATEWAY_ID,
                "name": name,
                "status": "READY",
                "createdAt": "2026-11-18T00:00:00Z",
                "updatedAt": "2026-11-18T00:00:00Z",
                "authorizerType": "AWS_IAM",
                "protocolType": "MCP",
            }
            for name in gateway_names
        ]
    }


def test_a_new_gateway_waits_for_its_role_to_reach_agentcore(
    aws, stub, no_pauses, capsys
):
    control = stub("bedrock-agentcore-control")
    control.add_response("list_gateways", gateway_listing())
    control.add_client_error(
        "create_gateway", "ValidationException", "The role can't be assumed"
    )
    control.add_response(
        "create_gateway",
        GATEWAY | {"status": "CREATING"},
        {
            "name": names.GATEWAY,
            "description": ANY,
            "roleArn": ROLE_ARN,
            "protocolType": "MCP",
            "authorizerType": "AWS_IAM",
            "exceptionLevel": "DEBUG",
            "tags": names.TAGS,
        },
    )
    control.add_response("get_gateway", GATEWAY | {"status": "CREATING"})
    control.add_response("get_gateway", GATEWAY, {"gatewayIdentifier": GATEWAY_ID})
    assert gateway.make_gateway(aws, ROLE_ARN)["status"] == "READY"
    assert no_pauses == [3, 3]
    assert f"Gateway {names.GATEWAY}: created" in capsys.readouterr().out


def test_a_gateway_thats_there_is_left_alone(aws, stub, capsys):
    control = stub("bedrock-agentcore-control")
    control.add_response("list_gateways", gateway_listing("other", names.GATEWAY))
    control.add_response("get_gateway", GATEWAY, {"gatewayIdentifier": GATEWAY_ID})
    control.add_response("get_gateway", GATEWAY, {"gatewayIdentifier": GATEWAY_ID})
    gateway.make_gateway(aws, ROLE_ARN)
    assert capsys.readouterr().out.startswith(f"Gateway {names.GATEWAY}: unchanged")


def test_the_agents_api_document_names_the_app_as_its_server(no_pauses):
    asked: list[httpx.Request] = []

    def answer(request):
        asked.append(request)
        if len(asked) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"openapi": "3.1.0", "paths": {}})

    with httpx.Client(transport=httpx.MockTransport(answer)) as client:
        document = gateway.agent_api(APP_URL, "the-key", client)
    assert document == {
        "openapi": "3.1.0",
        "paths": {},
        "servers": [{"url": APP_URL}],
    }
    assert str(asked[-1].url) == f"{APP_URL}/api/agent/openapi.json"
    assert asked[-1].headers["X-API-Key"] == "the-key"
    assert no_pauses == [3]


def test_the_targets_are_the_apps_operations_with_the_key_and_the_context_layer(aws):
    app = gateway.app_target({"paths": {}}, PROVIDER)
    assert app["name"] == "payrollcheck-app"
    assert json.loads(
        app["targetConfiguration"]["mcp"]["openApiSchema"]["inlinePayload"]
    ) == {"paths": {}}
    assert app["credentialProviderConfigurations"][0]["credentialProvider"] == {
        "apiKeyCredentialProvider": {
            "providerArn": PROVIDER_ARN,
            "credentialParameterName": "X-API-Key",
            "credentialLocation": "HEADER",
        }
    }
    context = gateway.context_target(aws, "https://ctx.lambda-url.us-east-1.on.aws")
    assert context["name"] == "payrollcheck-context"
    assert context["targetConfiguration"] == {
        "mcp": {
            "mcpServer": {"endpoint": "https://ctx.lambda-url.us-east-1.on.aws/mcp"}
        }
    }
    assert context["credentialProviderConfigurations"] == [
        {
            "credentialProviderType": "GATEWAY_IAM_ROLE",
            "credentialProvider": {
                "iamCredentialProvider": {"service": "lambda", "region": "us-east-1"}
            },
        }
    ]


def target(wanted, status="READY", reasons=()):
    return {
        "gatewayArn": GATEWAY["gatewayArn"],
        "targetId": "TARGET0001",
        "createdAt": "2026-11-18T00:00:00Z",
        "updatedAt": "2026-11-18T00:00:00Z",
        "status": status,
        "statusReasons": list(reasons),
        "name": wanted["name"],
        "description": wanted["description"],
        "targetConfiguration": wanted["targetConfiguration"],
        "credentialProviderConfigurations": wanted["credentialProviderConfigurations"],
    }


def target_listing(*target_names):
    return {
        "items": [
            {
                "targetId": "TARGET0001",
                "name": name,
                "status": "READY",
                "createdAt": "2026-11-18T00:00:00Z",
                "updatedAt": "2026-11-18T00:00:00Z",
            }
            for name in target_names
        ]
    }


@pytest.fixture
def wanted(aws):
    return gateway.context_target(aws, "https://ctx.lambda-url.us-east-1.on.aws")


def test_a_target_thats_the_same_is_left_alone(aws, stub, wanted, capsys):
    control = stub("bedrock-agentcore-control")
    control.add_response("list_gateway_targets", target_listing(wanted["name"]))
    control.add_response("get_gateway_target", target(wanted))
    gateway.put_target(aws, GATEWAY_ID, wanted)
    assert capsys.readouterr().out == f"Target {wanted['name']}: unchanged\n"


def test_a_target_that_differs_is_updated(aws, stub, wanted):
    control = stub("bedrock-agentcore-control")
    old = target(wanted) | {"description": "Old"}
    control.add_response("list_gateway_targets", target_listing(wanted["name"]))
    control.add_response("get_gateway_target", old)
    control.add_response(
        "update_gateway_target",
        target(wanted),
        {"gatewayIdentifier": GATEWAY_ID, "targetId": "TARGET0001", **wanted},
    )
    control.add_response("get_gateway_target", target(wanted))
    assert gateway.put_target(aws, GATEWAY_ID, wanted)["status"] == "READY"


def test_a_new_target_is_tried_again_while_the_gateways_role_isnt_usable(
    aws, stub, wanted, no_pauses, capsys
):
    control = stub("bedrock-agentcore-control")
    control.add_response("list_gateway_targets", target_listing())
    control.add_response(
        "create_gateway_target",
        target(wanted, "CREATING"),
        {"gatewayIdentifier": GATEWAY_ID, **wanted},
    )
    control.add_response(
        "get_gateway_target",
        target(wanted, "FAILED", ["Failed to obtain execution role credentials"]),
    )
    control.add_response("list_gateway_targets", target_listing(wanted["name"]))
    control.add_response(
        "get_gateway_target",
        target(wanted, "FAILED", ["Failed to obtain execution role credentials"]),
    )
    control.add_response("update_gateway_target", target(wanted, "UPDATING"))
    control.add_response("get_gateway_target", target(wanted))
    assert gateway.put_target(aws, GATEWAY_ID, wanted)["status"] == "READY"
    assert no_pauses == [10]
    assert (
        "Waiting for the Gateway's role to reach AgentCore" in capsys.readouterr().out
    )


def test_a_target_that_fails_for_another_reason_is_given_back(aws, stub, wanted):
    control = stub("bedrock-agentcore-control")
    control.add_response("list_gateway_targets", target_listing())
    control.add_response("create_gateway_target", target(wanted, "CREATING"))
    control.add_response(
        "get_gateway_target", target(wanted, "FAILED", ["The endpoint isn't MCP"])
    )
    assert gateway.put_target(aws, GATEWAY_ID, wanted)["status"] == "FAILED"


def test_the_step_puts_both_targets_on_the_gateway(aws, monkeypatch, capsys):
    put: list[str] = []
    monkeypatch.setattr(gateway.resources, "key_provider", lambda _: PROVIDER)
    monkeypatch.setattr(gateway.resources, "function_arn", lambda _, name: CONTEXT_ARN)
    monkeypatch.setattr(gateway, "make_gateway_role", lambda *_: ROLE_ARN)
    monkeypatch.setattr(gateway, "make_gateway", lambda *_: GATEWAY)
    monkeypatch.setattr(
        gateway.resources, "function_url", lambda _, name: f"https://{name}"
    )
    monkeypatch.setattr(gateway, "agent_api", lambda url, key, client: {"url": url})
    monkeypatch.setattr(
        gateway, "put_target", lambda _, gateway_id, wanted: put.append(wanted["name"])
    )
    gateway.run(aws)
    assert put == ["payrollcheck-app", "payrollcheck-context"]
    assert capsys.readouterr().out == "The Gateway: https://gw.example/mcp\n"


def test_a_target_is_given_up_on_when_the_role_never_arrives(
    aws, monkeypatch, wanted, no_pauses
):
    class Control:
        def create_gateway_target(self, **_):
            return {"targetId": "TARGET0001"}

        def get_gateway_target(self, **_):
            return target(wanted, "FAILED", ["Authorization failed for the role"])

    monkeypatch.setattr(gateway.resources, "control", lambda _: Control())
    monkeypatch.setattr(gateway.resources, "find_targets", lambda *_: [])
    with pytest.raises(RuntimeError, match="Gateway's role"):
        gateway.put_target(aws, GATEWAY_ID, wanted)
    assert no_pauses == [10] * 20


def test_the_apps_target_with_the_same_document_is_left_alone(aws, stub, capsys):
    wanted = gateway.app_target({"openapi": "3.1.0", "paths": {}}, PROVIDER)
    control = stub("bedrock-agentcore-control")
    control.add_response("list_gateway_targets", target_listing(wanted["name"]))
    control.add_response("get_gateway_target", target(wanted))
    gateway.put_target(aws, GATEWAY_ID, wanted)
    assert capsys.readouterr().out == f"Target {wanted['name']}: unchanged\n"


def test_a_gateway_that_isnt_ready_stops_the_step(aws, stub):
    control = stub("bedrock-agentcore-control")
    control.add_response("list_gateways", gateway_listing(names.GATEWAY))
    control.add_response("get_gateway", GATEWAY | {"status": "FAILED"})
    control.add_response("get_gateway", GATEWAY | {"status": "FAILED"})
    with pytest.raises(RuntimeError, match="FAILED"):
        gateway.make_gateway(aws, ROLE_ARN)
