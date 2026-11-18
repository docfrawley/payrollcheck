# Provisioning runbook

This stands PayrollCheck up on AWS AgentCore and Supabase from nothing. Work through it in order. Each step says what it needs before it starts, what to do, and what it leaves behind. The steps marked **by code** are commands, run from the root of the repo:

```
uv run --env-file .env -m deploy <step>
```

Each one creates what's missing and updates what's there, and prints `created`, `updated` or `unchanged` for everything it touches, so running it again changes nothing. No step prints a secret or writes one into the repo.

Only the user runs this runbook, or the coding agent when the user explicitly asks it to.

## Before you start

- [ ] **An AWS account**, with a budget and a billing alert in Billing and Cost Management.
- [ ] **An IAM user for the work**, `payrollcheck`, made by hand in the IAM console. Give it the policy in `deploy/operator_policy.json` as an inline policy, and create an access key for the command line.
- [ ] **The AWS CLI v2**, from AWS's installer. Run `aws configure` with the user's access key, in region `us-east-1`. `aws sts get-caller-identity` should show the `payrollcheck` user.
- [ ] **uv, Python 3.12 and Node 26**, as for `npm run dev`, with `uv sync` and `npm install` run.
- [ ] **A `.env` at the root of the repo** with `OPENROUTER_API_KEY`, `PAYROLLCHECK_API_KEY` and `REVIEWER_PASSWORD`, as `README.md` describes. The Supabase settings come in step 1.

## Step 1: Supabase

Needs: a Supabase account.

- [ ] **By hand: the project.** In Supabase's dashboard, create a project named `payrollcheck`, in the region nearest you. Give it a database password of letters and numbers only, and keep a copy, since Supabase won't show it again. The free plan allows two active projects: if the account has two already, pause one or choose a paid plan.
- [ ] **By hand: its settings, in `.env`.**
  - `DATABASE_URL`: under **Connect**, **Direct**, choose **Session pooler**, copy the connection string, and put the password in place of `[YOUR-PASSWORD]`. It ends `:5432/postgres`. The laptop and `npm run seed` use the session pooler; the runbook gives Lambda and Runtime the transaction pooler, port 6543, from it.
  - `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`: the project's URL and its publishable key, under **Project Settings**, **API Keys**.
  - `SUPABASE_SECRET_KEY`: the project's secret key, from the same page. Only this step uses it, to make the reviewers' users.
- [ ] **By code: `npm run seed`.** It makes the `payrollcheck` schema and loads the seed. Run it once now, and again before the smoke check.
- [ ] **By code: `uv run --env-file .env -m deploy supabase`.** It makes the three reviewers' users in the project's Auth, with the emails in `data/reviewers.json`, `REVIEWER_PASSWORD` and their emails confirmed. A user who's already there is left as they are. Making them by hand under **Authentication**, **Users** works just as well.
- [ ] **By hand: the Supabase MCP server.** The step prints the command that points Claude Code's read-only Supabase MCP server at the new project. If one is set up for an earlier project, remove it first with `claude mcp remove supabase`. Then run `/mcp` in Claude Code and choose Authenticate.

Leaves: the project with its schema, the seed and three Auth users; four settings in `.env`; the MCP server pointed at the project. `npm run dev` now uses the new project.
