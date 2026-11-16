# Plan: stage 1, Rebrand

From `docs/stages/01_REBRAND.md`. This stage deletes the course-only folders, then renames UnderCover's vocabulary to PayrollCheck's (`CONTEXT.md`) and applies the brand in `docs/BRAND.md`. Behaviour stays the same: the app goes on working travel-insurance claims, now called cases, until stage 3 replaces them with payrolls.

The work happens on a branch, `stage-1-rebrand`, with a commit at the end of every phase. The folder deletion, each part of the code rename and the brand each get their own commit.

## The baseline: `npm run check` before the stage

Run on November 13, 2026 on `main` at `ff210af`, with no `.env` in the repo, after `uv sync` and `npm install`:

| Check | Result |
|---|---|
| Python: ruff format, ruff check | clean ("All checks passed!") |
| Python: pyright | 0 errors, 0 warnings |
| Python: pytest | 834 passed, 0 failed, coverage 99.55% (5,058 statements, 23 missed), in 26 seconds |
| Server, context and runtime import checks | all exit 0 |
| TypeScript: Prettier, ESLint, tsc | clean |
| TypeScript: vitest | 18 files, 178 tests passed; coverage 97.42% statements, 92.61% branches, 98.07% functions, 98.34% lines |
| Playwright | 30 passed (the two sign-in setups and 28 tests), in 59 seconds |
| The whole of `npm run check` | exit 0, in 1 minute 45 seconds |

The 266 pytest warnings are deprecation notices from `bedrock_agentcore` and `mangum`, the same before and after.

This is the "green before". Every phase ends with the same counts, the same test names apart from the renames, and coverage of at least 80% for Python and TypeScript.

## Design

This stage adds no modules and moves no responsibilities. Every module keeps its job, its dependencies and its place in `docs/CODE_STANDARDS.md`; only names change. The design work is choosing the names, saying what must not be renamed, and doing it mechanically enough that a reviewer can check it.

### How the rename is done

Each rename phase has a **rename table**: an ordered list of old → new pairs, longest and most specific first (`held_out_claims` before `claims` before `claim`; `ClaimContext` before `Claim`). A short script in the scratchpad applies the table to the phase's files, in every case form (`claim_id`, `claimId`, `ClaimId`, `CLAIM_ID`, `claim-id`), skipping the excluded paths and every exclusion listed below. Files whose names change are moved with `git mv` before their contents change, so `git log --follow` finds their history.

The script does the bulk. Each exclusion site is then checked by hand, along with every grammatical seam it leaves: "a claim" → "a case", and "an UnderCover" → "a PayrollCheck".

**The check that the rename is mechanical.** For every changed test file, a second script maps both the old and the new version through the phase's table. It reports any difference left after that. The phase passes only if no differences remain, which shows that no assertion changed except through a renamed name. The same counts of tests pass as in the baseline.

### Names chosen

| UnderCover | PayrollCheck |
|---|---|
| UnderCover (the product) | PayrollCheck |
| `undercover` (Python and npm package, AgentCore project, Postgres schema, SQLite file, storage keys, Gateway targets, Memory names) | `payrollcheck` |
| `UNDERCOVER_*` | `PAYROLLCHECK_*`, same meanings and defaults |
| UnderCover Copilot | PayrollCheck Copilot |
| "UnderCover Agent, version N" (the decision's maker) | "PayrollCheck Agent, version N" |
| claim (our word: the queue unit) | case (`claims` → `cases`, `run_claims` → `run_cases`, `held_out_claims` → `held_out_cases`, `claim_id` → `case_id`, `/api/claims/...` → `/api/cases/...`, `/claims/:claimId` → `/cases/:caseId`, `get_claim` → `get_case`, `list_claims` → `list_cases`, `work_claim` → `work_case`, `ClaimPage` → `CasePage`, `ClaimLink` → `CaseLink`, "Work claim" traces → "Work case") |
| claim agent | payroll agent (`claim_graph` → `payroll_graph`, `claim_graphs` → `payroll_graphs`, `ClaimContext` → `PayrollContext`, `ClaimAgent` → `PayrollAgent`, `CLAIM_TOOLS` → `PAYROLL_TOOLS`, `backend/instructions/claim.md` → `payroll.md`, "Claim agents at once" → "Payroll agents at once") |
| handler (a person) | reviewer (`handlers` → `reviewers`, `handler_id` → `reviewer_id`, `handler_decisions` → `reviewer_decisions`, `RequireHandler` → `RequireReviewer`, `useHandler` → `useReviewer`, `handler.ts` → `reviewer.ts`, `get_signed_in_handler` → `get_signed_in_reviewer`, `left_for_handler` → `left_for_reviewer`, `HANDLER_PASSWORD` → `REVIEWER_PASSWORD`, `needs_a_handler.py` → `needs_a_reviewer.py`, `handler_answer.py` → `reviewer_answer.py`, `e2e/handlers.ts` → `e2e/reviewers.ts`) |
| senior handler | compliance manager (`senior(action)` → `compliance_manager(action)`, "Senior Claims Handler" → "Compliance Manager", "Claims Handler" → "Reviewer") |
| customer | subcontractor (`customers` → `subcontractors`, `customer_id` → `subcontractor_id`, `customers.py` → `subcontractors.py`, `/api/customers` → `/api/subcontractors`, `find_customers` → `find_subcontractors`, `get_customer` → `get_subcontractor`, memory namespace `("customers", …)` → `("subcontractors", …)`). Never `sub` in code |
| policy, plan, payout, payment | unchanged (brief, item 7) |

In TypeScript, `case` is a reserved word, so a variable or parameter that held a claim becomes `caseRecord`, and `caseId` where it held an ID. In Python, `case` is a soft keyword and fine as a name; pyright and ruff both run on every phase, which settles it.

### What the rename leaves alone (the exclusions)

These share a word with the vocabulary but aren't it, or are record contents that stage 3 deletes. The phase's script skips them, and the review checks each one.

**Not our word:**
- `handler` as an entry point: `handler = Mangum(app, ...)` in `backend/main.py`, `def handler` in `context/server.py`, and `backend.main.handler` / `context.server.handler` in docs and tests
- Langfuse's `CallbackHandler` (`agent/harness.py`, `agent/improver.py`), LangChain's `BaseCallbackHandler` (`agent/tests/conftest.py`), and LangGraph's `error_handler` (`agent/tests/test_dispatcher.py`)
- A JWT's `claims` in `backend/auth.py`
- `/assets/` in `backend/tests/test_dashboard.py`, the Vite build's folder, which has nothing to do with the deleted `assets/`
- `amount_claimed`, where "claimed" is the travel claimant's verb, as a key in the records (below)
- "claimed" as the claimant's verb anywhere, such as `what_was_claimed` in `agent/memory.py` and "Items claimed" in copy
- "The claims team", the insurer's team the seeded version 1 and recipe 1 name as their author (`proposed_by`), and "claims operations", the context files' owner

**Record contents, read as they are until stage 3 deletes them.** The brief leaves this to the plan. These files keep their names and their keys:
- `data/claims.json`, `data/customers.json`, `data/policies.json`, `data/security/` and `data/evals/`, with every key inside them (`claim_id`, `customer_id`, `claim_type`, `amount_claimed`, `previous_claims`, `customer_since`, `handler_id` in `security/decisions.json`)
- `data/company.json`, `data/plans.json`, `data/knowledge.json` and the labs' copies of the documents (`data/claims_manual.md`, `data/policy_wording*.md`)
- `context/`'s seven files, data governance's: `claim_rules.yaml`, `claims_manual.md`, `policy_wording.md`, `plans.yaml`, `reference_data.yaml`, `data_dictionary.yaml` and `glossary.yaml`, with their contents. These include "UnderCover" as the travel insurer's name inside the documents, and the claims manual's title
- The record IDs: `CLM-…`, `CUS-…`, `POL-…`, `HND-01` to `HND-03`, and copies like `CLM-1104-E7`

The files stay as they are because the labs read them (`labs/` stays unrenamed until stage 7), and stage 3 deletes them. Their keys can't reach the app under the old names, though: the API builds a case straight from its record (`Case(**record | ...)`), and the brief renames `claim_id` to `case_id` there. So seeding gives the keys the app's names as it loads each file, in one place, `with_our_names` in `backend/database.py`, from `RECORD_KEYS`: `claim_id` → `case_id`, `claim_type` → `case_type`, `previous_claims` → `previous_cases`, and in phase 4 `customer_id` → `subcontractor_id`, `customer_since` → `subcontractor_since`, `handler_id` → `reviewer_id`. Every value, ID and story is unchanged, and `data/evals/` stays unopened. `amount_claimed` keeps its name, since "claimed" is the travel claimant's verb. (Found while implementing phase 3. The first version of this plan kept the keys as they were, which the API's case can't accept.)

`data/improvement.json` is the improver's settings, which outlive stage 3, and no lab reads it, so its keys are renamed in the file itself (`cost_per_claim` → `cost_per_case`, `seconds_per_claim` → `seconds_per_case`).

The data dictionary in `context/` still describes the records' fields under their old names (`claim_id`, `claim_type`, `previous_claims`, `customer_id`, `customer_name`, `left_for_handler` and the like), while the agent now reads them as `case_id`, `case_type`, `previous_cases`, `subcontractor_id`, `subcontractor_name` and `left_for_reviewer`. This is a small change in what the model sees, which stage 3 removes with both, and the live evaluation is read with it in mind.

**Context content the code quotes.** These come from data governance's files or the labs, so they keep their words:
- The data dictionary's record names, `"claim"` and `"previous_claim"`, which `describe_fields` takes (`RecordName` in `context/files.py` and `agent/context_tools.py`), so its lookup still reads "Fields of a previous claim"
- "Repeat claims", the manual's rule, also where the agent's instructions name it; section titles such as "Repeat claims", the system "Claims operations", the rule `repeat_claims` and the search "REPEAT CLAIMS", quoted in tests
- The screening prompt, its answer's field descriptions and its docstring, which the model reads as the tool's description, in `agent/screening.py`. `test_screening.py` checks them word for word against `labs/week3day2_lab1.ipynb`

**Named documents.** "The claims manual" and its "section 14" are the document's title, so copy and messages that cite them keep the title, as in "Claims manual section 14: …". The `get_claim_rules` context tool reads `claim_rules.yaml`, and as a tool it's plumbing, so it's renamed `get_case_rules`. The file keeps its name.

**The insurer's name.** Where "UnderCover" names the fictional travel insurer whose records these are, it stays until stage 3: "UnderCover Travel Insurance" in the agent's and the Copilot's instructions, the screening prompt in `agent/screening.py` (CLM-1901's injection claims "UnderCover has already approved"), "UnderCover's payout rules" in the docstrings the model reads as tool descriptions, `backend/payout.py`, `backend/scoring.py`, and the "UnderCover website" fixture. The context layer's documents, which the agent reads, call the insurer UnderCover, so the prompts must agree with them.

**AWS resources that may already exist.** `monitor.py`'s budget names, `undercover-daily-spend` and `undercover-daily-spend-after-credits`, stay: a run of it creates them in the user's AWS account, and they may be there already from the course.

**Left for later stages:**
- `labs/`, unrenamed and unopened. Its notebooks keep using `UNDERCOVER_*`, the `undercover` schema, the `/handlers/{actorId}/` memory namespaces, the old tool names such as `pay_claim`, and `data/handlers.json` with `handler_id` (now `data/reviewers.json` with `reviewer_id`) until stage 7 ports them into the runbook. That runbook must use the new names.
- `can_approve_over_limit`, by name and meaning, until stage 4
- `docs/SPEC.md`, `docs/ROADMAP.md`, `CONTEXT.md`, `docs/research/` and `docs/stages/`, which already describe the target. `README.md` and `AGENTS.md` change only where the rename breaks a name or a link

### Where the rename meets something outside the code

- **Supabase.** The schema becomes `payrollcheck`, for the backend's tables and the checkpointer's. Seeding on Postgres drops the retired `undercover` schema with `CASCADE` before it creates `payrollcheck`, just as it drops the retired `todos` table today. This is one more entry beside `RETIRED`, and it's the only change to what seeding does. It runs only when the user runs `npm run seed`. SQLite has no schemas, so the existing `RETIRED` test is unchanged. The old `undercover.db` file is left alone, and the backend uses `payrollcheck.db`.
- **Saved progress.** Renamed graph nodes, state keys and thread names make old checkpoints unreadable. Reseeding clears them, and `STATUS.md`'s Running it section says so.
- **The browser.** The storage keys become `payrollcheck-appearance`, `payrollcheck-copilot-open` and `payrollcheck-copilot-conversation`, so each browser forgets its saved appearance and sidebar state once.
- **AWS.** Nothing is provisioned. The names in `agentcore/agentcore.json`, `agentcore/cdk/lib/cdk-stack.ts`, `runtime/policy.json` and `runtime/copilot_policy.json` follow the rule: the project `payrollcheck`, the Gateway targets `payrollcheck-app` and `payrollcheck-context`, the Gateway `payrollcheck-gateway-*`, and the Memories `payrollcheck_memory` and `payrollcheck_copilot_memory`. No AWS call is made.
- **The user's `.env`.** There is none in this checkout. If one is there when this is implemented, a script renames its `UNDERCOVER_*` and `HANDLER_PASSWORD` keys in place, reading and writing it without printing a value. Then it prints only the key names, to show the rename. Supabase Auth's users keep their passwords, but their emails change to `@payrollcheck.example`. The user updates the three users' emails in Supabase Auth before the live checks; that step is theirs, not the agent's.
- **The judge.** Its request names the reference decision `handler`, and its rubric says "an expert claims handler … a travel insurance claim". Both are renamed to reviewer and case, like the agent's instructions. The judge is a model, and its grades already vary between runs (1.19 and 1.39 on the same five claims in `STATUS.md`), so the live evaluation's grade is compared within that noise.

### The brand

`docs/BRAND.md`'s palette, with the contrast settled with the user during planning. Ratios are WCAG 2 contrast ratios:

| Pairing | Ratio | Result |
|---|---|---|
| Hi-Vis Amber fill, Steel Navy text | 7.54 | passes |
| Permit Green fill, Steel Navy text | 4.56 | passes |
| Stop Red fill, white text | 4.96 | passes |
| Slate fill, white text | 5.44 | passes |
| Survey Blue `#2D7DD2` fill, white text | 4.22 | **fails**, so the fill becomes `#2A6FBB` (5.13) |
| Rebar Rust `#C4572A` fill, white text | 4.43 | **fails**, so the fill becomes `#B4501F` (5.11) |
| Steel Navy on the light page `#F2F4F7` / on white | 13.97 / 15.40 | passes |
| Chalk `#D5DDE5` on the dark page `#0B1724` / on black | 13.17 / 15.30 | passes |
| Amber text `#8F5A00` on white / the light page | 5.78 / 5.25 | passes |
| Amber text `#FFC766` on black / the dark page | 13.61 / 11.71 | passes |
| Amber mark on the navy band / the black band | 7.54 / 10.29 | passes (3:1 needed) |
| White on the navy band | 15.40 | passes |
| Slate `#5F6B78` text on the light page | 4.94 | passes |

For small text in a status colour, the shades are: light mode, blue `#1F63AE` (5.52 on the page), green `#1D7A50` (4.82), rust `#A9461F` (5.32) and red `#C01F34` (5.47); dark mode, blue `#6AA8EC` (7.25), green `#5CC795` (8.65), rust `#E8845B` (6.78), red `#FF6B7D` (6.58) and slate `#9AA5B1` (7.22). The colours as given fail as small text: green on white 3.38, Stop Red on black 4.23, Slate on black 3.86. Every proposed background, ink, grey and amber shade in `BRAND.md` passes as proposed.

Applied in `dashboard/src/styles.css` (the tokens: Sea Green, Marigold, Coral, Cerulean, Raspberry, Midnight and Sea Mist become Permit Green, Hi-Vis Amber, Rebar Rust, Survey Blue, Stop Red, Steel Navy and Chalk, with the page, panel, ink, muted, link and text tokens rederived from them), `theme.ts` (the storage key), `components/Brand.tsx` (Lucide `ClipboardCheck` in amber and the wordmark **PayrollCheck** in Instrument Sans semibold, with the "claims" tagline gone) and `components/Header.tsx` (the chip). Also `dashboard/index.html` (the title PayrollCheck) and `dashboard/public/favicon.svg` (a navy tile with an amber clipboard check).

Today's claim states take the case lifecycle's colours, in this order: waiting is Slate (as Received will be), in progress is Survey Blue, waiting for sign-off is Hi-Vis Amber (as Awaiting review will be), decided is Permit Green, and sent back is Rebar Rust (as Returned to sub will be). Left for a reviewer, Refused and Failed are Stop Red. The judge's grades are A Permit Green, B Survey Blue, C Hi-Vis Amber and F Stop Red. A diff's removed lines are tinted Stop Red and its added lines Permit Green.

**The chip.** "Synthetic data — not real rates" goes in the header band on every signed-in page and on the sign-in page, always visible, never hidden on a narrow window. The business date arrives in stage 6. The brief says this stage adds no new test, so the chip is checked in the browser, not by a new test.

### What doesn't change

Every module's job and dependencies, every route's behaviour, the API rules (an `operation_id`, a one-line docstring and no optional inputs on every operation, checked by `api_rules.py`), and the agent's API document, which keeps exactly the agent's six operations under their new names: `get_case`, `get_policy`, `get_case_history`, `calculate_payout`, `record_decision` and `pay_case`. Also every test's assertions, the coverage bars, the stand-ins, and policy, plan, payout and payment by name.

## Phase 1: Delete the course-only folders

Remove `community_contributions/`, `guides/`, `setup/` and `assets/` with `git rm -r`, and fix whatever pointed at them. The survey found nothing in `pyproject.toml`, `package.json`, `tsconfig.json`, `eslint.config.js`, Prettier's paths or `lefthook.yml`. Only `AGENTS.md`'s Folders section names them, and it becomes a line saying they're gone. `labs/` stays as it is. The commit holds the deletion and that one fix, nothing else.

- [x] `git ls-files community_contributions guides setup assets` lists nothing, and the four folders aren't on disk
- [x] `git grep -n -E 'community_contributions|guides/|(^|[^/])setup/|(^|[^a-z/])assets/'` outside `labs/` finds only `docs/ROADMAP.md`, `docs/stages/01_REBRAND.md` and the `/assets/` build path in `backend/tests/test_dashboard.py`
- [x] `git diff --stat main` shows only deletions under the four folders and `AGENTS.md`
- [x] `npm run check` is green with no `.env`, with the baseline's counts
- [x] Commit: "Delete the course-only folders"

## Phase 2: The product's name, the packages and the settings

UnderCover becomes PayrollCheck wherever it names the product: the agent's and the Copilot's instructions, the decision's maker, log lines, the agent API document's title, docstrings and comments, `runtime/`'s files, and the Copilot's name, "PayrollCheck Copilot", in code and copy. The dashboard's visible brand waits for phase 5. The packages become `payrollcheck` in `pyproject.toml` and `package.json`. `uv lock` and `npm install` then update `uv.lock` and `package-lock.json`, where only the name changes, and the plan checks that no package version moved. Every `UNDERCOVER_*` becomes `PAYROLLCHECK_*`, still read where it is read today, with the same default: `PAYROLLCHECK_API_KEY`, `_API`, `_AGENT`, `_AGENT_RUNTIME`, `_CONTEXT`, `_GATEWAY_URL`, `_MEMORY_ID`, `_COPILOT`, `_COPILOT_RUNTIME`, `_COPILOT_MEMORY_ID` and `_DB`. The search found exactly these eleven. The same goes for `playwright.config.ts`, the test fixtures and stand-ins that set them, and `agentcore/`. The schema, the SQLite files (`payrollcheck.db`, `e2e/payrollcheck.db`), the storage keys, the Gateway targets, the Memory names and the AgentCore project become `payrollcheck`, and seeding drops the retired `undercover` schema on Postgres.

The README's and AGENTS.md's env var names follow, since the rename breaks them. TECH_STACK, CODE_STANDARDS and PROCESS are rewritten in phase 5, and STATUS gets a line now saying the settings were renamed.

- [x] `git grep -n -i undercover` outside the exclusions, `labs/` and the target docs finds nothing in `backend/`, `agent/`, `context/*.py`, `runtime/`, `agentcore/`, `e2e/`, `dashboard/src/` apart from the brand components phase 5 replaces, `package.json`, `pyproject.toml` or the config files
- [x] `git grep -n UNDERCOVER_` outside `labs/`, the target docs and `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md` and `docs/PROCESS.md` (rewritten in phase 5) finds nothing
- [x] `git diff main -- uv.lock package-lock.json` changes only the project's own name
- [x] `uv run -m backend.seed` (no `.env`) builds `payrollcheck.db` and prints the same counts as before: 26 claims, now cases, 51 policies, 50 customers, now subcontractors, 3 handlers, now reviewers, 25 held-out and 50 decisions
- [x] A test-file diff through the phase's table leaves no differences
- [x] `npm run check` is green with no `.env`, with the baseline's counts and coverage of at least 80% for both languages
- [x] The phase's review by a fresh subagent finds nothing it would block the PR for
- [x] Commit: "Rename UnderCover to PayrollCheck: packages, settings and names"

## Phase 3: Claim becomes case, and the claim agent the payroll agent

The largest phase. With the table above:
- In the backend: the tables `claims`, `run_claims` and `held_out_claims` and every `claim_id` column; the routes under `/api/claims/...`, `/api/runs/{run_id}/claims` and `/api/customers/{id}/claims`; the twelve operation ids (`list_cases`, `get_case`, `get_case_history`, `start_case`, `pay_case`, `sign_off_case`, `send_back_case`, `take_case`, `record_case_heartbeat`, `fail_case`, `record_run_cases` and the others); the `Claim…` Pydantic models and `StrEnum`s; and `views.py`'s `to_claim` → `to_case`. Also `backend/instructions/claim.md` → `payroll.md`.
- In the agent: the graph, its nodes, its state and `PayrollContext`; the tools; the harness's `work_case`, `carry_on` and `work_in_run`; the dispatcher's `list_cases`; `app_terms.py`'s words; the Langfuse trace and session names; the context tool `get_case_rules`; and the Copilot's tools and instructions.
- In the dashboard: `ClaimPage.tsx` → `CasePage.tsx`, `ClaimLink.tsx` → `CaseLink.tsx`, `claimTesting.ts` → `caseTesting.ts`, `ClaimWork.test.tsx` → `CaseWork.test.tsx`, the route `/cases/:caseId`, and `api.ts`'s functions, one per operation and named after it. Copy says case. The Copilot's claim-ID linker becomes a case-ID linker, still matching `CLM-…`.
- In the tests: `test_claim_agent.py` → `test_payroll_agent.py`, `test_claims.py` → `test_cases.py`, `claim_requests.py` → `case_requests.py`, and the e2e specs' routes and copy.

The record IDs, the record contents and their keys, the claims manual's title and the JWT's claims stay.

- [x] `git grep -n -i -w -E 'claims?|claim_[a-z_]+|[a-z_]+_claims?'` with the camel and Pascal forms (`claimId`, `ClaimPage` and the like), outside the exclusions, `labs/` and the target docs, finds nothing but the listed exclusions. The search and what it finds go in the phase's commit message
- [x] `curl` against the backend started with `uv run -m uvicorn backend.main:app` on a fresh SQLite seed: `GET /api/openapi.json` lists no path or operation id with "claim", and `GET /api/agent/openapi.json` with the test key lists exactly `get_case`, `get_policy`, `get_case_history`, `calculate_payout`, `record_decision` and `pay_case`
- [x] The API-rules test (`backend/tests/test_openapi.py` and `api_rules.py`) passes unchanged except for renamed names
- [x] A test-file diff through the phase's table leaves no differences, and the test files moved with `git mv` (`git log --follow` on `test_payroll_agent.py` reaches the import commit; three heavily edited files, `payroll.md`, `case_requests.py` and `CaseLink.tsx`, fall below git's default similarity, so their history needs `git log --follow -M30%`)
- [x] pyright and ruff agree with every `case` used as a Python name, and no TypeScript identifier is named `case`
- [x] `npm run check` is green with no `.env`, with the baseline's counts and coverage of at least 80% for both languages
- [x] The phase's review by a fresh subagent finds nothing it would block the PR for, and checks every exclusion
- [x] Commit: "Rename claim to case and the claim agent to the payroll agent"

## Phase 4: The people: reviewers, the compliance manager and subcontractors

- `data/handlers.json` → `data/reviewers.json` with `git mv`, its key `handler_id` → `reviewer_id` (the IDs `HND-01` to `HND-03` stay), the roles "Compliance Manager" for Dana Whitfield and "Reviewer" for Marcus Oyelaran and Priya Raman, and the emails `dana.whitfield@payrollcheck.example`, `marcus.oyelaran@payrollcheck.example` and `priya.raman@payrollcheck.example`. `can_approve_over_limit` keeps its name and values.
- Handler → reviewer: the tables `handlers` and `handler_decisions`, `SignedIn`'s reviewer and `models.Handler` → `Reviewer`, `get_signed_in_reviewer`, `RequireReviewer`, `reviewer.ts`/`useReviewer`, `needs_a_reviewer.py`, `reviewer_answer.py`, `left_for_reviewer`, the note message "Dana Whitfield, a compliance manager, sent your decision back", the Copilot's memory namespace `("reviewers", …)`, `e2e/reviewers.ts`, `REVIEWER_PASSWORD`, the judge's request and rubric, and the "Signed in as" copy. The improver's views, such as `beside_handler`, follow.
- Senior handler → compliance manager: `senior(action)` → `compliance_manager(action)` and the copy that says "senior handler".
- Customer → subcontractor: the table `customers`, `subcontractor_id`, `backend/customers.py` → `subcontractors.py`, `/api/subcontractors`, `find_subcontractors`, `get_subcontractor`, the payroll agent's memory namespace `("subcontractors", …)`, the dashboard's panels and copy. The UI may say "sub", and code never does.
- `data/README.md`'s entry for `reviewers.json`, which this phase moves.

The Lambda handlers, Langfuse's and LangChain's callback handlers, LangGraph's `error_handler` and the record contents stay.

- [x] `git grep -n -i -E 'handler'` in the code finds only the listed entry points and library classes (the Lambda handlers, Langfuse's and LangChain's callback handlers, LangGraph's `error_handler`, MCP's `request_handlers`, LangChain's next-handler in `wrap_model_call`, httpx's mock handlers) and the lab's screening prompt; `git grep -n -i -E 'customer|senior'` in the code finds only the record-key map, the data file name `customers.json` and the screening prompt. Outside the code they remain in the record files, the context files and the docs phase 5 rewrites
- [x] `uv run -m backend.seed` prints the same counts under the new names, and `data/reviewers.json` holds the three people with the new emails and roles
- [x] `uv run pytest backend/tests/test_sign_in.py --no-cov` signs in by the new emails, and Marcus Oyelaran is still refused a sign-off over the limit
- [x] No identifier in Python or TypeScript is named `sub`, `subs` or `sub_id` (`git grep -n -w -E 'sub|subs|sub_id'` in code)
- [x] A test-file diff through the phase's table leaves no differences
- [x] `npm run check` is green with no `.env`, with the baseline's counts and coverage of at least 80% for both languages
- [x] The phase's review by a fresh subagent finds nothing it would block the PR for, and checks every exclusion
- [x] Commit: "Rename handler to reviewer, senior handler to compliance manager and customer to subcontractor"

## Phase 5: The brand and the docs

The brand, as in the design above: `styles.css`, `theme.ts`, `Brand.tsx`, `Header.tsx`, `index.html` and `favicon.svg`. Every hard-coded colour of the old palette goes, including those in SVG charts and the favicon. Then the docs:
- `docs/BRAND.md`: the settled colours and shades replace "(proposed)", and it gains the contrast table, the case lifecycle's status colours (already there) and how today's claim states and grades map onto the palette.
- `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md` and `docs/PROCESS.md`: the new names, the `PAYROLLCHECK_*` settings, the `payrollcheck` schema, `data/reviewers.json` and `REVIEWER_PASSWORD`. PROCESS's sign-in line names Dana Whitfield and Marcus Oyelaran from `data/reviewers.json`.
- `docs/STATUS.md`: stage 1 is built, and the product is described under its new names. Running it says to reseed after pulling, since the tables, the schema and the saved progress all changed, and to update the three users' emails in Supabase Auth and the `.env` keys. The earlier live runs keep their dates and figures but use the new names, with a note that they ran under UnderCover's.
- `data/README.md` follows the renamed files.
- `README.md` and `AGENTS.md`: only the names and links the rename broke, such as "Until stage 1 is built…".

One assertion changed in this phase, and only because the brand changes what it checks: `e2e/settings.spec.ts` checks that the chosen appearance applies by reading the page's background, so its two colours follow the new page colours, `#0B1724` (dark) and `#F2F4F7` (light), in place of `#04232E` and `#F0F4F5`. The test checks the same thing as before. This departs from "no assertion changes" in the brief and in "What doesn't change" above, which the brand's new colours can't meet for this test.

The brand and the docs are two commits.

- [x] `git grep -n -i -E 'sea-green|marigold|coral|cerulean|raspberry|midnight|sea-mist|#06d6a0|#073b4c|#ffc145|#ef476f|#118ab2|#f78c6b'` in `dashboard/` and `docs/` finds nothing, and neither does a search for `ShieldCheck` in the brand
- [x] Through the Playwright MCP server, on `npm run e2e`'s backend and dashboard, which need no `.env`, signed in as Dana Whitfield: the sign-in page, the queue, a case, the Scoreboard and the Settings, Improvement and Configuration pages show the navy band, the amber clipboard-check, the PayrollCheck wordmark and the chip, in light and dark mode, at 1,280 and 800 pixels wide, with no console errors or warnings. The chip is visible on the sign-in page too
- [x] A script in the page reads every element's computed text colour against its background, and every pairing of small text is at least 4.5:1 and every icon and large text at least 3:1, in both modes. It also finds no border on one edge only and no gradient fill
- [x] Money and IDs render in JetBrains Mono, checked on the queue and a case page
- [x] The final search across the repo, outside `labs/`, `docs/research/`, `docs/SPEC.md`, `docs/ROADMAP.md`, `docs/stages/`, `CONTEXT.md` and the record contents, finds no `UnderCover`, `undercover`, `UNDERCOVER_`, `claim` as our word, `handler` as a person, or `customer`, apart from the listed exclusions. The search and what it still finds are recorded in `STATUS.md`
- [x] `npm run check` is green with no `.env`, with the baseline's counts and coverage of at least 80% for both languages
- [x] The phase's review by a fresh subagent finds nothing it would block the PR for
- [x] Commits: "Apply the PayrollCheck brand" and "Describe the product under its new names"

## Phase 6: The live checks, then the review of the branch

These need the user's `.env`, with the renamed keys, and the three users' new emails in Supabase Auth. If either is missing at this point, implementation stops and asks. After one `npm run seed` on Supabase, which drops the `undercover` schema and builds `payrollcheck`, and with `npm run dev` running on the default models, through the Playwright MCP server (there was none in this environment, so these ran as Playwright scripts, with the user signing each reviewer in):

- [x] Dana Whitfield signs in with `dana.whitfield@payrollcheck.example`. The header shows the navy band, the amber clipboard-check, the PayrollCheck wordmark and the "Synthetic data — not real rates" chip, in light and dark mode, with no console errors
- [x] The queue lists 26 cases, each linking to `/cases/CLM-…`. A dispatch at N=3 works them all and its summary adds up as before: approved, declined and referred, with the payouts held for sign-off
- [x] A payout held for sign-off is signed off by Dana on its case page and paid once: one row in `payrollcheck.payments`, checked through the Supabase MCP server. Signed in as Marcus Oyelaran, the same kind of payout says he can't sign it off and shows no button
- [x] An evaluation of the evaluation set's five tiny cases appears on the Scoreboard with the same measures as before: decision accuracy, accuracy, cost of mistakes, straight-through, model cost and time per case, and the grade. The figures are compared with the last run's in `STATUS.md`
- [x] The Copilot sidebar says PayrollCheck Copilot and answers one question about a case, naming its ID. The sidebar's title is "Copilot", as it was on `main`; the name is in its instructions and docstrings, and the user accepted that
- [x] `uv run -m agent CLM-1001` works one case and prints its report line, after a second `npm run seed` the user agreed to, since the dispatch had already decided CLM-1001
- [x] Supabase holds the `payrollcheck` schema and no `undercover` schema, and no run is left running
- [x] What the runs spent, from the backend's records and the OpenRouter key's usage, goes in `STATUS.md`'s live run section

Then the whole branch is reviewed against `main` by a fresh subagent, as `docs/PROCESS.md` describes, with the exclusions list and the rename tables. The review checks every standard and that each exclusion is right. Whatever it would block the PR for is fixed, the tests the fixes touch are run, plus `npm run e2e` if they change the dashboard or the API, and the result is committed.

- [x] `npm run check` is green with no `.env` on the branch's last commit, with the baseline's counts
- [x] `docs/STATUS.md` records the live runs, the final search and what it still finds, and what the reviews found and changed
- [x] Commit: "Record stage 1's live checks"
- [x] The report to the user covers the search, what the runs spent, and what the reviews found and changed
