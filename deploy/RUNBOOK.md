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

## Step 2: Lambda

Needs: step 1's settings in `.env`, with `PAYROLLCHECK_API_KEY`; the AWS CLI profile.

- [ ] **By code: `uv run --env-file .env -m deploy lambda`.** It builds the dashboard with `npm run build`, packages the app (`backend/`, `data/` and `dashboard/dist/`, with the `server` group's packages for Lambda's Linux and Python 3.12) and the context layer (`context/`, with the `context` group's), and deploys each:
  - It needs `VITE_SUPABASE_PUBLISHABLE_KEY` as well, which the build bakes into the dashboard.
  - `payrollcheck-app`: the backend and the dashboard, `backend.main.handler`, 30 seconds and 1024 MB, behind a **public** Function URL. Its environment is the database on Supabase's transaction pooler (port 6543), `VITE_SUPABASE_URL` and `PAYROLLCHECK_API_KEY`, and from step 7 the two runtimes' ARNs, which a later run of this step keeps.
  - `payrollcheck-context`: the context layer, `context.server.handler`, 30 seconds and 512 MB, behind a Function URL with **`AWS_IAM`** auth, so only callers allowed to invoke it, the Gateway among them, can reach it.
  - Each has its log group, `/aws/lambda/<function>`, kept for 7 days, and its role, `<function>-role`, which may write to that log group and do nothing else.

  The zips are the same bytes for the same code, so a run updates a function's code only when it changed, and its settings only when they changed.

Leaves: the two functions and their URLs, printed. Open the app's URL to see the dashboard's sign-in page.

## Step 3: Identity

Needs: `OPENROUTER_API_KEY`, `PAYROLLCHECK_API_KEY` and `DATABASE_URL` in `.env`; the AWS CLI profile.

- [ ] **By code: `uv run --env-file .env -m deploy identity`.** It puts:
  - the agent's API key in AgentCore Identity as the API key credential provider `payrollcheck-app-key`, which the Gateway sends to the app as `X-API-Key`. A later run reads the key the provider holds, without showing it, and sends `.env`'s only when it differs.
  - the values of the runtimes' three credentials, the ones `agentcore/agentcore.json` declares (`OPENROUTER_API_KEY`, `PAYROLLCHECK_API_KEY` and `DATABASE_URL` on the transaction pooler), in `agentcore/.env.local` as `AGENTCORE_CREDENTIAL_<NAME>`. Git ignores the file, and only you can read it. `agentcore deploy` makes the three credentials from it in step 7.

Leaves: the key provider; the credentials' values in `agentcore/.env.local`.

## Step 4: the Gateway

Needs: steps 2 and 3; `PAYROLLCHECK_API_KEY` in `.env`.

- [ ] **By code: `uv run --env-file .env -m deploy gateway`.** It makes:
  - the Gateway's role, `payrollcheck-gateway-role`, which only AgentCore may run as, for our Gateway alone. It may fetch the agent's key from AgentCore Identity and invoke the context layer, and nothing else.
  - the Gateway, `payrollcheck-gateway`: MCP, with `AWS_IAM` auth, so every caller signs its requests. A new role can take a minute to reach AgentCore, and the step waits.
  - its two targets, named as `agent/routes.py` names them:
    - `payrollcheck-app`: the payroll agent's own API document, read from the deployed app's `/api/agent/openapi.json` with the app's URL as its server. The Gateway sends the agent's key with every call as `X-API-Key`.
    - `payrollcheck-context`: the context layer's MCP endpoint, `<its URL>/mcp`, which the Gateway's role signs for Lambda.

  A target that's the same is left alone; one that differs is updated.

Leaves: the Gateway, with its URL printed, and its two targets. Each tool on it is named `<target>___<tool>`, such as `payrollcheck-app___get_case`.

## Step 5: the Policy

Needs: step 4.

- [ ] **By code: `uv run --env-file .env -m deploy policy`.** It makes the policy engine `payrollcheck_policy_engine`, lets the Gateway's role ask it about every call, and enforces it on the Gateway (`ENFORCE`). Then it puts the allowlist: one permit for each tool the payroll agent's work needs, naming who may call it. Nothing is forbidden, and anything without a permit is denied by default. There's no payment cap, since PayrollCheck has no payments.

  | Tool | Who may call it |
  |---|---|
  | `payrollcheck-app___get_case`, `___get_project`, `___list_subcontractors`, `___get_payroll_history`, `___record_check_findings`, `___record_screening_flag`, `___record_exception_report` | the payroll agent's runtime role |
  | `payrollcheck-context___get_wage_rate`, `___check_registration`, `___check_apprentice`, `___get_filing_rules`, `___lookup_payroll_term` | the payroll agent's runtime role, the Copilot's runtime role, and you, the operator |

  The people's actions, sign off, send back and override, aren't in the agent's API document, so they aren't on the Gateway at all. The backend refuses them to the agent's key whatever reaches it.

  Before step 7, the runtimes aren't there, so the step writes only the context tools' permits, for you. Step 7 runs this step again, and the permits then name both runtimes' roles. A permit that's the same is left alone; one that differs is updated.

Leaves: the engine, enforced on the Gateway, and the permits. Calls signed with your own AWS identity reach the context layer's tools and are refused the app's, so on the laptop the payroll agent uses the direct route.
