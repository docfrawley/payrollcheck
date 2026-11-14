# PayrollCheck, under its own name

From the compliance manager at Pinelands Builders, with our IT team.

## Where we're heading

We're turning the claims platform we were handed into PayrollCheck, a reviewer's tool for New Jersey certified payroll (`docs/SPEC.md`). The platform underneath is the one in this repo: the dispatcher, the screening, the evaluations and the Scoreboard, versioned configuration, the improver, sign-in, the agent's API key, the AgentCore app and the Copilot. Almost all of it stays.

Before we change what it does, we want it to speak our language. Today every file, table, route, environment variable and label says UnderCover, claim, handler and customer. Our glossary in `CONTEXT.md` says case, reviewer, compliance manager and subcontractor. If we change the words and the domain at the same time, nobody will be able to tell a broken rename from a broken feature, so this stage only renames. The app keeps working travel-insurance claims under the new names until stage 3 replaces them with payrolls. For one stage it will be PayrollCheck working travel cases, and that's expected.

The repo also still carries the course it came from. The folders that only teach go first, before the rename, so we don't rename what we're about to delete.

## What we want

1. **The course-only folders deleted first.** Remove `community_contributions/`, `guides/`, `setup/` and `assets/`, in a commit of their own, before any renaming. Then fix anything that pointed at them (links in `README.md`, `AGENTS.md` or `docs/`, entries in `pyproject.toml`, `package.json`, `tsconfig.json`, the ESLint or Prettier ignores) so `npm run check` is green on that commit alone. `labs/` stays exactly as it is, unrenamed: stage 7 ports its AWS and Supabase steps into a provisioning runbook and deletes it then.

2. **The brand.** UnderCover becomes PayrollCheck everywhere it names the product: the dashboard's title (`dashboard/index.html`), `Brand.tsx`, the header, the sign-in page, page titles, the agent's and Copilot's instructions, log lines, the API document's title, docstrings and comments. "UnderCover Copilot" becomes "PayrollCheck Copilot". The Python and npm packages are named `payrollcheck` (`pyproject.toml`, `package.json`, `uv.lock`, `package-lock.json`), and the AgentCore project in `agentcore/agentcore.json` and the names in `runtime/` follow the same rule, since nothing is provisioned on AWS yet.

3. **Environment variables.** Every `UNDERCOVER_*` becomes `PAYROLLCHECK_*`, with the same meaning and default: `PAYROLLCHECK_API_KEY`, `PAYROLLCHECK_API`, `PAYROLLCHECK_AGENT`, `PAYROLLCHECK_AGENT_RUNTIME`, `PAYROLLCHECK_CONTEXT`, `PAYROLLCHECK_GATEWAY_URL`, `PAYROLLCHECK_MEMORY_ID`, `PAYROLLCHECK_COPILOT`, `PAYROLLCHECK_COPILOT_RUNTIME`, `PAYROLLCHECK_COPILOT_MEMORY_ID`, `PAYROLLCHECK_DB`, and any other the search turns up. Each is still read in one place. Rename the user's own `.env` keys without printing their values, and update `playwright.config.ts` and the test fixtures that set them.

4. **Claim becomes case, in the plumbing.** Tables, columns, routes, operation ids, function and variable names, modules, components, test names and copy say case where they said claim: `claims` → `cases`, `run_claims` → `run_cases`, `held_out_claims` → `held_out_cases`, `claim_id` → `case_id`, `get_claim` → `get_case`, `ClaimPage` → `CasePage`, `/claims/...` → `/cases/...`, and so on. The claim agent becomes the **payroll agent** in names and copy (`claim_graph`, `ClaimContext`, `CLAIM_TOOLS`, `backend/instructions/claim.md` and the like). The record IDs (`CLM-1001` and the rest) and the stories inside the records don't change.

5. **The people.** Handler becomes **reviewer** throughout (`handlers` → `reviewers`, `handler_id` → `reviewer_id`, `RequireHandler`, `SignedIn`'s handler, `HANDLER_PASSWORD`, "Signed in as" copy and the rest). Senior handler becomes **compliance manager** in names and copy. `data/handlers.json` becomes `data/reviewers.json`, with the same three people and their emails moved to a PayrollCheck `.example` domain:
   - Dana Whitfield, compliance manager
   - Marcus Oyelaran, reviewer
   - Priya Raman, reviewer

   What each of them may do doesn't change in this stage: `can_approve_over_limit` keeps its name and meaning until stage 4 replaces it with roles.

6. **Customer becomes subcontractor.** Tables, columns, functions, routes, tools and copy that say customer say `subcontractor`. In code it is always `subcontractor`, never `sub` (`CONTEXT.md` explains why); "sub" is fine in UI copy only. The data about these people is still travel customers for now, under the new name.

7. **The words we leave alone.** Policy, plan, payout and payment have no PayrollCheck counterpart, so they keep their names in this stage, in code and copy alike. Stage 3 replaces them with projects, wage rates, filing rules, exceptions and shortfalls. Don't rename them to anything, and don't remove them.

8. **The new brand.** Apply the construction-compliance identity, keeping Ed's design system otherwise:
   - **Unchanged:** the fonts (Instrument Sans and Serif, JetBrains Mono), the surfaces and panel rules, Lucide icons, the "Avoid" list and the header band's layout.
   - **Palette:** Steel Navy `#12263A` (ink and the header band), Hi-Vis Amber `#F5A524` (primary: the mark and key actions), Survey Blue `#2D7DD2` (information), Permit Green `#2E9E6A` (accepted, clean), Rebar Rust `#C4572A` (medium severity), Stop Red `#D7263D` (high severity and screening flags). Amber is too bright for small text, so it's darkened there; check the contrast of every pairing you use.
   - **Mark:** Lucide `clipboard-check` in amber on the navy band, in place of the shield. The wordmark is **PayrollCheck** in Instrument Sans semibold.
   - **Header chip:** "Synthetic data — not real rates", on every signed-in page and the sign-in page, always visible.
   - **Tone:** plain and exact, never alarmist. Money and IDs in JetBrains Mono.

   `docs/BRAND.md` already holds all of this (it replaced the Sea Green palette and the shield when the doc set landed). Check its proposed colours for WCAG AA contrast, settle any that fail with the user, then apply it in `dashboard/src/styles.css`, `theme.ts`, `Brand.tsx` and `Header.tsx`. The status colours for the case lifecycle (Received grey, In progress blue, Awaiting review amber, Accepted green, Returned to sub rust) go into `docs/BRAND.md` now, for the stage that brings those statuses; today's claim states map onto the new palette however reads best.

9. **Our how-we-build docs.** `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/STATUS.md` use the new names, the new env vars and `data/reviewers.json`. `PROCESS.md`'s sign-in line names Dana Whitfield and Marcus Oyelaran from `data/reviewers.json` and the renamed password variable. `STATUS.md` says stage 1 is built and describes the product under its new names. `data/README.md` follows the renamed files. Leave `docs/SPEC.md`, `docs/ROADMAP.md`, `CONTEXT.md` and `docs/research/` as they are: they already describe the target.

## Our IT team's choices

- **Mechanical, and checked as mechanical.** Behaviour is unchanged. Every test that was green before is green after, and no assertion changes: a test changes only where a name it uses changes. Run the whole of `npm run check` before you start and record the result in the plan, so "green before" is a fact and not a memory.
- **Tests move with their code.** A test file is renamed with the module it tests (`agent/tests/test_claim_agent.py`, `backend/tests/test_claims.py`, `dashboard/src/ClaimWork.test.tsx`, `claimTesting.ts`, `e2e/handlers.ts` and the rest). The Playwright specs in `e2e/` are renamed with their pages and keep every step and check.
- **Not every match is ours.** A plain search-and-replace would break things that only share the word:
  - the Lambda handlers (`handler` in `backend/main.py` and `context/server.py`, and `backend.main.handler` in the deployment notes), LangGraph's `error_handler`, and event handlers in the dashboard are not reviewers;
  - a JWT's claims in `backend/auth.py` are not cases;
  - `case` is a reserved word in TypeScript, so a variable that held a claim needs a name such as `caseRecord` there. In Python it's a soft keyword and fine as a name, but check pyright and ruff agree.

  The plan lists the exclusions it finds before it renames, and the review checks them.
- **The database is rebuilt, not migrated.** `npm run seed` drops and recreates everything as it does today, so renamed tables need no migration. On Supabase, seeding drops the old-named tables too, as it dropped the to-do table once.
- **The data files.** `data/handlers.json` becomes `data/reviewers.json`. Whether the record files that stage 3 deletes (`data/claims.json`, `data/customers.json`, `data/security/`, `data/evals/`) and the keys inside them are renamed now or read under their old names until then is the plan's choice. Either way the records' contents and IDs don't change, no score changes, and you may open `data/evals/` only to rename.
- **Checkpoints and saved state.** Renamed graph nodes, state keys and thread names make old saved progress unreadable. That's fine: reseeding clears it. Say so in `STATUS.md`'s Running it section.
- **Git history.** Use `git mv` for renamed files so history follows them, and commit the folder deletions, the code rename and the brand in separate commits.

## What stays the same

- What the app does, page by page and route by route: dispatches, screening, sign-off and payment, send-back to the agent, evaluations and the Scoreboard, the improver, Settings and the Copilot.
- The labelled sets, their measures and every score.
- The API rules in `docs/TECH_STACK.md`: every operation has an `operation_id`, a one-line docstring and no optional inputs. The agent's API document still has exactly the agent's operations, under their new names.
- Policy, plan, payout and payment, by name.
- `labs/`, unrenamed and unopened.
- Tests never call a model, `npm run check` never reads `.env`, and the code follows `docs/CODE_STANDARDS.md`.
- Everything works on Windows too (`docs/PROCESS.md`).
- Nothing in this stage touches AWS.

## What done looks like

- `npm run check` is green with `.env` moved out of the way, at the end of every phase, and the same tests pass as before the stage, with the same assertions. Coverage is still at least 80% for Python and TypeScript.
- `community_contributions/`, `guides/`, `setup/` and `assets/` are gone, and nothing refers to them.
- A search of the repo, outside `labs/`, `docs/research/`, `docs/SPEC.md`, `docs/ROADMAP.md`, `CONTEXT.md`, the record contents and Ed's historical briefs and plans in `docs/` (which a later stage deletes), finds no `UnderCover`, `undercover`, `UNDERCOVER_`, `claim` (as our word), `handler` (as a person) or `customer`, apart from the exclusions the plan lists. Report the search and what it still finds.
- After one `npm run seed`, with `npm run dev` running and the default model, checked through the Playwright MCP server:
  - Dana Whitfield signs in with her new email from `data/reviewers.json`; the header shows the navy band, the amber clipboard-check, the PayrollCheck wordmark and the "Synthetic data — not real rates" chip, in light and dark mode.
  - The queue lists the cases under `/cases/...`; a dispatch at N=3 works them as before; a payout held for sign-off is signed off by Dana and paid once; Marcus Oyelaran still can't sign it off.
  - An evaluation of the evaluation set's five tiny cases appears on the Scoreboard with the same measures as before.
  - The Copilot sidebar says PayrollCheck Copilot and answers one question about a case.
  - `uv run -m agent CLM-1001` still works one case.

  Report what the runs spent.
- `docs/BRAND.md`, `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md`, `docs/STATUS.md` and `data/README.md` describe the product under its new names.

## Not for now

- Any change of behaviour, any new feature, any new test.
- Replacing policy, plan, payout or payment (stage 3).
- Roles and project assignments in place of `can_approve_over_limit` (stage 4).
- Rewriting `README.md` and `AGENTS.md` for the product, beyond fixing the links and names the rename breaks.
- Renaming or deleting `labs/` (stage 7).
- Creating anything on AWS or Supabase.

## Planning

Follow `docs/PROCESS.md`, but write this plan to `docs/PLAN_REBRAND.md` and tick it off there. Plan five or six phases and commit at the end of each. Start by running `npm run check` and recording it. Then delete the course folders, then the env vars and package names, then claim → case and the payroll agent, then handler → reviewer, senior handler → compliance manager and customer → subcontractor with `data/reviewers.json`, then the brand and the docs. Do the live checks last, after reseeding once.
