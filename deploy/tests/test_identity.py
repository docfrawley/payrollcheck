import json

from deploy import identity, names, settings

KEY = "the-agents-api-key"
PROVIDER = {
    "name": names.KEY_PROVIDER,
    "credentialProviderArn": (
        "arn:aws:bedrock-agentcore:us-east-1:1:token-vault/default/"
        "apikeycredentialprovider/payrollcheck-app-key"
    ),
    "apiKeySecretArn": {"secretArn": "arn:aws:secretsmanager:us-east-1:1:secret:x"},
    "createdTime": "2026-11-18T00:00:00Z",
    "lastUpdatedTime": "2026-11-18T00:00:00Z",
}


def listed(*provider_names):
    return {
        "credentialProviders": [
            {
                "name": name,
                "credentialProviderArn": PROVIDER["credentialProviderArn"],
                "createdTime": "2026-11-18T00:00:00Z",
                "lastUpdatedTime": "2026-11-18T00:00:00Z",
            }
            for name in provider_names
        ]
    }


def provider_with(key):
    """The provider, holding a key in its secret under its JSON key."""
    return PROVIDER | {"apiKeySecretJsonKey": "api_key_value"}, {
        "ARN": PROVIDER["apiKeySecretArn"]["secretArn"],
        "Name": "bedrock-agentcore-identity!default/apikey/payrollcheck-app-key",
        "SecretString": json.dumps({"api_key_value": key}),
    }


def test_the_gateways_credential_is_made_tagged(aws, stub, capsys):
    control = stub("bedrock-agentcore-control")
    control.add_response("list_api_key_credential_providers", listed("other"))
    control.add_response(
        "create_api_key_credential_provider",
        {
            "name": names.KEY_PROVIDER,
            "credentialProviderArn": PROVIDER["credentialProviderArn"],
            "apiKeySecretArn": PROVIDER["apiKeySecretArn"],
        },
        {"name": names.KEY_PROVIDER, "apiKey": KEY, "tags": names.TAGS},
    )
    control.add_response(
        "get_api_key_credential_provider", PROVIDER, {"name": names.KEY_PROVIDER}
    )
    assert identity.put_key_provider(aws, KEY)["name"] == names.KEY_PROVIDER
    assert capsys.readouterr().out == (
        f"Credential provider {names.KEY_PROVIDER}: created\n"
    )


def test_a_credential_holding_the_key_is_left_alone(aws, stub, capsys):
    control = stub("bedrock-agentcore-control")
    provider, secret = provider_with(KEY)
    control.add_response(
        "list_api_key_credential_providers", listed(names.KEY_PROVIDER)
    )
    control.add_response(
        "get_api_key_credential_provider", provider, {"name": names.KEY_PROVIDER}
    )
    stub("secretsmanager").add_response(
        "get_secret_value", secret, {"SecretId": secret["ARN"]}
    )
    assert identity.put_key_provider(aws, KEY) == provider
    shown = capsys.readouterr().out
    assert shown == f"Credential provider {names.KEY_PROVIDER}: unchanged\n"


def test_a_credential_holding_another_key_is_given_this_one(aws, stub, capsys):
    control = stub("bedrock-agentcore-control")
    provider, secret = provider_with("an-old-key")
    control.add_response(
        "list_api_key_credential_providers", listed(names.KEY_PROVIDER)
    )
    control.add_response("get_api_key_credential_provider", provider)
    stub("secretsmanager").add_response("get_secret_value", secret)
    control.add_response(
        "update_api_key_credential_provider",
        {
            "credentialProviderArn": PROVIDER["credentialProviderArn"],
            "apiKeySecretArn": PROVIDER["apiKeySecretArn"],
            "name": names.KEY_PROVIDER,
            "createdTime": "2026-11-18T00:00:00Z",
            "lastUpdatedTime": "2026-11-18T00:00:00Z",
        },
        {"name": names.KEY_PROVIDER, "apiKey": KEY},
    )
    control.add_response(
        "get_api_key_credential_provider", provider, {"name": names.KEY_PROVIDER}
    )
    identity.put_key_provider(aws, KEY)
    shown = capsys.readouterr().out
    assert shown == f"Credential provider {names.KEY_PROVIDER}: updated\n"
    assert KEY not in shown


def test_the_runtimes_credentials_are_agentcore_jsons_three(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("PAYROLLCHECK_API_KEY", KEY)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://postgres.ref:pw@pooler.supabase.com:5432/postgres"
    )
    assert identity.runtime_credentials() == {
        "AGENTCORE_CREDENTIAL_OPENROUTER_API_KEY": "or-key",
        "AGENTCORE_CREDENTIAL_PAYROLLCHECK_API_KEY": KEY,
        "AGENTCORE_CREDENTIAL_DATABASE_URL": (
            "postgresql://postgres.ref:pw@pooler.supabase.com:6543/postgres"
        ),
    }


def test_the_step_puts_the_key_and_writes_the_credentials(aws, monkeypatch):
    monkeypatch.setenv("PAYROLLCHECK_API_KEY", KEY)
    sent: list[str] = []
    written: list[dict[str, str]] = []
    monkeypatch.setattr(identity, "put_key_provider", lambda _, key: sent.append(key))
    monkeypatch.setattr(identity, "runtime_credentials", lambda: {"A": "b"})
    monkeypatch.setattr(settings, "write_local", written.append)
    identity.run(aws)
    assert sent == [KEY]
    assert written == [{"A": "b"}]
