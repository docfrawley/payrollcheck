# Roadmap

PayrollCheck is built from Ed Donner's UnderCover `week3day5-end` (commit `ecca35dd`) in seven stages. Each stage has a brief in `docs/stages/`, and each one leaves a working app with `npm run check` green.

For each stage, in order:

1. "Please plan stage N from `docs/stages/NN_NAME.md`." The coding agent writes `docs/PLAN_NAME.md`, 5 or 6 phases as `docs/PROCESS.md` describes, against the code as it stands, and stops.
2. The user reviews the plan.
3. "Please implement the plan for stage N." The agent builds every phase, ticks the plan off and updates `docs/STATUS.md`.

Each stage has a GitHub issue that tracks it: plan written, plan reviewed, implemented, `npm run check` green.

| # | Stage | Brief | Plan | What it builds | What it removes |
|---|---|---|---|---|---|
| 1 | Rebrand | `docs/stages/01_REBRAND.md` | `docs/PLAN_REBRAND.md` | Deletes the course-only folders, then renames UnderCover to PayrollCheck vocabulary and applies the new brand, with behaviour unchanged | `community_contributions/`, `guides/`, `setup/`, `assets/` |
| 2 | Data & context | `docs/stages/02_DATA.md` | `docs/PLAN_DATA.md` | The generator, error manifest, committed data and labels, `copilot_expected.json`, and the new context layer and compliance context server tools. Additive only | none |
| 3 | Cases & checks | `docs/stages/03_CASES.md` | `docs/PLAN_CASES.md` | The new schema (including the overrides and notices tables) and seed (including the business date setting), CSV intake, check tools, the payroll agent and its draft notice, retuned screening, evaluations and the Scoreboard against labels, minimal queue and case pages | claims, policies, customers, payouts, payments, agent memory, the old context files |
| 4 | Review & access | `docs/stages/04_REVIEW.md` | `docs/PLAN_REVIEW.md` | Overrides, editing and sending notices through the outbox, reopening on resubmission, roles, project assignments and scoping | the over-limit flag (sending back to the agent goes in stage 3, with the paused graph) |
| 5 | Improver | `docs/stages/05_IMPROVER.md` | `docs/PLAN_IMPROVER.md` | Override signals, the judge's notice rubric, the four measures and the keep/rollback gate, ending with the development-set scoring run | the payout-explanation judge |
| 6 | Copilot | `docs/stages/06_COPILOT.md` | `docs/PLAN_COPILOT.md` | The business date in the header and on Settings, the Copilot's tools, exposure, withheld text and both layers of acceptance tests | the claim and payout tools and the sign-off card |
| 7 | Deploy | `docs/stages/07_DEPLOY.md` | `docs/PLAN_DEPLOY.md` | The Gateway policy for people's actions, the provisioning runbook and the smoke test on AWS | `labs/` |

Stage 3 is the heaviest: it's where the domain changes over, so the old claim code dies in the same stage that replaces it.

## The test rule, for every stage

- Tests move with their code. Stage 1 renames the tests and changes no assertions: everything green before is green after.
- From stage 2 on, a test for code that survives is adapted in the stage that changes that code, and a test for code that's replaced is deleted in the same commit as that code, with its replacement written in the same stage. A test is never deleted otherwise.
- The bars stay where `docs/PROCESS.md` sets them: 80% coverage for Python and TypeScript, tests on a stub model only, no network in `npm run check`, and never a lowered threshold, a turned-off rule or an excluded file to get a green run.
- The stand-ins stay, apart from the agent memory's, which goes with agent memory in stage 3.
- A Playwright spec is rewritten in the stage that changes its page.
- Live runs on a real model stay outside `npm run check`, as the briefs list them.

## Where the decisions came from

Every choice in these documents was made on the planning map, GitHub issue #1 in this repo, and its tickets, each with its reasoning in its resolution comment. If a stage turns up something undecided, raise it with the user rather than inventing an answer.
