# Plan: stage 7, PayrollCheck on AWS AgentCore

From `docs/stages/07_DEPLOY.md`. After stage 6, PayrollCheck works end to end on the laptop on the direct route, and the code already runs on Lambda and AgentCore Runtime when each piece's setting is there. Nothing exists on AWS for PayrollCheck, and there's no PayrollCheck project in our Supabase account. Ed's code assumes resources his lab notebooks made by hand, one notebook at a time. This stage ports those steps into one scripted, re-runnable runbook that stands PayrollCheck up from nothing. It replaces UnderCover's $1,000 payment cap with an allowlist Policy, runs a smoke check on the deployed product, and then deletes `labs/`, Ed's notebooks, which his import commit `ecca35dd` keeps.

Writing the runbook creates nothing. Only running it does, and only when the user says so (`AGENTS.md`).

The work happens on a branch, `stage-7-deploy`, cut from `main` at `4ddd6f2`, with a commit at the end of every phase.

## The baseline: `npm run check` before the stage

On `main` at `4ddd6f2`, the stage 6 merge: pytest passes about 1,380 at 99% coverage, vitest 218, and Playwright 41, with ruff, pyright, ESLint, Prettier and tsc clean and the three import checks passing. Run again at the start of phase 1 with `.env` moved aside: pytest 1,396 at 99%, vitest 218 at 98.5% of lines, Playwright 41, everything else clean.

Every phase ends with `npm run check` green and coverage of at least 80%. No file is excluded from coverage, and no threshold or rule is lowered (`docs/ROADMAP.md`'s test rule).

## What Ed's code relies on

I read the notebooks the brief names without running them: Part 1 of `week2day3`, Parts 1 to 4 of `week3day2_lab2`, Parts 1 to 6 of `week3day3`, Parts 1 to 6 of `week3day4_lab2` and Parts 1 to 5 of `week3day5_lab1`. I also read `ecca35dd:labs/week3day4_aws.py`, and `ecca35dd:labs/week3day4_lab1.ipynb` for the AgentCore CLI and the CDK bootstrap, which the later labs take for granted. This is everything they make or read, by its PayrollCheck name.

### Before the runbook

| What | Ed's | PayrollCheck's | Made by |
|---|---|---|---|
| An AWS account, with a budget alert | Day 1 | the same | the user, by hand |
| An IAM user for the work, and its access key in the AWS CLI profile | `undercover`, with `ecca35dd:labs/undercover-course-policy.json` | `payrollcheck`, with `deploy/operator_policy.json`, the course policy renamed | the user, in the AWS console, then `aws configure` (region `us-east-1`) |
| The AWS CLI v2, and the AgentCore CLI at a pinned version | `@aws/agentcore@1.0.0-rc.5` | the same pin, checked against `agentcore/cdk`'s `@aws/agentcore-cdk` in phase 4 | the user, `npm install -g` |
| The CDK project's packages | `npm ci --prefix agentcore/cdk` | the same | the runtimes step |
| The CDK bootstrap, `CDKToolkit`: an S3 bucket, a KMS key at $1 a month and five roles | the first `agentcore deploy` | the same | `agentcore deploy`, the first time |

### The resources

| Step | Resource | Name | Notes |
|---|---|---|---|
| 1 Supabase | project | `payrollcheck` | made by hand in the dashboard; database password of letters and numbers |
| 1 | schema and seed | the `payrollcheck` schema | `npm run seed` |
| 1 | three Auth users | the emails in `data/reviewers.json` | password `REVIEWER_PASSWORD`, email confirmed |
| 2 Lambda | log groups | `/aws/lambda/payrollcheck-app`, `/aws/lambda/payrollcheck-context` | 7-day retention |
| 2 | roles | `payrollcheck-app-role`, `payrollcheck-context-role` | Lambda trust; logging only, plus `payrollcheck-app-runtime` in step 7 |
| 2 | functions | `payrollcheck-app` (Python 3.12, `backend.main.handler`, 30 s, 1024 MB), `payrollcheck-context` (`context.server.handler`, 30 s, 512 MB) | zips as `docs/TECH_STACK.md` describes |
| 2 | Function URLs | the app's public (`NONE`, with the two public permissions); the context layer's `AWS_IAM` | |
| 3 Identity | API key provider | `payrollcheck-app-key` | the agent's key, which the Gateway sends as `X-API-Key` |
| 3 | runtime credentials | `OPENROUTER_API_KEY`, `PAYROLLCHECK_API_KEY`, `DATABASE_URL` | values in `agentcore/.env.local`; `agentcore deploy` makes them |
| 4 Gateway | role | `payrollcheck-gateway-role` | trust in `bedrock-agentcore` for `gateway/payrollcheck-gateway-*`; inline `-api-key` and `-context` policies |
| 4 | Gateway | `payrollcheck-gateway` | MCP, `AWS_IAM`, `exceptionLevel` `DEBUG` |
| 4 | targets | `payrollcheck-app` (the agent's API document, with the app's URL as its server), `payrollcheck-context` (`<context URL>/mcp`, the Gateway's role signing for Lambda) | the names `agent/routes.py` gives |
| 5 Policy | policy engine | `payrollcheck_policy_engine` | the role's `-policy-engine` permission; attached in `ENFORCE` |
| 5 | policies | one permit per tool, `payrollcheck_allow_<target>_<tool>` | no forbid; Ed's `payment_limit` isn't ported |
| 6 Memory | the Copilot's Memory | `payrollcheck_copilot_memory` | User Preference on `/reviewers/{actorId}/preferences/`, Semantic on `/reviewers/{actorId}/facts/`, 7-day events |
| 7 Runtimes | stack | `AgentCore-payrollcheck-default` | two runtimes, `payrollcheck_default_agent` and `payrollcheck_default_copilot`, on V2, with their roles (`runtime/policy.json`, `runtime/copilot_policy.json`) |
| 7 | the app's permission to invoke both | `payrollcheck-app-runtime` on `payrollcheck-app-role` | both ARNs and their `runtime-endpoint/*` |

Ed's agent Memory (`undercover_memory`, `create_memory`) isn't ported, since agent memory went in stage 3, and nor are his course budget monitor, his Render guides or his teaching cells.

### The settings

| Setting | Where | From |
|---|---|---|
| `DATABASE_URL` | `.env` | Supabase's session pooler, port 5432, for the laptop and `npm run seed` |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` | `.env` | the new project; `npm run build` bakes them into the dashboard |
| `SUPABASE_SECRET_KEY` | `.env` | **new**, the project's secret key, used only by step 1 to make the Auth users. It never leaves the laptop |
| `REVIEWER_PASSWORD`, `OPENROUTER_API_KEY`, `PAYROLLCHECK_API_KEY` | `.env` | as now |
| the function's environment | `payrollcheck-app` | `DATABASE_URL` on the transaction pooler (port 6543, `":5432/"` replaced with `":6543/"` as Ed did), `VITE_SUPABASE_URL`, `PAYROLLCHECK_API_KEY`, and from step 7 `PAYROLLCHECK_AGENT_RUNTIME` and `PAYROLLCHECK_COPILOT_RUNTIME` |
| `AGENTCORE_CREDENTIAL_OPENROUTER_API_KEY`, `..._PAYROLLCHECK_API_KEY`, `..._DATABASE_URL` | `agentcore/.env.local` (git ignores it) | `.env`, the database on the transaction pooler |
| `PAYROLLCHECK_API`, `PAYROLLCHECK_GATEWAY_URL`, `PAYROLLCHECK_COPILOT_MEMORY_ID` | `agentcore/.env.local` | the app's URL, the Gateway's URL and the Memory's id |
| the Supabase MCP server | Claude Code | `claude mcp add --transport http supabase "https://mcp.supabase.com/mcp?project_ref=<ref>&read_only=true"`, printed by step 1 |

## Decisions

### Taken with the user while planning

1. **The allowlist names its callers.** The agent's work needs every tool the Gateway has: all seven operations in its API document (`backend/agent_api.py`'s `OPERATIONS`, each called on its route from `agent/tools.py`, `agent/check_inputs.py` and `agent/harness.py`) and all five context tools. So an allowlist of exactly those tools leaves nothing on the Gateway for the smoke check to be refused. **Agreed:** each tool gets one permit naming who may call it:
   - **The agent's runtime role** may call all 12 tools.
   - **The Copilot's runtime role** may call the five context tools only.
   - **The AWS identity that runs the runbook**, the operator, may also call the five context tools only.

   The smoke check signs with the operator's identity, as the agent's Gateway route signs on the laptop. It calls an app tool and is refused by the Policy's default deny, and the app's logs show nothing arrived. This also closes the known gap where the Copilot's role could reach the app's tools.

   **The cost:** the payroll agent on the laptop's Gateway route keeps only the context tools, so on the laptop it uses the direct route. The documents say so.

### Choices this plan makes, for your review

2. **The runbook lives in `deploy/`**, a Python package beside `backend/` and `agent/`:
   - **The checklist:** `deploy/RUNBOOK.md`, with every step, by hand or by code.
   - **The steps:** one command each, `uv run --env-file .env -m deploy <step>`.
   - **Its tests:** in `deploy/tests/`.

   `deploy` joins pytest's `testpaths`, coverage's `source`, ruff's `include` and pyright's, so its ordinary code is tested with nothing excluded. It runs in the project's own environment, which already has boto3, httpx and the MCP client, so it needs no dependency group of its own. A folder of its own keeps it apart from the product: nothing in `backend/`, `agent/` or `context/` imports it.
3. **The steps run in this order, which moves the Memory before the Runtimes:** Supabase, Lambda, Identity, the Gateway, the Policy, **the Memory, then the Runtimes**. The brief lists the Memory last, but `agentcore deploy` reads the Memory's id from `agentcore/.env.local`. Making it first saves a second 10-minute deploy, and it's the order of Ed's `week3day5_lab1` (Part 3 before Part 4). The checklist keeps the brief's names for each step.
4. **The Policy's permits are written twice.** The Policy step writes them for the callers that exist then: the operator. The Runtimes step ends by running the Policy step's code again, so the permits name both runtimes' roles. Each permit is compared with what's there and updated only when it differs.
5. **Re-runnable means a second run changes nothing,** with each step printing `created`, `updated` or `unchanged` for every resource. Ed's code re-uploaded the code and re-put the targets on every run, which would change things. So:
   - **The zips are byte-for-byte repeatable:** sorted entries with a fixed timestamp. The function's code is updated only when its SHA-256 differs from Lambda's `CodeSha256`, and its configuration only when it differs.
   - **The other resources** are updated only when what's there differs: a target, the Gateway's policy engine and a policy.
   - **Some calls change nothing when repeated:** an IAM policy put again with the same document, and `agentcore deploy` with no changes.
   - **The function's environment keeps the runtimes' ARNs** when the Lambda step runs again after the Runtimes step.
6. **Ed's waits and retries are kept, in one module**, `deploy/waits.py`, rather than copied into each step:
   - waiting while an AgentCore resource is `CREATING`, `UPDATING` or `SYNCHRONIZING`
   - retrying a new role until Lambda can use it (`InvalidParameterValueException`, every 3 s, 10 tries)
   - retrying a new role until AgentCore can use it (a `ValidationException` naming the role, every 3 s, 10 tries)
   - retrying a target while the Gateway's role can't be used yet (every 10 s, 20 tries)
   - retrying the policy engine's attachment until the role's `GetPolicyEngine` permission arrives (every 5 s, 20 tries)
   - retrying the agent's API document from a new function (every 3 s, 5 tries)
   - waiting for the Memory to leave `CREATING` (every 10 s)
7. **What's done by hand.** These steps need the user:
   - creating the Supabase project, a choice of plan and region in Supabase's dashboard
   - copying its settings into `.env`
   - the IAM user and `aws configure`
   - installing the two CLIs
   - signing in on the deployed dashboard for the smoke check

   Everything else is code. **Seeding** is a checklist line, `npm run seed`, rather than part of the Supabase step, since seeding rebuilds the database and would break "a second run changes nothing". The smoke check starts with it.
8. **The Auth users are made by code,** with Supabase Auth's admin API (`/auth/v1/admin/users`) and `SUPABASE_SECRET_KEY`, which is why that key goes in `.env`. A user who is missing is made with `REVIEWER_PASSWORD` and their email confirmed. A user who's already there is left alone, so a run never changes a password. Doing it by hand in Supabase's dashboard works just as well, and the checklist says so.
9. **The runbook includes a teardown**, `uv run --env-file .env -m deploy teardown --yes`. It runs only when the user runs it, and without `--yes` it only lists what it would delete. It deletes only resources whose name starts `payrollcheck` and whose tags include `project=payrollcheck`, both checked on each one:
   - the stack `AgentCore-payrollcheck-default`, through CloudFormation
   - the Gateway with its targets
   - the policy engine with its policies
   - the key provider
   - the Memory
   - the two functions with their log groups and roles
   - the Gateway's role

   **Amended in phase 4's review:** the stack goes as Ed's did, through the CLI (`agentcore remove all --yes`, then `agentcore deploy --yes`, then `agentcore/agentcore.json` put back from git), since that also deletes the three credentials `agentcore deploy` made in AgentCore Identity, with their secrets, which deleting the stack alone would leave. It leaves the CDK bootstrap, which isn't tagged for PayrollCheck, and the Supabase project, and prints how to remove each by hand. Ed's `delete_bootstrap` is ported only as those printed instructions. **Amended in phase 1:** the runtimes' own log groups under `/aws/bedrock-agentcore/`, which Runtime makes and the runbook doesn't tag, are left too, and listed.
10. **The smoke check asks the Copilot before the dispatch.** `docs/PROCESS.md` says the Copilot's live checks come after one `npm run seed` and before any dispatch, since `data/copilot_expected.json` describes that state. So the order is: seed, the Copilot's question, the two uploads, the dispatch, then the Policy.
    - **The question:** question 2, "How much underpayment have we flagged for Garden State Electric this month?", which has both case ids and a total to check.
    - **Why there are uploads:** the brief's "all 24 cases" needs PC-1214 and PC-1223 uploaded first, since seeding leaves them missing.
    - **Who uploads them:** PC-1214 is on the municipal building, so Marcus uploads it. PC-1223 is on the road resurfacing, outside his scope, so Dana uploads it.
11. **How the smoke check shows the Policy refused the call** (item 5). Signed as the operator, through the Gateway, with `agent/gateway.py`'s `Gateway`, the one way to call it:
    - **The allowed call:** `payrollcheck-context___get_filing_rules`. It answers, and the context function's log group shows an invocation in the window.
    - **The refused call:** `payrollcheck-app___get_case` for PC-1201. It's a read, so it does no harm even if something were wrong. It is refused with the Policy's default-deny reason, which the check requires the refusal's text to name ("not allowed due to policy enforcement", the wording phase 5 confirms on the real Gateway), and the app function's log group shows **no** invocation in the same window. The probe runs with no dashboard open, so nothing else calls the app.
    - **The engine's count:** a minute or two later, the policy engine's `DenyDecisions` metric in CloudWatch has gone up, as in Ed's `week3day2_lab2`.
12. **The Policy's tool names come from the code that names them:**
    - **The targets** from `agent/routes.py`'s `Target`.
    - **The app's operations** from `agent/app_operations.py`.
    - **The context tools** from `agent/context_tools.py`.
    - **The Gateway's separator** `___` from `agent/gateway.py`.

    A test checks that the app's names match `backend/agent_api.py`'s `OPERATIONS` and the context names match the tools the context server lists, so a new tool can't be left off the allowlist without a failing test. Each permit has the form `permit(principal is AgentCore::IamEntity, action == AgentCore::Action::"<target>___<tool>", resource == AgentCore::Gateway::"<gateway ARN>") when { [<callers>].contains(principal.id) };`. That is one permit per tool, as the brief asks, naming its callers by `principal.id`, the caller's ARN, which AWS's documentation for gateways with `AWS_IAM` auth describes ([Policy scope](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-understanding-cedar.html), [Principal-scoped policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/example-policies-principal.html)). A role is named as `arn:aws:sts::<account>:assumed-role/<role name>`, without a session. The policy engine validates each statement when it's created, and the step prints any failure's reasons.
13. **The CLI and the deploy target.** **Found in phase 3:** `agentcore deploy` makes its `default` target from the AWS account and region on its first deploy, so it needs no prompts, and `--yes` only confirms removing a stack; the step runs it. The global install of `@aws/agentcore@1.0.0-rc.5` was refused here, since npm's global folder belongs to root, so the help was read through `npx` and the user installs the CLI before step 7. Phase 4 reads `agentcore deploy --help` and `agentcore --version`, which make no AWS calls, to confirm two things. The first is how the CLI records its target account and region (in `agentcore/aws-targets.json`, which git ignores) and whether it takes `--yes`. The second is that the pinned CLI matches `@aws/agentcore-cdk` in `agentcore/cdk`. Installing the CLI on this laptop changes the machine, so I ask first. If the CLI can't deploy without prompts, the step prints the command for the user to run instead. **Found in phase 4:** the user agreed to a global install, which npm refused, since its global folder belongs to root, so the CLI was read through `npx`. Its help settled the target and the prompts. The CLI is `1.0.0-rc.5`, Ed's pin, and `agentcore/cdk` pins `@aws/agentcore-cdk` at `1.0.0-rc.3`, as Ed's project did; whether they deploy together is first shown by the real run in phase 5. The runbook tells the user to install the CLI globally, with `sudo` where npm needs it.

## Design

### The modules, and what each is for

- **`deploy/names.py`:** every resource name the runbook makes and the `project=payrollcheck` tag, written once, with `is_ours(name, tags)`, the teardown's test.
- **`deploy/aws.py`:** the one boto3 session, with its account, region and clients (Lambda, IAM, CloudWatch Logs, CloudWatch, `bedrock-agentcore-control`, `bedrock-agentcore`, CloudFormation and STS), and the operator's identity. Every step reaches AWS through it.
- **`deploy/waits.py`:** Ed's waits and retries (decision 6), where botocore has no waiter of its own: botocore's `function_active_v2`, `function_updated_v2`, `policy_engine_active`, `policy_active` and `memory_created` are used where they exist.
- **`deploy/commands.py`:** the one way a step runs a command (`uv`, `npm`, `agentcore`): from the root of the repo, found on the PATH as Windows and the Mac each name it, stopping the step when it fails.
- **`deploy/settings.py`:** reading what a step needs from the environment, saying which setting is missing by name and never its value, and writing `agentcore/.env.local`, replacing a line or adding one and never printing a value.
- **`deploy/supabase.py`:** step 1, the Auth users through the admin API (with httpx), and printing the MCP server's command from the project's ref.
- **`deploy/packaging.py`:** the two zips: `uv export` and `uv pip install --target` for Linux and Python 3.12, the folders without `tests/` and `__pycache__`, written with sorted entries and a fixed timestamp, and their SHA-256 as Lambda gives it.
- **`deploy/functions.py`:** step 2: the log groups, the roles, the functions and their URLs. It also holds the function's environment, keeping the runtimes' ARNs.
- **`deploy/identity.py`:** step 3: the Gateway's key provider, and the three credentials' values in `agentcore/.env.local`.
- **`deploy/gateway.py`:** step 4: the Gateway's role, the Gateway, the agent's API document from the deployed app, and the two targets, each compared before it's updated.
- **`deploy/policy.py`:** step 5:
  - **The Cedar text**, from pure functions: `allowlist(gateway_arn, callers)` gives each permit by its name.
  - **Callers by ARN:** `caller_of(arn)` turns a role's or a session's ARN into the principal the Policy sees.
  - **On AWS:** the engine, its attachment in `ENFORCE`, and putting the permits.
- **`deploy/memory.py`:** step 6, the Copilot's Memory.
- **`deploy/runtimes.py`:** step 7:
  - **Before the deploy:** the settings in `agentcore/.env.local`, `npm ci --prefix agentcore/cdk`, then `agentcore deploy`.
  - **After it:** finding the two runtimes and their roles, the app's permission to invoke them, and the function's environment.
  - **To finish:** step 5 again with both roles, and a health check of each runtime in a new session.
- **`deploy/resources.py`:** finding what the runbook made, by name, for every step.
- **`deploy/inventory.py`:** what the runbook made, with its tags, printed with every value the next step or `.env` needs (Ed's `show_resources`), and the teardown (decision 9). **Amended in phase 4:** apart from `resources.py`, since finding a resource and tearing everything down are two jobs.
- **`deploy/smoke.py`:** the parts of the smoke check that are code:
  - **The Policy probe** (decision 11): the two calls, and the two log groups read over the probe's window. **Amended in phase 4:** the probe calls each tool by its name in an MCP session of its own, signed with `agent/gateway.py`'s `SigV4Auth`, rather than through `agent/gateway.py`'s `Gateway`, which calls only the tools the Gateway lists, and the Gateway lists the operator none of the app's.
  - **The Copilot's Memory:** that events for Marcus's conversation are there.
  - **The answer:** checking the Copilot's answer against `data/copilot_expected.json`.
- **`deploy/__main__.py`:** the command line: one subcommand per step, `show`, `smoke` and `teardown`.
- **`deploy/operator_policy.json`:** the IAM policy for the operator's user: the course policy with `undercover*` resources renamed `payrollcheck*`, plus the three permissions the teardown's tag checks need (`iam:ListRoleTags`, `logs:TagResource` and `logs:ListTagsForResource`).
- **`deploy/RUNBOOK.md`:** the checklist. Each step says what it needs before it starts, what to run, what it leaves behind, and the settings that go into `.env` or `agentcore/.env.local`.

### How they depend

- **The shared modules.** `names.py`, `aws.py`, `waits.py`, `settings.py` and `commands.py` use nothing else in `deploy/` but each other's names and settings, and `resources.py` finds what's there for every step.
- **The steps.** Each step module uses those four and no other step's helpers. Two steps use another step's module through what it's for:
  - `runtimes.py` runs `policy.py`'s step, and runs `functions.py`'s environment update.
  - `gateway.py` and `policy.py` read the Gateway by its name through `resources.py`'s finders.
  - `policy.py` uses `gateway.py`'s `gateway_settings`, the Gateway's definition, since `update_gateway` must send every setting again when it enforces the engine.
- **The checks and the command line.** `smoke.py` uses `agent.gateway` and `agent.routes` for the probe, and `resources.py` to find the functions' log groups. `__main__.py` uses the steps.
- **Reading the product's names.** `deploy/` reads names from the product, and the product imports nothing from `deploy/`:
  - the targets, operations and context tools (decision 12)
  - `backend/agent_service.RUNTIME` and `backend/copilot_service.RUNTIME`, the function's two runtime settings
  - `agent/gateway.GATEWAY_URL`, written into `agentcore/.env.local`

There are no circular imports, and every service is called one way:
- **AWS:** through `aws.py`.
- **Supabase Auth's admin API:** through `supabase.py`.
- **The Gateway:** through `agent/gateway.py`.
- **The deployed app's API document:** through `gateway.py`, the one place with its path.

### What stays the same

The backend, the payroll agent, the Copilot, the improver, the dashboard and the context layer don't change. This stage changes configuration, packaging and documents, plus what the Policy needs, which is code in `deploy/`. `agentcore/` keeps the platform team's project with only the changes this stage needs: none are expected beyond what phase 4 finds. `backend/tests/test_sign_in.py::test_every_reviewer_operation_needs_a_sign_in_and_the_key_wont_do`, the test that the agent's key never signs off, sends back or overrides, stays as it is and passes.

### Testing without the network

`npm run check` never calls AWS or Supabase, and never reads `.env`:
- **AWS:** the steps' AWS calls are tested on real boto3 clients made with dummy credentials and botocore's `Stubber`, which checks every call's parameters and answers it with no network.
- **Supabase Auth:** the admin API calls go through `httpx.MockTransport`.
- **Commands:** `uv`, `npm` and `agentcore` are run through `deploy/commands.py`'s `run`, which the tests replace.
- **Packaging:** tested on a small folder in `tmp_path`, with the uv commands stubbed.

## Phases

### Phase 1: the runbook's frame, the operator's policy and Supabase

The `deploy/` package with its shared modules, the checklist's frame, the operator's IAM policy and step 1.

- [x] Before anything changes, `npm run check` with `.env` moved aside, and its figures recorded in the baseline above.
- [x] `pyproject.toml`: `deploy` in pytest's `testpaths`, coverage's `source`, ruff's `include` and pyright's include; `npm run check` still green, with `deploy/tests/` collected.
- [x] `deploy/tests/test_names.py`: every name starts `payrollcheck`; `is_ours` takes a name and tags with both, and refuses one with either missing (an `undercover-app`, a `payrollcheck-x` without the tag).
- [x] `deploy/tests/test_settings.py`: a missing setting is named in the error and no value appears in any message; writing `agentcore/.env.local` replaces an existing line, adds a new one, keeps the others, and prints nothing of the values.
- [x] `deploy/tests/test_operator_policy.py`: the policy parses, no statement names `undercover`, and it allows what the runbook calls, including `logs:FilterLogEvents` and `cloudwatch:GetMetricStatistics` for the smoke check, and nothing on resources outside `payrollcheck*`, `AgentCore-*`, `cdk-*` and the account-wide reads the course policy has.
- [x] `deploy/tests/test_supabase.py` (`httpx.MockTransport`): of three reviewers, the two missing are created with their email confirmed and the password, the one there is left alone; a second run creates nothing; the secret key is sent only as the admin API's headers; the MCP command has the ref from `VITE_SUPABASE_URL` and `read_only=true`.
- [x] `deploy/RUNBOOK.md`: the prerequisites (account, budget alert, IAM user with `deploy/operator_policy.json`, `aws configure` in `us-east-1`, the two CLIs) and step 1, each line saying what it needs and leaves.
- [x] `uv run -m deploy --help` lists every step built so far (a test checks each one is listed); `uv run -m deploy supabase` with no settings says which are missing, by name.
- [x] Review, fixes, tick, `docs/STATUS.md`, commit.

### Phase 2: Lambda and the Identity credentials

Steps 2 and 3: the two functions and the credentials.

- [x] `deploy/tests/test_packaging.py`: the app's zip holds `backend/`, `data/` and `dashboard/dist/` without `tests/` or `__pycache__`; the context layer's holds `context/`; building one twice gives the same bytes and the same SHA-256; the uv commands asked for are the server or context group for `x86_64-manylinux2014`, Python 3.12, binaries only.
- [x] `deploy/tests/test_functions.py` (`Stubber`):
  - a first run creates the log group with 7 days' retention, the role with Lambda's trust and the logging policy, and the function. It retries while the new role can't be used yet, then makes the URL. The app's URL is public, with its two permissions; the context layer's is `AWS_IAM`
  - a second run with the same zip calls no `update_function_code` and no `update_function_configuration`
  - a changed zip updates the code only
  - the function's environment keeps `PAYROLLCHECK_AGENT_RUNTIME` and `PAYROLLCHECK_COPILOT_RUNTIME` when they're there, and `DATABASE_URL` is on port 6543
- [x] `deploy/tests/test_identity.py` (`Stubber`): the key provider is created with the tag; one there holding the same key, read from its secret in Secrets Manager and never shown, is left alone; one holding another key is given this one (**amended in review**: the step compares the key rather than sending it again on every run, so a second run changes nothing); `agentcore/.env.local` gets the three `AGENTCORE_CREDENTIAL_*` values with the database on port 6543; nothing printed holds a value.
- [x] `deploy/RUNBOOK.md`: steps 2 and 3.
- [x] `npm run check` green; review, fixes, tick, `docs/STATUS.md`, commit.

### Phase 3: the Gateway, its targets and the Policy

Steps 4 and 5, with the allowlist.

- [x] `deploy/tests/test_gateway.py` (`Stubber`, `httpx.MockTransport` for the API document):
  - the role is created with `bedrock-agentcore`'s trust for `gateway/payrollcheck-gateway-*` and its two policies
  - the Gateway is created with MCP and `AWS_IAM`, retrying while its role isn't usable
  - the app's target carries the agent's API document with the app's URL as its server, and the key provider as `X-API-Key` in the header; the context layer's target points at `<URL>/mcp` with the Gateway's role signing for Lambda
  - a second run, with the same document, updates no target
- [x] `deploy/tests/test_policy.py`:
  - **The allowlist**, with no network, from a Gateway ARN and the callers:
    - one permit for each of the 12 tools, named `payrollcheck_allow_<target>_<tool>`
    - each `action ==` the Gateway's name for one tool (`payrollcheck-app___get_case`, …), and each `resource ==` the Gateway's ARN
    - no `forbid` in any statement, and nothing about payments, amounts or `pay_claim`
  - **The callers on each permit:**
    - the app's seven tools name only the agent's runtime role
    - the five context tools name the agent's role, the Copilot's role and the operator
    - with no runtimes yet, the app's permits aren't written, since no one may call them, and the context tools name the operator (**amended**: a permit naming no caller would be an empty set in Cedar)
    - the Runtimes step needs both runtimes, each with its own role
  - **What's allowlisted is what the code names:** the app's names are `backend/agent_api.py`'s `OPERATIONS`, and the context names are the tools `context/server.py`'s server lists.
  - **`caller_of`** turns `arn:aws:iam::<account>:role/<name>` and `arn:aws:sts::<account>:assumed-role/<name>/<session>` into `arn:aws:sts::<account>:assumed-role/<name>`, and leaves an IAM user's ARN as it is.
  - **On AWS**, through `Stubber`:
    - the engine is created with the tag, the role gets `GetPolicyEngine`, `AuthorizeAction` and `PartiallyAuthorizeActions`, and the Gateway is updated to `ENFORCE`, retrying while the permission travels
    - a policy that's there, active, with the same statement isn't touched; one with a different statement, or one the engine refused, is updated; a missing one is created; and one of ours the allowlist no longer has is deleted (**amended in review**)
    - a permit the engine refuses prints its reasons and stops the step
    - a second run changes nothing
- [x] `backend/tests/test_sign_in.py::test_every_reviewer_operation_needs_a_sign_in_and_the_key_wont_do` passes unchanged.
- [x] `deploy/RUNBOOK.md`: steps 4 and 5, with the allowlist in a table, each tool and who may call it.
- [x] `npm run check` green; review, fixes, tick, `docs/STATUS.md`, commit.

### Phase 4: the Memory, the Runtimes, what's there and the teardown

Steps 6 and 7, `show` and `teardown`.

- [x] With the user's okay to install it: `agentcore --version` gives the pinned version, and `agentcore deploy --help` says how it takes its target and whether it takes `--yes` (decision 13). The plan records what it found. (Read through `npx`, since the global install was refused: decision 13.)
- [x] `deploy/tests/test_memory.py` (`Stubber`): the Memory is created with its two strategies on `/reviewers/{actorId}/preferences/` and `/reviewers/{actorId}/facts/`, 7-day events and the tag, then waited on while `CREATING`; one that's there, and not `DELETING`, is used as it is.
- [x] `deploy/tests/test_runtimes.py` (`Stubber`, the runner stubbed):
  - `agentcore/.env.local` gets `PAYROLLCHECK_API`, `PAYROLLCHECK_GATEWAY_URL` and `PAYROLLCHECK_COPILOT_MEMORY_ID` beside the three credentials
  - the runner is asked for `npm ci --prefix agentcore/cdk`, then `agentcore deploy`
  - the two runtimes are found by name, and their roles' ARNs read
  - the app's role may invoke both runtimes and their endpoints
  - the function's environment gains both ARNs and keeps the rest
  - the permits are put again naming both roles
  - each runtime answers the health check in a new session
- [x] `deploy/tests/test_resources.py` (`Stubber`):
  - **`show`** lists what's there by kind, with the values `.env` and the next steps need, and no secret.
  - **The teardown without `--yes`** deletes nothing and lists what it would delete.
  - **With `--yes`** it deletes only what is named `payrollcheck…` and tagged for the project. A same-named resource without the tag is left and reported. It waits for targets and policies to go before their Gateway and engine. It leaves `CDKToolkit` and prints how to remove it and the Supabase project by hand.
- [x] `deploy/RUNBOOK.md`: steps 6 and 7, `show`, the smoke check's lines (phase 5) and the teardown.
- [x] `deploy/tests/test_smoke.py` (**added**: the smoke check's code is built here, so phase 5 only runs it): through the agent tests' stand-in Gateway, a context tool answers signed as the operator and an app tool its Policy refuses is refused by name; the probe passes only on the Policy's own refusal with no invocation of the app; the Copilot's latest answer must be to question 2 and name PC-1009 and $198.75, with the Memory holding the conversation's events; the engine's decisions are read for `ENFORCE`.
- [x] `npm run check` with `.env` moved aside: green, including `npm run check:runtime`, which still imports `runtime.main` and `runtime.copilot` with the `runtime` group alone.
- [x] Review, fixes, tick, `docs/STATUS.md`, commit.

### Phase 5: the runbook run, and the smoke check

This phase creates resources on AWS and a project on Supabase, so it starts only when the user runs the runbook or asks me to run it. Before it, I take the OpenRouter key's usage, for the spending report.

- [x] **The first run**, from nothing, step by step as `deploy/RUNBOOK.md` says. Each step ends `created` or `unchanged` for each of its resources, and `uv run --env-file .env -m deploy show` lists every resource in the table above.
- [x] **The second run** of steps 2 to 7: every resource says `unchanged`. The function's `CodeSha256` and `LastModified` are the same before and after, and `show` prints the same.
- [x] **The deployed dashboard:** the app's Function URL serves the dashboard. The user signs Marcus Oyelaran and Dana Whitfield in, in a Playwright window opened after asking, typing the passwords themselves. The header shows the business date Nov 23, 2026 after `npm run seed`. **Amended in the run:** the app's URL is public, so the user signed in in their own browser and sent screenshots, and scripts checked the records.
- [x] **The Copilot, before any dispatch:** asked question 2 as Marcus, it answers on the Copilot's Runtime with the case ids and the total in `data/copilot_expected.json`, checked by `deploy/smoke.py`. With its Memory on, the Memory holds events for Marcus's conversation.
- [x] **The dispatch:**
  - Marcus uploads PC-1214 and Dana uploads PC-1223.
  - Marcus starts a dispatch of the week-12 wave, which works all 24 cases on the payroll agent's Runtime, through the Gateway. Each case's steps name its tools as the Gateway names them (`payrollcheck-app___…`, `payrollcheck-context___…`), and every case ends Awaiting review.
  - The panel shows Marcus his cases and the count of the others.
- [x] **The Policy**, with `uv run --env-file .env -m deploy smoke` and no dashboard open:
  - the context tool answers and its function's log group shows the call
  - `payrollcheck-app___get_case`, signed as the operator, is refused with the Policy's default deny, and the app's log group shows no invocation in the window
  - a few minutes later, the engine's `DenyDecisions` metric shows the refusal and `AllowDecisions` the dispatch's calls
- [x] **What it spent:** the dispatch's and the Copilot turn's cost from the backend's records, the OpenRouter key's usage before and after, and AWS's figures as the console shows them a day later. The report also lists the resources the runbook made. **Amended in the run:** the backend's and OpenRouter's figures are in `docs/STATUS.md`; AWS's come a day later, for the user to read in the console.
- [x] **Success criterion 7, deployed on AWS AgentCore,** is met, and `docs/STATUS.md`'s "Last live run" says how, with the spend.

### Phase 6: Ed's notebooks go, and the documents

- [x] The `labs/` folder is deleted, as `ecca35dd:labs/` had it: Ed's notebooks, `ecca35dd:labs/week3day4_aws.py`, `ecca35dd:labs/undercoverlab/` and the day briefs in it, and `.gitignore`'s lines for it.
- [x] `git grep -n "labs/"` finds no reference to the folder as something in the repo. `agent/screening.py`'s and `agent/improver.py`'s docstrings, and `docs/ROADMAP.md`, the stage briefs and the earlier plans, name Ed's import commit `ecca35dd` where they cite a notebook. **Amended in the review:** a file of Ed's is cited as `ecca35dd:labs/<file>`, git's name for it at that commit; where the history speaks of the folder as it was, such as the stage briefs' own requirement to delete it, it stays `labs/`.
- [x] **The documents describe the product as it now is:**
  - **`AGENTS.md`:** the `deploy/` folder in place of `labs/`, and where Ed's notebooks are now, at `ecca35dd`.
  - **`README.md`:** the deployment and its runbook. It also drops "Today these run the renamed UnderCover code" and "until stage 3", which are stale.
  - **`docs/TECH_STACK.md`:** its Deployment section renamed, with the runbook in place of the notebooks, the Memory made by step 6, and the Policy as an allowlist by caller. The payroll agent's Gateway route on the laptop now reaches only the context tools.
  - **`docs/PROCESS.md`:** how the runbook is run, and that `npm run check` tests its ordinary code without the network.
  - **`docs/CODE_STANDARDS.md`:** rule 7 gains `deploy/` with each service called one way and the names in `deploy/names.py`.
  - **`docs/SPEC.md`:** its rule on the Gateway's Policy says the allowlist names its callers.
  - **`docs/STATUS.md`:** stage 7 built, the known gap on the Copilot's route closed, `Running it` pointing at the runbook, and the stage 6 line's "on `stage-6-copilot`" corrected now that it's merged.
- [x] `npm run check` with `.env` moved aside: green.
- [x] Review, fixes, tick, `docs/STATUS.md`, commit; then the review of the whole branch against `main`, its fixes, and the report.

## Not in this stage

- Render or any other host.
- Memory for the payroll agent.
- Langfuse on Runtime: the runtimes' credentials keep their three entries, as the brief says, so the payroll agent's traces are off there. The documents say so.
- Everything in `docs/SPEC.md`'s Not for now.
