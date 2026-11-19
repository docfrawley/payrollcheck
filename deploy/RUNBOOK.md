# Provisioning runbook

This stands PayrollCheck up on AWS AgentCore and Supabase from nothing. Work through it in order. Each step says what it needs before it starts, what to do, and what it leaves behind. The steps marked **by code** are commands, run from the root of the repo:

```
uv run --env-file .env -m deploy <step>
```

Each one creates what's missing and updates what's there, and prints `created`, `updated` or `unchanged` for everything it touches, so running it again changes nothing. No step prints a secret or writes one into the repo.

Only the user runs this runbook, or the coding agent when the user explicitly asks it to.

## Before you start

- [ ] **An AWS account**, with a budget and a billing alert in Billing and Cost Management.
- [ ] **An IAM user for the work**, made by hand in the IAM console:
  1. **Policies → Create policy**, in the JSON editor, with the whole of `deploy/operator_policy.json`, named `payrollcheck-operator`. It's a customer managed policy, since it's longer than IAM allows an inline one.
  2. **Users → Create user**, `payrollcheck`, with no console access, and `payrollcheck-operator` attached directly.
  3. On the user's **Security credentials**, **Create access key** for the **Command Line Interface (CLI)**. Copy both halves; AWS shows the secret once.
- [ ] **The AWS CLI v2**, from AWS's installer, or `brew install awscli` on a Mac. Run `aws configure --profile payrollcheck` with the user's access key, in region `us-east-1`, and add `AWS_PROFILE=payrollcheck` to `.env`, so the runbook uses this profile and any other project keeps its own. `aws sts get-caller-identity --profile payrollcheck` should show the `payrollcheck` user.
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

Needs: step 1's settings in `.env`, with `PAYROLLCHECK_API_KEY` and `OPENROUTER_API_KEY`; the AWS CLI profile.

- [ ] **By code: `uv run --env-file .env -m deploy lambda`.** It builds the dashboard with `npm run build`, packages the app (`backend/`, `data/`, `context/__init__.py` with `context/filing_dates.py`, and `dashboard/dist/`, with the `server` group's packages for Lambda's Linux and Python 3.12) and the context layer (`context/`, with the `context` group's), and deploys each:
  - It needs `VITE_SUPABASE_PUBLISHABLE_KEY` as well, which the build bakes into the dashboard.
  - `payrollcheck-app`: the backend and the dashboard, `backend.main.handler`, 30 seconds and 1024 MB, behind a **public** Function URL. Its environment is the database on Supabase's transaction pooler (port 6543), `VITE_SUPABASE_URL`, `PAYROLLCHECK_API_KEY` and `OPENROUTER_API_KEY`, which the judge grades an evaluation's notices with, and from step 7 the two runtimes' ARNs, which a later run of this step keeps.
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

## Step 6: the Copilot's Memory

Needs: the AWS CLI profile.

- [ ] **By code: `uv run --env-file .env -m deploy memory`.** It makes `payrollcheck_copilot_memory`, which takes about two and a half minutes. Its two strategies turn each conversation into notes under the reviewer's own namespace: **User Preference** on `/reviewers/{actorId}/preferences/`, how the reviewer likes to work, and **Semantic** on `/reviewers/{actorId}/facts/`, the facts they mention. Events are kept 7 days. The payroll agent keeps no memory, so it has none.

Leaves: the Memory, with its id printed. It comes before the runtimes, since `agentcore deploy` reads its id.

## Step 7: the two Runtimes

Needs: steps 2 to 6; the AgentCore CLI, `npm install -g @aws/agentcore@1.0.0-rc.5` (with `sudo` on a Mac whose npm folder belongs to root), so that `agentcore --version` says 1.0.0-rc.5.

- [ ] **By code: `uv run --env-file .env -m deploy runtimes`.** It takes about 10 minutes the first time.
  1. It writes the app's address (`PAYROLLCHECK_API`), the Gateway's (`PAYROLLCHECK_GATEWAY_URL`) and the Memory's id (`PAYROLLCHECK_COPILOT_MEMORY_ID`) into `agentcore/.env.local`, beside step 3's credentials.
  2. It installs the CDK project's packages (`npm ci --prefix agentcore/cdk`) and runs `agentcore deploy`. The first deploy in an account makes the CDK bootstrap, `CDKToolkit` (an S3 bucket, a KMS key at about $1 a month and five roles), and the deploy's `default` target, from the AWS CLI profile's account and region. Then it makes the three credentials in AgentCore Identity and the stack `AgentCore-payrollcheck-default`, with the runtimes `payrollcheck_default_agent` and `payrollcheck_default_copilot` on platform version V2 and their roles, which may call the Gateway (`runtime/policy.json`) and, for the Copilot, use its Memory (`runtime/copilot_policy.json`).
  3. It lets the app's role invoke both runtimes, and nothing else on Runtime, and sets `PAYROLLCHECK_AGENT_RUNTIME` and `PAYROLLCHECK_COPILOT_RUNTIME` on the app's function, so it sends the agent's work and the Copilot's turns there.
  4. It runs step 5 again, so the permits name both runtimes' roles: the agent's may call all twelve tools, the Copilot's the five context tools.
  5. It sends each runtime a health check in a new session, which gets ready (fetching its credentials and opening its pool) before it answers `{'healthy': True}`.

Leaves: both runtimes, the app pointed at them, and the Policy naming their roles.

## What the runbook made

- [ ] **By code: `uv run --env-file .env -m deploy show`.** It lists everything named for PayrollCheck: the stack and the runtimes with their ARNs, the Gateway with its URL and targets, the policy engine and its permits, the credential provider, the Memory's id, the functions with their URLs and log groups, and the roles.

## A second run changes nothing

- [ ] **By code:** run steps 2 to 7 again, in order. Every resource says `unchanged`, the app's function keeps its `CodeSha256` and `LastModified`, each runtime keeps its `agentRuntimeVersion`, and `show` prints the same.

## The smoke check

Needs: steps 1 to 7.

- [ ] **By hand: OpenRouter's reading.** Note the key's usage on openrouter.ai, under Settings, Keys, to report what the check spent.
- [ ] **By code: `npm run seed`.** The week-12 wave is back in the queue as Received, PC-1214 and PC-1223 are missing for an upload, the business date is Nov 23, 2026, and the Copilot has no conversations, as `data/copilot_expected.json` describes.
- [ ] **By hand: sign in.** Open the app's URL, from step 2 or `show`, and sign in as Marcus Oyelaran (`marcus.oyelaran@payrollcheck.example`, `REVIEWER_PASSWORD`). The header shows the business date, Nov 23, 2026.
- [ ] **By hand: the Copilot, before any dispatch.** In the sidebar, ask: "How much underpayment have we flagged for Garden State Electric this month?" and wait for the answer. It comes from the Copilot's Runtime, with its Memory on.
- [ ] **By code: `uv run --env-file .env -m deploy smoke copilot`.** It reads Marcus's latest answer from the app's records and checks it names PC-1009 and $198.75, question 2's case id and total, and that the Copilot's Memory holds the conversation's events.
- [ ] **By hand: the two missing payrolls.** As Marcus, on the municipal building's project page, choose Delaware Valley Masonry LLC as the subcontractor, since the list starts on the first one, and upload `data/development/arrivals/PC-1214-1.csv`; it says "Uploaded as PC-1214, Received". Then sign in as Dana Whitfield and, on the road resurfacing's page, which isn't Marcus's, choose Meadowlands Site Services LLC and upload `data/development/arrivals/PC-1223-1.csv`; it says "Uploaded as PC-1223". The queue holds the 24 cases of the week-12 wave as Received.
- [ ] **By hand: the dispatch.** As Marcus, on the queue page, start a dispatch with 5 payroll agents at once. It works on the payroll agent's Runtime, through the Gateway. When it finishes, all 24 cases are Awaiting review; the panel shows Marcus his cases with their cost and time, and the count of the others; a case's steps name its tools as the Gateway does, such as `payrollcheck-app___get_case` and `payrollcheck-context___get_wage_rate`.
- [ ] **By code, with the dashboard closed: `uv run --env-file .env -m deploy smoke policy`.** Signed with your AWS identity, through the Gateway, `payrollcheck-context___get_filing_rules` answers and the context layer's logs show it, and `payrollcheck-app___get_case`, which isn't on your allowlist, is refused by the Policy's default deny, which the Gateway words as not allowed due to policy enforcement, and the app's logs show no invocation over the probe. It waits a minute for Lambda to deliver the logs.
- [ ] **By code, a few minutes later: `uv run --env-file .env -m deploy smoke decisions`.** The policy engine's counts in CloudWatch: `AllowDecisions` for the dispatch's calls and the allowed probe, and `DenyDecisions` for the refused one.
- [ ] **By hand: what it spent.** The dispatch's cost on its panel and the Copilot's turn from the app's records, the OpenRouter key's usage against the reading before, and AWS's figures in Billing and Cost Management a day later.

## The teardown

Only when you want PayrollCheck off AWS.

- [ ] **By code: `uv run --env-file .env -m deploy teardown`.** It lists what it would delete: everything named and tagged for PayrollCheck, and anything named for it without the tag, which it leaves.
- [ ] **By code: `uv run --env-file .env -m deploy teardown --yes`.** It deletes them in the order AWS needs: the stack with both runtimes and the three credentials `agentcore deploy` made, as Ed's teardown did, with `agentcore remove all --yes` and then `agentcore deploy --yes`, putting `agentcore/agentcore.json` back from git afterwards, which discards any edit to it you haven't committed; the Gateway after its targets, the policy engine after its permits, the credential provider, the Memory, the two functions with their log groups, and the three roles. It leaves, and says how to remove by hand:
  - the runtimes' own log groups under `/aws/bedrock-agentcore/runtimes/`, which Runtime made
  - the CDK bootstrap, `CDKToolkit` and its `cdk-*` bucket, which every AgentCore project in the account shares
  - `agentcore/.env.local`, and the CLI's own state in `agentcore/.cli/` and `agentcore/aws-targets.json`
  - the Supabase project
