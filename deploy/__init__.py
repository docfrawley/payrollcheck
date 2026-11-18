"""The provisioning runbook: the steps that stand PayrollCheck up on AWS AgentCore
and Supabase from nothing, each creating what's missing and updating what's there,
run by the user with uv run --env-file .env -m deploy <step>. Its checklist is
deploy/RUNBOOK.md."""
