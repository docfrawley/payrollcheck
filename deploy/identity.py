"""Step 3, AgentCore Identity: the agent's API key as the credential the Gateway sends
to the app, and the values of the runtimes' three credentials in agentcore/.env.local,
which agentcore deploy reads to make them."""

import json
from typing import Any

from agent import identity as agent_identity
from deploy import names, settings
from deploy.aws import Aws

AGENTCORE_PROJECT = settings.REPO / "agentcore" / "agentcore.json"


def stored_key(aws: Aws, provider: dict[str, Any]) -> str:
    """The key a provider holds, from its secret in Secrets Manager."""
    secret = aws.client("secretsmanager").get_secret_value(
        SecretId=provider["apiKeySecretArn"]["secretArn"]
    )["SecretString"]
    json_key = provider.get("apiKeySecretJsonKey")
    return json.loads(secret)[json_key] if json_key else secret


def put_key_provider(aws: Aws, api_key: str) -> dict[str, Any]:
    """The app's API key in AgentCore Identity, for the Gateway to send: created,
    given the key when it holds another, or left alone. Returns the provider."""
    control = aws.client("bedrock-agentcore-control")
    pages = control.get_paginator("list_api_key_credential_providers").paginate()
    there = {p["name"] for page in pages for p in page["credentialProviders"]}
    if names.KEY_PROVIDER in there:
        provider = control.get_api_key_credential_provider(name=names.KEY_PROVIDER)
        if stored_key(aws, provider) == api_key:
            print(f"Credential provider {names.KEY_PROVIDER}: unchanged")
            return provider
        control.update_api_key_credential_provider(
            name=names.KEY_PROVIDER, apiKey=api_key
        )
        print(f"Credential provider {names.KEY_PROVIDER}: updated")
    else:
        control.create_api_key_credential_provider(
            name=names.KEY_PROVIDER, apiKey=api_key, tags=names.TAGS
        )
        print(f"Credential provider {names.KEY_PROVIDER}: created")
    return control.get_api_key_credential_provider(name=names.KEY_PROVIDER)


def runtime_credentials() -> dict[str, str]:
    """The values of the credentials agentcore/agentcore.json declares, each from the
    setting of its name, with the database on the transaction pooler, under the
    names agentcore deploy reads them by."""
    declared = [
        c["name"] for c in json.loads(AGENTCORE_PROJECT.read_text())["credentials"]
    ]
    found = settings.required(*declared)
    found[settings.DATABASE_URL] = settings.pooled(found[settings.DATABASE_URL])
    return {f"{agent_identity.PREFIX}{name}": found[name] for name in declared}


def run(aws: Aws) -> None:
    """Step 3: the Gateway's credential, and the runtimes' credentials' values."""
    api_key = settings.required(settings.API_KEY)[settings.API_KEY]
    put_key_provider(aws, api_key)
    settings.write_local(runtime_credentials())
