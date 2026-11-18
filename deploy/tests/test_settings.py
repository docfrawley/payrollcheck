import pytest

from deploy import settings

HIDDEN = "sk-very-secret-value"


def test_a_missing_setting_is_named_and_no_value_is_shown(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", HIDDEN)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("REVIEWER_PASSWORD", raising=False)
    with pytest.raises(settings.MissingSettings) as missing:
        settings.required(
            "OPENROUTER_API_KEY", "SUPABASE_SECRET_KEY", "REVIEWER_PASSWORD"
        )
    assert str(missing.value) == "Add SUPABASE_SECRET_KEY, REVIEWER_PASSWORD to .env"
    assert HIDDEN not in str(missing.value)


def test_the_settings_a_step_needs_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", HIDDEN)
    assert settings.required("OPENROUTER_API_KEY") == {"OPENROUTER_API_KEY": HIDDEN}


def test_the_database_on_the_transaction_pooler():
    session = "postgresql://postgres.ref:pw@aws-0.pooler.supabase.com:5432/postgres"
    assert settings.pooled(session) == (
        "postgresql://postgres.ref:pw@aws-0.pooler.supabase.com:6543/postgres"
    )
    with pytest.raises(settings.MissingSettings, match="session pooler"):
        settings.pooled("postgresql://postgres@localhost/postgres")


def test_writing_agentcores_settings_keeps_the_rest_and_shows_no_value(
    tmp_path, capsys
):
    local = tmp_path / "agentcore" / ".env.local"
    local.parent.mkdir()
    local.write_text('KEPT="yes"\nAGENTCORE_CREDENTIAL_DATABASE_URL="old"\n')
    settings.write_local(
        {"AGENTCORE_CREDENTIAL_DATABASE_URL": HIDDEN, "PAYROLLCHECK_API": "https://x"},
        local,
    )
    assert local.read_text().splitlines() == [
        'KEPT="yes"',
        f'AGENTCORE_CREDENTIAL_DATABASE_URL="{HIDDEN}"',
        'PAYROLLCHECK_API="https://x"',
    ]
    assert local.stat().st_mode & 0o777 == 0o600
    shown = capsys.readouterr().out
    assert HIDDEN not in shown
    assert shown == (
        "AGENTCORE_CREDENTIAL_DATABASE_URL, PAYROLLCHECK_API in agentcore/.env.local:"
        " updated\n"
    )


def test_writing_the_same_settings_again_changes_nothing(tmp_path, capsys):
    local = tmp_path / "agentcore" / ".env.local"
    local.parent.mkdir()
    settings.write_local({"PAYROLLCHECK_API": "https://x"}, local)
    written = local.stat().st_mtime_ns
    settings.write_local({"PAYROLLCHECK_API": "https://x"}, local)
    assert local.stat().st_mtime_ns == written
    assert capsys.readouterr().out.splitlines() == [
        "PAYROLLCHECK_API in agentcore/.env.local: created",
        "PAYROLLCHECK_API in agentcore/.env.local: unchanged",
    ]


def test_a_new_settings_file_is_made(tmp_path):
    local = tmp_path / "agentcore" / ".env.local"
    local.parent.mkdir()
    settings.write_local({"PAYROLLCHECK_API": "https://x"}, local)
    assert local.read_text() == 'PAYROLLCHECK_API="https://x"\n'


def test_a_value_that_cant_be_written_as_it_is_is_refused(tmp_path):
    local = tmp_path / ".env.local"
    with pytest.raises(ValueError, match="PAYROLLCHECK_API"):
        settings.write_local({"PAYROLLCHECK_API": 'a"b'}, local)
    assert not local.exists()
