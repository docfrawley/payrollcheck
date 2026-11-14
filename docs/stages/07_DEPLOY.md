# PayrollCheck on AWS AgentCore

From the compliance manager at Pinelands Builders, with our IT team.

A note on names: this brief uses the file, table and setting names as stage 1 renamed them (UnderCover to PayrollCheck, claim to case, handler to reviewer, `UNDERCOVER_*` to `PAYROLLCHECK_*`). Where a file here doesn't exist under exactly that name, use the one an earlier stage left in its place. The words are those in `CONTEXT.md`.

## Where we're heading

After stage 6, PayrollCheck works end to end on the laptop: `npm run dev` runs the backend, the payroll agent, the Copilot, the context layer and the dashboard on the direct route, against our database. The code is already ready for AWS. Ed built it to run on Lambda and AgentCore Runtime, each AWS piece switched on by its setting, and `docs/TECH_STACK.md`'s Deployment section describes it. Our last success criterion is that it runs there: deployed on AWS AgentCore.

Nothing exists on AWS for PayrollCheck yet, and nothing was ever created for UnderCover either. Ed's code assumes resources his lab notebooks made by hand, one notebook at a time, and we never ran them. We have a Supabase account, but no PayrollCheck project in it. So this stage is mostly a port: take the provisioning steps out of `labs/` and turn them into one scripted, re-runnable runbook that stands up PayrollCheck from nothing, then delete `labs/`.

The deployment also gets one new rule. UnderCover's AgentCore Gateway had a Policy that capped payments at $1,000. PayrollCheck has no payments, so the cap goes. In its place, the Policy is an explicit allowlist: a permit for each tool the agent's work needs on each target (its lookups, check tools and its own writes, such as saving its exception report and draft notice), and everything else denied by default. A person's actions, sign off, send back and override, need a reviewer's sign-in and aren't in the agent's API document, so they can't be routed through the Gateway at all. Our backend refusing them to the agent's API key stays the lock on "no case reaches Accepted without a reviewer's sign-off", with its own test; the allowlist keeps the agent to its own tools at the infrastructure level.

## What we want

1. **AWS AgentCore is the target; the direct route stays.** `npm run dev` still runs everything on the laptop, with each AWS piece off when its setting isn't there, as now. Render isn't a target.

2. **Fresh resources, all named for PayrollCheck.** Every AWS resource is new and named `payrollcheck…` (with a hyphen or an underscore where a service needs one, as Ed's names did), and tagged for the project, so the runbook can find what it made. Nothing is shared with any UnderCover resource.

3. **A provisioning runbook in place of the notebooks.** One scripted, re-runnable runbook, organised as a checklist. Each step creates what's missing and updates what's already there, as `labs/week3day4_aws.py` does, so running it twice changes nothing the second time. The user runs it, or explicitly asks the coding agent to run it; the agent never creates or deletes AWS resources unless the user asks, as `AGENTS.md` says. It covers, in order:
   1. **Supabase**: a new PayrollCheck project in the existing Supabase account, its schema and seed from `npm run seed`, and the three reviewers' auth users (Dana Whitfield, Marcus Oyelaran, Priya Raman) with the emails in `data/reviewers.json`. Ported from Part 1 of `labs/week2day3.ipynb`. The runbook says which settings go into `.env` afterwards (`DATABASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`) and how to point the read-only Supabase MCP server at the new project.
   2. **Lambda**: the backend and dashboard as one function with a public Function URL, and the context layer as a function behind a Function URL with IAM auth, each with its log group and role. Ported from Part 1 of `labs/week3day2_lab2.ipynb`, Parts 1 and 2 of `labs/week3day3.ipynb` and `deploy_app` and `deploy_context` in `labs/week3day4_aws.py`, packaged as `docs/TECH_STACK.md` describes.
   3. **Identity credentials**: the agent's API key as the Gateway's credential for the app target, and `OPENROUTER_API_KEY`, `PAYROLLCHECK_API_KEY` and `DATABASE_URL` (Supabase's transaction pooler, port 6543) for the two runtimes, in AgentCore Identity.
   4. **The Gateway**: its role, the Gateway, and its two targets, the app (the payroll agent's own API document, which the backend serves) and the context layer. Ported from Part 3 of `labs/week3day3.ipynb` and `make_gateway` and `put_targets` in `labs/week3day4_aws.py`.
   5. **The Policy**: the policy engine, enforced on the Gateway, as an explicit allowlist: a permit for each tool the agent's work needs on each target (its lookups, check tools and its own writes, such as saving its exception report and draft notice), and everything else denied by default. Ed's `payment_limit` forbid is not ported. Ported from Part 3 of `labs/week3day2_lab2.ipynb` and `enforce_policy` in `labs/week3day4_aws.py`.
   6. **The two Runtimes**: the payroll agent and the Copilot, deployed from the AgentCore project in `agentcore/` with one `agentcore deploy`, writing `agentcore/.env.local` first. Then the backend's function is pointed at both, with `PAYROLLCHECK_AGENT_RUNTIME` and `PAYROLLCHECK_COPILOT_RUNTIME` and its role allowed to invoke them. Ported from Parts 2 to 4 of `labs/week3day4_lab2.ipynb` and Parts 4 and 5 of `labs/week3day5_lab1.ipynb`.
   7. **The Copilot's Memory**: `payrollcheck_copilot_memory`, with its User Preference and Semantic strategies on the per-reviewer namespaces the Copilot uses. Ported from Part 3 of `labs/week3day5_lab1.ipynb`. There's no Memory for the payroll agent: agent memory went in stage 3, so `create_memory` for it isn't ported, and the agent's runtime role (`runtime/policy.json`) has no Memory permission.

   The runbook ends with what it made and each value the next step or `.env` needs, printed, as `show_resources` in `labs/week3day4_aws.py` does.

4. **A smoke check on the deployed product.** After the runbook, on the deployed dashboard: sign in as Marcus Oyelaran, start a dispatch of the week-12 wave, which works on the payroll agent's Runtime through the Gateway, and ask the Copilot one of the six questions in `docs/SPEC.md`, which answers from the Copilot's Runtime with the right case ids and totals. The check is part of the runbook's checklist.

5. **The Policy is shown working.** As part of the smoke check, a call through the Gateway, signed as the agent, to a tool that isn't on the allowlist is refused by the Policy, and the target's logs show the call never reached it.

6. **Then `labs/` goes.** Once every step the code relies on is in the runbook and the smoke check passes, delete `labs/`, Ed's notebooks, `labs/week3day4_aws.py`, `labs/undercoverlab/` and the day briefs in it included. Nothing outside `labs/` may refer to it afterwards: update `AGENTS.md`, `README.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md` and `docs/STATUS.md` to point at the runbook instead.

## Our IT team's choices

- **Port, don't redesign.** The runbook does what Ed's notebooks and `labs/week3day4_aws.py` do, with boto3 and the `agentcore` CLI, in the same order and the same create-or-update way, renamed for PayrollCheck and without the payment cap, the agent's Memory and the course's teaching steps. Keep the notebooks' hard-won waits and retries, such as waiting for the Gateway role's new permission to reach AgentCore.
- **The plan chooses where the runbook lives**, how its checklist and its scripts are split, and which steps run as code and which the user does by hand in the Supabase or AWS console (creating the Supabase project, for instance, may need the user). Each step says what it needs before it starts and what it leaves behind.
- **A teardown is the user's call.** The plan says whether the runbook includes a teardown like Ed's `tear_down`, and if it does, it deletes only resources tagged for PayrollCheck, only when the user runs it.
- **The allowlist in Cedar** is written against the Gateway's names for the agent's tools on each target, as `payment_limit` was written against `pay_claim`: one permit per tool, no forbid, and default deny for the rest. The plan works out how the Policy names each tool and which call off the allowlist item 5 makes; if that can't be done as decided, stop and ask.
- **`agentcore/`** keeps the platform team's project as it is, renamed: two runtimes, `agent` and `copilot`, on platform version V2, with only the changes this stage needs. Its credentials list keeps its three entries.
- **The runbook is tested where it can be.** `npm run check` never calls AWS or Supabase. Anything in the runbook that's ordinary code, such as building a package, the policy statements or the settings it writes, is tested without the network if it lives where the tests reach it; the plan says where that is, without excluding a file from coverage.
- **Credentials** come from the user's AWS CLI profile and `.env`; the runbook never prints a secret and never writes one into the repo.

## What stays the same

- The rules in `docs/SPEC.md`. The agent identifies itself with its API key on every request and never takes a person's action.
- The code: the backend, the payroll agent, the Copilot, the improver, the dashboard and the context layer behave as they do on the laptop. This stage changes configuration, packaging and documents, plus what the Policy needs, and nothing else.
- The direct route for `npm run dev`, and every check in `npm run check`, which needs no network and never reads `.env`.
- `docs/TECH_STACK.md`'s Deployment section, renamed, except where the runbook replaces a lab notebook.

## What done looks like

- `npm run check` is green with `.env` moved out of the way, with tests for the runbook's ordinary code and for the Policy's statements: a permit for each allowlisted tool, a default deny, and no payment cap. The backend's test that the agent's API key is refused on sign off, send back and both overrides still passes.
- The runbook, run once by the user (or by the agent when the user asks), stands up everything in item 3 from nothing, and a second run changes nothing.
- The smoke check passes on the deployed product:
  - signed in as Marcus Oyelaran on the deployed dashboard, a dispatch of the week-12 wave works all 24 cases on the payroll agent's Runtime, through the Gateway, and the panel shows his cases and the count of the others
  - one Copilot question answers from its Runtime, with its Memory on, with the right case ids and totals, checked against `data/copilot_expected.json`
  - a call through the Gateway, signed as the agent, to a tool that isn't on the allowlist is refused by the Policy and never reaches its target
  - report what the smoke check spent and the resources the runbook made
- Success criterion 7 in `docs/SPEC.md`, deployed on AWS AgentCore, is met.
- `labs/` is deleted, and nothing in the repo refers to it.
- `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md`, `docs/CODE_STANDARDS.md`, `docs/STATUS.md`, `AGENTS.md` and `README.md` describe the product as it now is.

## Not for now

- Render or any other host. The direct route keeps it possible later.
- Memory for the payroll agent.
- Everything in `docs/SPEC.md`'s Not for now: real email, live NJDOL rates, filing to NJ Wage Hub and the rest.

## Planning

Follow `docs/PROCESS.md`, but write this plan to `docs/PLAN_DEPLOY.md` and tick it off there. Plan five or six phases and commit at the end of each. Start by reading the notebooks named above without running them, and list every resource and setting Ed's code relies on. Then write the runbook's Supabase steps, then Lambda and the Identity credentials, then the Gateway, its targets and the new Policy, then the two Runtimes and the Copilot's Memory, and last the smoke check, which the user runs or asks you to run, and the deletion of `labs/`. Writing the runbook creates nothing: only running it does, and only when the user says so.
