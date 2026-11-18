from deploy import names, resources
from deploy.tests.conftest import ACCOUNT

MEMORY = {
    "arn": f"arn:aws:bedrock-agentcore:us-east-1:{ACCOUNT}:memory/x",
    "createdAt": "2026-11-18T00:00:00Z",
    "updatedAt": "2026-11-18T00:00:00Z",
}


def test_no_gateway_is_found_when_ours_isnt_there(aws, stub):
    stub("bedrock-agentcore-control").add_response(
        "list_gateways",
        {
            "items": [
                {
                    "gatewayId": "other-gateway-1",
                    "name": "other-gateway",
                    "status": "READY",
                    "createdAt": "2026-11-18T00:00:00Z",
                    "updatedAt": "2026-11-18T00:00:00Z",
                    "authorizerType": "AWS_IAM",
                    "protocolType": "MCP",
                }
            ]
        },
    )
    assert resources.find_gateway(aws) is None


def test_no_runtime_is_found_before_agentcore_deploy(aws, stub):
    stub("bedrock-agentcore-control").add_response(
        "list_agent_runtimes", {"agentRuntimes": []}
    )
    assert resources.find_runtime(aws, names.AGENT_RUNTIME) is None


def test_the_copilots_memory_is_found_unless_its_being_deleted(aws, stub):
    control = stub("bedrock-agentcore-control")
    control.add_response(
        "list_memories",
        {
            "memories": [
                MEMORY | {"id": f"{names.MEMORY}-old", "status": "DELETING"},
                MEMORY | {"id": "other_memory-1", "status": "ACTIVE"},
                MEMORY | {"id": f"{names.MEMORY}-new", "status": "ACTIVE"},
            ]
        },
    )
    control.add_response(
        "list_memories",
        {"memories": [MEMORY | {"id": f"{names.MEMORY}-old", "status": "DELETING"}]},
    )
    found = resources.find_memory(aws)
    assert found
    assert found["id"] == f"{names.MEMORY}-new"
    assert resources.find_memory(aws) is None


def test_a_functions_url_and_arn(aws, stub):
    lambda_ = stub("lambda")
    arn = f"arn:aws:lambda:us-east-1:{ACCOUNT}:function:{names.APP_FUNCTION}"
    lambda_.add_response(
        "get_function_url_config",
        {
            "FunctionUrl": "https://app.lambda-url.us-east-1.on.aws/",
            "FunctionArn": arn,
            "AuthType": "NONE",
            "CreationTime": "2026-11-18",
            "LastModifiedTime": "2026-11-18",
        },
        {"FunctionName": names.APP_FUNCTION},
    )
    lambda_.add_response(
        "get_function",
        {"Configuration": {"FunctionArn": arn}},
        {"FunctionName": names.APP_FUNCTION},
    )
    assert resources.function_url(aws, names.APP_FUNCTION) == (
        "https://app.lambda-url.us-east-1.on.aws"
    )
    assert resources.function_arn(aws, names.APP_FUNCTION) == arn


def test_the_gateways_credential_is_step_threes(aws, stub):
    stub("bedrock-agentcore-control").add_response(
        "get_api_key_credential_provider",
        {
            "name": names.KEY_PROVIDER,
            "credentialProviderArn": "arn:provider",
            "apiKeySecretArn": {"secretArn": "arn:secret"},
            "createdTime": "2026-11-18T00:00:00Z",
            "lastUpdatedTime": "2026-11-18T00:00:00Z",
        },
        {"name": names.KEY_PROVIDER},
    )
    assert resources.key_provider(aws)["name"] == names.KEY_PROVIDER
