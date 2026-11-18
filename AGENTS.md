# PayrollCheck

## The product

PayrollCheck checks the certified payrolls that subcontractors file on New Jersey public works jobs. It's built for Pinelands Builders, a fictional mid-size New Jersey general contractor. Its compliance reviewers work a queue of cases, one subcontractor's payroll for one project and one week, and the payroll agent checks every line of every payroll against the prevailing wage rules and writes an exception report. The agent flags; it never accepts. A reviewer signs off or sends back every case. There's also an improver that proposes better versions of the payroll agent, and the PayrollCheck Copilot, a chat for reviewers in the dashboard. It runs in production on AWS AgentCore.

PayrollCheck is built from Ed Donner's UnderCover `week3day5-end` (commit `ecca35dd`), in seven stages. Stage 1 renamed the code to PayrollCheck's words (case, reviewer, subcontractor, `PAYROLLCHECK_*`), stage 3 changed the domain over to payrolls, and stage 7 deployed it.

The user may be on Windows, where the terminal in VS Code is PowerShell, or on a Mac. Give commands that work on both.

## Start here

IMPORTANT: before you plan, build or change anything in the product, or answer questions about it, read each of these files in full:

1. `CONTEXT.md`: the words we use, in the code as well as the documents
2. `docs/SPEC.md`: what the business needs, end to end
3. `docs/ROADMAP.md`: the seven stages and the test rule for every stage
4. `docs/TECH_STACK.md`: the tech choices
5. `docs/CODE_STANDARDS.md`: how to write the code
6. `docs/PROCESS.md`: how to plan, build and check the work
7. `docs/BRAND.md`: the look
8. `docs/STATUS.md`: what's built so far and how to run it
9. The brief of the current stage in `docs/stages/`, and its plan in `docs/PLAN_<NAME>.md` once there is one

## Your role in the build

The documents in `docs/` are written as Pinelands Builders' own. The spec and the stage briefs come from their compliance manager. Treat them as the customer's requirements. The user directs the work and reviews your plans and builds. You plan, build and check the work as `docs/PROCESS.md` describes.

Write plans the user can review: say what each phase builds and why you chose that approach. Explain your work when they ask, at the level they ask for.

## The stages

Each stage has a brief in `docs/stages/`, listed in `docs/ROADMAP.md`. A stage goes in two steps, with the user's review in between:

1. "Please plan stage N from `docs/stages/NN_NAME.md`" writes the plan to `docs/PLAN_NAME.md`, and nothing else.
2. "Please implement the plan for stage N" builds every phase, ticks the plan off and updates `docs/STATUS.md`.

- Build only the stage you're asked for. `docs/SPEC.md` is where the stages lead, not a request to build ahead, even though you know what's coming.
- Each brief builds on the code as the previous stage left it. Where a brief's notes on the code don't match it, follow the brief's intent.
- Never create or delete AWS resources unless the user asks you to. Stage 7's provisioning runbook is a checklist the user runs, or explicitly asks you to run.
- Every choice in these documents was made on the planning map, GitHub issue #1 in this repo, and its tickets. If something is undecided, or the documents disagree, raise it with the user rather than inventing an answer.

Ed's day briefs and plans for UnderCover are no longer in `docs/`. This repo's first commit, `77cd362`, which imported Ed's `ecca35dd`, has them, if you need to see why the code is the way it is.

## Folders

- `docs/`: the product's documents. `docs/stages/` holds the stage briefs, and `docs/research/` the research behind the rules, such as `nj-prevailing-wage-rules.md`
- `backend/`, `agent/`, `dashboard/` and `e2e/`: the product
- `context/`: the context layer, the reference data the agent reads through the context server
- `runtime/` and `agentcore/`: the files for AgentCore Runtime
- `data/`: the business data, all of it synthetic
- `deploy/`: the provisioning runbook, which stands PayrollCheck up on AWS and Supabase from nothing, a step a command, with its checklist in `deploy/RUNBOOK.md`. Run it only when the user says so

Ed's notebooks, which the runbook was ported from, went in stage 7. The import commit has them, as `77cd362:labs/`: `git show 77cd362:labs/<file>` opens one.

Stage 1 deleted the course material that came with the code (`community_contributions/`, `guides/`, `setup/` and `assets/`). Nothing in the product depended on it.
