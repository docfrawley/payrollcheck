# Plan: stage 3, Cases & checks

From `docs/stages/03_CASES.md`. This is the stage where the domain changes over. The travel claims, policies, payouts and payments go. In their place come Pinelands Builders' projects, subcontractors, workers and certified payrolls:
- loaded by seeding from stage 2's committed output
- uploaded by reviewers as CSVs
- checked line by line by the payroll agent through eight deterministic check tools
- scored against stage 2's labels, strictly, to the cent

The agent flags; it never accepts. Every case it works ends Awaiting review, and a reviewer signs it off or sends it back.

The work happens on a branch, `stage-3-cases`, cut from `stage-2-data`, with a commit at the end of every phase.

## The baseline: `npm run check` before the stage

On `stage-2-data` at `452d481`, with no `.env`:
- ruff and pyright are clean, and pytest passes 1,276 at 99.5% coverage.
- The server, context and runtime import checks exit 0.
- Prettier, ESLint and tsc are clean, and vitest passes 178.
- Playwright passes 30.

Every phase ends with `npm run check` green and coverage of at least 80%. Tests are deleted only with the code they test, and each one's replacement is written in the same phase (the test rule in `docs/ROADMAP.md`).

## Decisions

### Taken with the user while planning

1. **The check tools run in the payroll graph's code, in order, before the model.** A `check` node runs all eight on the latest submission and records each one's candidate findings with the app as a step. The model then judges the findings and writes the report and the notice. This follows `docs/CODE_STANDARDS.md` rule 14: what must always happen, in a fixed order, is code. It also saves eight model round trips on every case. The instructions still tell the agent that every exception rests on a check tool's finding or a rule it can cite.
2. **Until stage 4, an upload for a case that already exists is refused.** Intake answers 409, naming the case, and changes nothing. Stage 4 replaces this with reopening.
3. **Until stage 5, improvement rounds compare the catch rate, cost and time.** The rule reads the catch rate where it read accuracy, and compares cost and time per case as before. The judge isn't called and the grade isn't required. Rounds still run and can keep a version.
4. **Any signed-in reviewer can Sign off and Send back.** `can_approve_over_limit` still gates Settings, starting and stopping rounds, and reviewing proposals, until stage 4 makes it the compliance manager's role.

### Carried from stage 2

5. **Week 12 has 22 Received cases and 2 missing filings, not 24 cases** (stage 2's decision 1). Wherever the brief says 24 week-12 cases, this plan means the 22.
6. **The labels belong to each case's first submission** (stage 2's decisions 2, 4 and 5). Timeliness is judged on each submission's own received date.

### Choices this plan makes, for your review

7. **What an evaluation copy holds.** A copy holds the submissions a case received before anyone reviewed it:
   - a history case: its first submission, the one the labels describe
   - a week-12 case: every submission it has (PC-1206, the resubmission decoy, has two)

   The agent checks the copy's latest submission, as on any case.
8. **A copy's history comes from its own set.** `get_payroll_history` for a copy reads the earlier payrolls of its labelled set: the latest submission of each earlier week of the same subcontractor and project, which is how stage 2's rule audit reads last week. It never reads the queue. The set's payroll records hold nothing from the labels, and only scoring reads the labels.
9. **The held-out world's projects, subcontractors and workers sit in the same tables as the development world's, marked `held_out`.** That way a held-out copy's `get_project` works like any other. Every list a person or the Copilot sees leaves them out, so PRJ-51 and PRJ-52 never reach the queue or the Copilot's expected answers.
10. **The seeded history's exceptions come from the labels.**
    - Each is raised by the reviewer who decided the case, with the severity and citation from the backend's rule catalogue.
    - `expected` and `actual` are empty, since seeding recomputes nothing.
    - On a corrected case they are superseded. On a case still Returned to sub they are open, so PC-0311 has its three.
11. **Two small generator changes**, both covered by stage 2's determinism test, with the labels unchanged:
    - Each engagement in `world.json` gains its pair's number (`pair`), so the app can make an uploaded case's id `PC-WWPP` as the generator does.
    - The two missing filings' payrolls are written to `data/development/arrivals/` (`PC-1214-1.csv` and `PC-1223-1.csv`), which seeding doesn't load. They are the CSVs the upload check and its end-to-end test upload.
12. **An upload goes to a project's page**, `POST /api/projects/{project_id}/payrolls`, and a file whose `project_id` names a different project is refused: "This payroll is for PRJ-02, not PRJ-01." This is the brief's "unknown project" refusal read against the page it's uploaded to, so stage 4's scoping can find the project from the path. An uploaded submission is received on the business date.
13. **The Copilot until stage 6.**
    - **Pointed at the new records:** `list_cases`, `get_case`, `list_steps`, `find_subcontractors`, `get_subcontractor`, `get_latest_dispatch`, `list_evaluations`, `get_settings`, `start_dispatch`, `start_evaluation`, `wait_for_run` and `what_needs_a_reviewer`. The last now lists the cases Awaiting review, those with a screening flag and those the agent failed.
    - **Context tools:** the five payroll lookups replace the seven travel ones, on the same route.
    - **Switched off, with their code and tests:** `get_policy`, `send_back_case`, `check_success_criteria` (`criteria.py` and the `report_criteria` node, since the payouts over the limit it counts are gone) and the sign-off card (the `sign_off_case` schema, the `check_sign_off`, `confirm`, `sign_off` and `cancelled` nodes, `pause_turn`, `answer_confirmation`, the card's fill-in and `ConfirmationCard`).

    The roadmap lists the sign-off card for stage 6. It goes now because the held payouts it confirmed are gone, and pointing it at cases would let the Copilot accept a case, which `docs/SPEC.md` forbids. Stage 6 builds the new criteria and tools.
14. **The judge isn't called until stage 5.** `backend/judge.py`, its tests and its stand-in stay as they are, for stage 5 to repurpose. `finish_run` no longer grades, and the `grades` table and the grade's columns and chips go with the explanation they graded.
15. **The business date is a column of the settings**, `business_date`. Empty means the real date, and seeding sets 2026-11-23. `backend/business_date.py` resolves it. The Settings page carries it through a save unchanged and doesn't show it until stage 6.
16. **The tunable parameters are a JSON column on each version**, `parameters`. Version 1 has `{"rounding_tolerance_cents": 0}`: a line's shortfall or arithmetic difference at or under the tolerance is no finding. A run's payroll agents read the parameters from the run's version, and an improver's change copies them from its base until stage 5 lets it propose them.
17. **The rule catalogue is the backend's**, `backend/rule_codes.py`: the 15 codes, each with its check, its severity, whether it carries money, and what a seeded exception cites.
    - The backend fills in each candidate's severity as it records it, so the check tools never state one.
    - The agent knows the codes as the app's words, in `agent/app_terms.py`.
18. **The payroll agent's memory goes**, as the brief says:
    - removed: `agent/memory.py`, its stand-in, `PAYROLLCHECK_MEMORY_ID`, the memory statements in `runtime/policy.json` and the setting in `agentcore/cdk/lib/cdk-stack.ts`
    - kept: the Copilot's memory and `agent/agentcore_memory.py`
19. **The rate logic travels with the agent.** The check tools import `context/wage_rules.py` and `context/registrations.py`. So the AgentCore package stages those two files and `context/__init__.py` beside `agent/` (`cdk-stack.ts`'s staging), and the backend's package needs nothing from `context/`, since the backend does no rate arithmetic. This settles what stage 2 left open.

## Design

### How a case is worked

1. A dispatch, or an evaluation, lists the cases to work: the Received ones, and any left In progress by a stop.
2. `work_in_run` starts or carries on each one.
3. The graph runs these nodes in order:
   - **`screen`**: the second model reads every text cell of the latest submission. If it finds an instruction, `flag` records `record_screening_flag(reason)`, the case goes to Awaiting review with `screening_flag` set, and the graph ends. The payroll agent's model never sees the case.
   - **`check`**: fetches what the checks read on the agent's route, runs the eight checks in order, and records each one's findings with `record_check_findings`. The backend keeps them as the attempt's candidates and returns them with ids and severities. Each check is a step on the case.
   - **`agent`** and **`tools`**: the model reads the candidates, may read the case, the project, its subcontractors, the payroll history and the five lookups, and ends by calling `record_exception_report`. That call takes the exceptions it raises, the candidates it dismisses with reasons, and the draft notice. The backend checks the report against the attempt's candidates, records it and moves the case to Awaiting review.
4. A model that ends without a report fails the attempt. A case failed twice reaches Awaiting review with `agent_failed`.

### The guarantee, in code

`record_exception_report` refuses the report with a 422 when any of these holds:
- an exception with a `shortfall_cents` matches no candidate of this attempt with the same rule, worker, line and shortfall
- a candidate is neither raised nor dismissed
- a dismissal has no reason
- an exception names a rule outside the catalogue
- the report has exceptions but a blank notice

It refuses a case that isn't In progress with a 409. The model may raise an exception with no money that no tool found, such as `form.project_mismatch` or a `classification.changed` it judges a note doesn't explain. This works as an approval matching its calculation does today: the candidates are kept per attempt, on the attempt's thread.

### The modules

| Module | Its one job |
|---|---|
| `agent/checks/__init__.py` | The eight check tools in order, each a name and a function. |
| `agent/checks/inputs.py` | `CheckInputs`, everything the checks read, as plain data: the latest submission's certification and lines, the project and the engagement window, the subcontractor's record, the earlier payrolls, each day's required rate with the craft's rules, the registration on each work date, each apprentice's registration and level on each work date, and the filing rules. |
| `agent/checks/findings.py` | `Finding`: rule, worker, line, expected, actual, shortfall in cents and citation, and how a citation names a rate row, a registry record or a filing rule. |
| `agent/checks/form.py`, `registration.py`, `rates.py`, `overtime.py`, `arithmetic.py`, `apprentices.py`, `timeliness.py`, `classification.py` | One check each, a pure function of `CheckInputs` and the version's parameters, computing with `context/wage_rules.py` and `context/registrations.py`. |
| `agent/check_inputs.py` | Fetches `CheckInputs` for a case on the payroll agent's route: the app's reads and the context layer's lookups, each lookup asked once. |
| `agent/tools.py` | The model's tools: `get_case`, `get_project`, `list_subcontractors`, `get_payroll_history`, the five lookups and `record_exception_report`, each filling in the case from `PayrollContext`. |
| `agent/harness.py` | The payroll graph: `screen`, `flag`, `check`, `agent` and `tools`, with no pause, no payment and no memory. |
| `agent/screening.py` | The screening, retuned for payrolls: its instructions, and the submission's text cells as it reads them. |
| `backend/database.py` | The tables and every query. |
| `backend/seeding.py` | Seeding: loads stage 2's committed output, the labels and the settings, recomputing nothing. Moved out of `database.py`, which keeps the tables. |
| `backend/rule_codes.py` | The rule catalogue. |
| `backend/business_date.py` | The business date in force: the setting, or the real date. |
| `backend/candidates.py` | A check's candidate findings, kept for the case's current attempt. |
| `backend/reports.py` | An exception report checked against the attempt's candidates and recorded with its notice. Replaces `records.py` and `calculation.py`. |
| `backend/intake.py` | An upload turned into a submission, or refused with its reason. |
| `backend/projects.py` | An `APIRouter`: `list_projects`, `get_project`, `list_subcontractors` and the upload. |
| `backend/history.py` | A case's payroll history, from the queue or from a copy's own set. |
| `backend/copies.py` | An evaluation's copies of a labelled set's cases, with the submissions before review. |
| `backend/scoring.py` | Rewritten: the strict matching rules and an evaluation's measures, pure. |
| `backend/scoreboard.py` | Reads the evaluations' copies and their labels, and scores them. |
| `data/payroll_world/template.py` | Gains the strict reader intake uses, `read_upload`, which refuses with a reason. The generator's `read_payroll` is built on it. |
| `dashboard/src/pages/ProjectsPage.tsx`, `ProjectPage.tsx` | The projects, and a project with its subcontractors, their engagement windows and the upload. |
| `dashboard/src/pages/CasePage.tsx` and its components | The case: its submissions, exceptions, screening, the agent's steps beside the checks' findings, the notice, Sign off and Send back. |

The dependencies run one way:
- `agent/checks/` imports `context.wage_rules` and `context.registrations` and nothing else of the agent.
- `check_inputs.py` uses the route, as the tools do.
- The backend imports `data.payroll_world.template` for intake and nothing from `context/`.
- `data/` imports nothing from the app.

`api.py`, `routes.py`, `gateway.py`, `direct.py` and `mcp_tools.py` keep their jobs, and the Gateway's target names don't change.

### The schema

Money is in integer cents and hours are exact decimals, held as strings in JSON.

| Table | What it holds |
|---|---|
| `projects` | `project_id`, name, county, location, public body, contract number, award date, `held_out` |
| `engagements` | `project_id`, `subcontractor_id`, `pair` and the first and last week ending: the subcontractors on each job and their engagement windows |
| `subcontractors` | `subcontractor_id`, legal name, FEIN, registration number, payroll contact (name and email), `held_out` |
| `workers` | `worker_id`, name, `subcontractor_id`, established craft and classification, `held_out` |
| `cases` | `case_id`, `subcontractor_id`, `project_id`, `week_ending`, `status`, `screening_flag`, `screening_reason`, `agent_failed`, `latest_submission_no`, `thread_id`, `attempts`, `evaluation_id`, `copy_of`, and for history `reviewed_by` and `reviewed_on`. A partial unique index covers the subcontractor, project and week ending where `evaluation_id` is null, so a copy can sit beside its original. |
| `submissions` | `(case_id, submission_no)`, `uploaded_by`, `uploaded_at`, `received_on`, `file_name`, `payroll_no`, `wage_payment_date`, `certification` and `lines` as JSON, never updated |
| `candidates` | `candidate_id`, `case_id`, `thread_id`, `submission_no`, `check`, the finding's fields, `severity`, and the dismissal's reason once a report dismisses it |
| `exceptions` | `exception_id`, `case_id`, `submission_no`, `rule`, `severity`, `worker_id`, `line_no`, `expected`, `actual`, `shortfall_cents`, `citation`, `raised_by`, `candidate_id` when a check found it, `status` (open, dismissed, superseded) |
| `overrides` | `override_id`, `exception_id`, `case_id`, `submission_no`, `kind`, `reviewer_id`, `reason`, `created_at`. Created empty; stage 4 fills it. |
| `notices` | `case_id`, `submission_no`, `draft`, `drafted_by`, `drafted_at`, and empty until stage 4: `edited_text`, `edited_by`, `edited_at`, `sent_by`, `sent_at` |
| `labelled_cases` | Each labelled set's cases, `(labelled_set, case_id)`, with their project, subcontractor, week ending, `tiny`, and their submissions as the generator wrote them: the development set's 207 and the held-out set's 98 |
| `labels` | `(labelled_set, case_id, rule, worker_id, line_no, expected_shortfall_cents)`, and the expected screening flags as rows with the rule `screening` |
| `settings` | As today, without `approval_limit` and with `business_date`. The measures are `catch_rate`, `cost_per_case` and `seconds_per_case` (decision 3). |
| `versions` | As today, with `parameters` |

**Gone:** `policies`, `held_out_cases`, `reviewer_decisions`, `decisions`, `sent_back_decisions`, `calculations`, `payments`, `payout_rules`, `documents` and `grades`, and the `resume_heard_at` column.

**Statuses:** `received`, `in_progress`, `awaiting_review`, `accepted` and `returned_to_sub`, shown as Received, In progress, Awaiting review, Accepted and Returned to sub.

**Step kinds:** `screening`, `check`, `tool_call`, `tool_result`, `message`, `lookup`, `refusal` and `error`.

### The operations

**The payroll agent's API document** has exactly the seven operations its route calls:
- `get_case`: the case, its latest submission, and each worker on it with their established craft
- `get_project`
- `list_subcontractors`: the project's subcontractors, their legal names and engagement windows
- `get_payroll_history`
- `record_check_findings`
- `record_screening_flag`
- `record_exception_report`

**The bookkeeping** goes straight to the app with the key, as now: `start_case`, `record_step`, `record_model_call`, `record_work_time`, `fail_case` and the run operations.

**Removed:** `get_policy`, `get_case_history`, `calculate_payout`, `record_decision`, `pay_case`, `hold_payment`, `take_case`, `record_case_heartbeat`, `count_payouts_over_limit`, `answer_confirmation` and `pause_turn`, with the agent's `resume_case` operation.

### Scoring

All matching is on an evaluation's copies, on each copy's latest submission:
- **Caught:** a label is caught by an open exception on its copy with the same rule code, exactly, and the same worker (both null for a case-level rule). The line isn't compared.
- **Shortfall correct:** a caught label's shortfall is correct when the exception's `shortfall_cents` equals the label's.
- **Screening:** a screening label is caught when its copy's `screening_flag` is set. Every exception on a flagged copy is false.
- **False exception:** an open exception matching no label, one on a decoy included.

An evaluation's measures:
- catch rate: exception labels caught ÷ exception labels
- false exceptions, in all and per 100 copies
- shortfall accuracy: caught money labels with the right shortfall ÷ caught money labels, or nothing when none was caught
- screening flags caught, of those expected
- model cost per case, seconds per case and the run's seconds

Stage 5 settles whether screening joins the catch rate.

## Phases

### Phase 1: the check tools and the CSV reader

Built first because both are pure, deterministic and additive: nothing in the travel domain changes, and the riskiest part of the stage, finding the labels to the cent, is proved before anything is wired to it.

- `agent/checks/`, as in the design. Each check implements its rules as `docs/research/nj-prevailing-wage-rules.md` and `context/filing_rules.yaml` state them, computing every amount with `context/wage_rules.py`:
  - **Rates:** the line's required wage and fringe for each work date, an apprentice's by `apprentice_rate` from the journeyman row, with `fringe_rate + fringe_cash` counting toward the fringe.
  - **Overtime:** `premium_split` with the weekly floor, and `overtime_shortfall`.
  - **Arithmetic:** the hours against `total_hours`, and gross against `wage_rules.gross`.
  - **Apprentices:** registration and level on each work date by `registrations.level_on`, and the ratio by `ratio_allows`.
  - **Timeliness and sequence:** received more than `due_days` after the wage payment date, and the payroll number against its week in the engagement window.
  - **Classification:** a lower-paid craft than the established one, with the shortfall to the established craft's rates, and a change from last week's latest submission.
  - **Form:** each required certification field filled and signed, and the contractor's name against the subcontractor's legal name.
- `get_wage_rate`'s answer gains the craft's whole entry, its name and statewide flag included, so a check builds the craft's rules with `wage_rules.craft_rules` unchanged.
- `data/payroll_world/template.py` gains `read_upload(text) -> Payroll`, raising `Unreadable` with a reason for:
  - no header row
  - a missing column, named
  - certification columns that differ between rows, named
  - a number or date that won't parse, naming the row and column
  - a `no_work_week` that isn't `true` or `false`

  `read_payroll` is built on it.
- The generator's two changes from decision 11, regenerated and committed.
- `agentcore/cdk/lib/cdk-stack.ts` stages `context/__init__.py`, `wage_rules.py` and `registrations.py` beside `agent/`.

Success criteria:
- [x] `uv run pytest agent/tests/test_checks.py --no-cov` passes, built from the committed records and the context layer's lookups called in process, for both labelled sets:
  - every label of each check's rules found on its case, with its worker, line and shortfall to the cent
  - on every other payroll, correction and decoy, no finding but one each on the two decoys that need judgment: the classification change with a valid note (`classification.changed`) and "Garden St. Electric" (`form.project_mismatch`)
  - the pre-listed Middlesex increase applied from 2026-10-01, and the later determination ignored, shown by the rate-increase-week and later-determination decoys
- [x] A unit test for each check on hand-made inputs (committed payrolls edited by hand), covering each finding's citation (the determination id and row, the registry record, the filing rule) and the rounding tolerance: a difference of 1 cent found at a tolerance of 0 and not at 1.
- [x] `uv run pytest data/tests/test_template.py --no-cov` passes, including an accept/reject table for `read_upload`: each refusal with its reason, and accepted files that break rules (blank FEIN, unsigned, bad arithmetic, a late wage payment date, a No Work Week row).
- [x] `npm run generate` leaves no change after the commit, and `data/tests/test_determinism.py` passes. The labels in `data/evals/` are byte for byte the same as before the phase.
- [x] `npm run check:runtime` and `npm run check:context` exit 0, and `context/tests/test_payroll_files.py` covers the craft entry in `get_wage_rate`'s answer.
- [x] `npm run check` is green.

### Phase 2: the change-over, from records to the case lifecycle

The seed replaces the records that every part of the app reads, so the backend, the agent, the Copilot's tools and the pages that read them change together. The travel domain goes in this commit, with everything that reads it. This is the stage's largest phase.

**The records and the seed:**
- The schema in the design.
- `backend/seeding.py` loads:
  - `data/development/` and the held-out world from `data/held_out/`, with every submission's CSV read by `template.read_payroll`
  - each history case's status, received dates, reviewer and outcome
  - the history's exceptions from the labels (decision 10)
  - the 22 Received week-12 cases
  - the labelled sets and labels from `data/evals/`
  - the business date 2026-11-23
  - version 1's parameters

  `data/reviewers.json` keeps its three people.
- **Removed:** the travel records in `data/` and `data/security/` with `data/README.md`'s section on them, the old files in `data/evals/` (named in `database.py`'s `LABELED_SETS` and `HELD_OUT_CASES`), `data/company.json`, `context/files.py` with its seven files and tools, `backend/context_files.py`, `documents.py`, `payout.py`, `calculation.py`, `records.py` and `sent_back.py`.

**The lifecycle:**
- `start_case` moves Received to In progress.
- `record_check_findings` and `record_screening_flag`.
- `record_exception_report` with the guarantee, moving the case to Awaiting review and writing the draft notice to `notices`.
- `fail_case` puts the case back to Received, or after its second attempt sets `agent_failed` and moves it to Awaiting review.
- `sign_off_case` and `send_back_case`:
  - each for any signed-in reviewer and never the key
  - each by a conditional update, so of two at once one goes through
  - Sign off refused with a 409 while any exception on the latest submission is open, saying how many
  - Send back to Returned to sub, with no note
- Reads:
  - `list_cases` and `get_case`, with its submissions, exceptions, candidates, screening and notice
  - `list_projects`, `get_project` and `list_subcontractors`, none listing a held-out record
  - `get_payroll_history`
  - `list_steps`
- `get_agent_api` has the seven operations.

**The payroll agent:**
- The graph in the design, with the `check` node wiring phase 1's checks through `check_inputs.py`, and the version's parameters in `PayrollContext`.
- Removed: `pay`, `wait_for_reviewer`, `resume`, `remember`, `reviewer_answer.py`, `memory.py` and their tests (`test_pause.py`, `test_send_back.py`, `test_memory.py`, `held.py`, `memory_stand_in.py`).
- `backend/instructions/payroll.md` is rewritten as goals (phase 4 refines them):
  - its goal: every rule breach and nothing that isn't one
  - what it works from
  - that code computes every amount
  - the judgments it makes
  - the notice it writes
  - that a payroll's text is the subcontractor's
- `agent/screening.py` reads every text cell of the latest submission, with instructions for payrolls.
- The dispatcher lists Received and In progress cases.
- `agent/work.py` and the entry point lose the resume.
- `uv run -m agent PC-1201` works one case.

**Evaluations:**
- `start_evaluation` takes the development, held-out or tiny set and makes copies through `copies.py` (decision 7).
- `backend/scoring.py` and `scoreboard.py` score them strictly.

**The improver's bridge** (decision 3):
- `verdict.py` compares `catch_rate`, cost and time, and no longer requires a grade.
- The improver's view gives the current version's scores and the development evaluation's misses and false exceptions, by case, in place of the reviewers' reasons.
- `improver.md` and `recipe.md` are adjusted only to name the new measures.

**The Copilot** as decision 13 says, and the context tools both agents share are the five payroll lookups.

**The dashboard**, against the new records:
- **The queue:** a tile for each status in `docs/BRAND.md`'s order and colors, and a line for each case with its subcontractor, project, week ending, status and flags.
- **A minimal case page:** its submissions, exceptions with citations, screening, steps and notice, with Sign off and Send back.
- **The dispatch panel:** its summary counts Awaiting review with exceptions, clean, flagged, agent failed and unfinished.
- **The Scoreboard:** the new measures.
- **The Improvement and Configuration pages:** the catch rate where they showed accuracy, with no grade.
- **Settings:** the new measures, with no approval limit.
- **The sidebar:** no confirmation card.

The components and tests of the travel pieces go with them (`Approval`, `DecisionDetails`, `DecisionPanel`, `PolicyPanels`, `SendBackForm`, `SentBackDecisions`, `SignOffForm`, `ConfirmationCard`, `Judging`, `SendBack.test.tsx` among them). The Playwright specs for the changed pages are rewritten: `agent.spec.ts`, `send_back.spec.ts`, `run.spec.ts`, `pages.spec.ts`, `scoreboard.spec.ts`, `starts.spec.ts`, `improvement.spec.ts`, `settings.spec.ts` and `copilot.spec.ts`'s sign-off tests.

Success criteria:
- [x] **The seed** (`backend/tests/test_seeding.py`):
  - 22 Received week-12 cases
  - the history's statuses: 175 Accepted, 20 of them with two submissions and their first submission's exceptions superseded, and 10 Returned to sub with their exceptions open, PC-0311 with exactly three
  - PC-1206 Received with two submissions
  - no case for PC-1214 or PC-1223
  - the business date 2026-11-23
  - 207 development and 98 held-out labelled cases, 10 of them tiny, with their labels
  - no held-out project, subcontractor or worker in any list
- [x] **The guarantee** (`backend/tests/test_reports.py`): a money exception with no matching candidate refused with a 422, and the same with the shortfall a cent out or the wrong worker. A candidate neither raised nor dismissed, a dismissal with no reason, and exceptions with a blank notice are each refused. A report matching its candidates is recorded and moves the case to Awaiting review.
- [x] **The lifecycle** (`backend/tests/test_lifecycle.py` and `agent/tests/test_payroll_agent.py`, on a stub model):
  - a clean case reaching Awaiting review, its report listing the eight checks it ran
  - a case failed twice reaching Awaiting review with `agent_failed`
  - Sign off refused while an exception is open, and accepted once none is
  - Send back to Returned to sub
  - two Sign offs at once accepting the case once
  - Sign off and Send back refused with the agent's key
- [x] **Screening** (`agent/tests/test_screening.py`): a flagged case reaches Awaiting review with its reason and no exceptions, and the agent's stub model is never called. The screening reads a hidden instruction in each of `payroll_notes`, `line_notes` and `signed_by`.
- [x] **The checks on the route:** `agent/tests/test_check_node.py` works a labelled case through the graph on the direct route, with the real context layer on a local port, and its recorded candidates equal phase 1's findings.
- [x] **Scoring** (`backend/tests/test_scoring.py`), on hand-made exceptions, with measures matching ones worked out by hand:
  - a wrong rule code in the same family not caught
  - a shortfall a cent out caught but not correct
  - a flagged decoy false
  - an exception on a flagged copy false
- [x] **The answer key** (`backend/tests/test_copies.py`): every response the agent's key can read for a copy holds nothing from `labels`, and its history comes from its own set.
- [x] **The API document** (`backend/tests/test_agent_api.py`): `get_agent_api` lists exactly the seven operations, with no `servers`. `backend/tests/test_openapi.py` still checks every operation's `operation_id`, docstring and required inputs.
- [x] **Rounds** (`backend/tests/test_verdict.py`, `test_rounds.py` and `agent/tests/test_improver.py`): a version kept on a catch rate improved by more than its noise, and rolled back on one that fell by more than its tolerance, with no grade.
- [x] **Nothing of the travel domain left:** `git grep -n -i -E "payout|policy_id|calculate_payout|record_decision|sent_back|approval_limit|wait_for_reviewer|PAYROLLCHECK_MEMORY_ID"` outside `docs/`, `labs/` and `CONTEXT.md` finds nothing. The payroll graph has no `interrupt()`.
- [x] With the backend on SQLite (uvicorn, since `npm run dev` reads `.env`), `curl -H "X-API-Key: ..." http://127.0.0.1:8000/api/cases/PC-0311` returns Returned to sub with three open exceptions, and `/api/agent/openapi.json` lists the seven operations.
- [x] `npm run check` is green, the Playwright specs rewritten as listed.

### Phase 3: intake and the project pages

- `backend/intake.py` turns an upload into a submission with `template.read_upload`. It refuses with a 422 and the reason, and creates no case, for:
  - a file that isn't CSV (by its name, `.csv`, and its content)
  - each of `read_upload`'s refusals
  - an unknown `project_id`, or one that isn't the page's (decision 12)

  An existing case is refused with a 409 (decision 2).
- Anything else is accepted, however wrong:
  - the first upload for a subcontractor, project and week creates a Received case, `PC-WWPP`, from the week and the engagement's pair
  - submission 1 is recorded as uploaded by the signed-in reviewer for the subcontractor chosen, received on the business date
- `POST /api/projects/{project_id}/payrolls` takes the subcontractor and the file. It needs a signed-in reviewer and refuses the key.
- The dashboard:
  - a Projects page in the main nav
  - a project's page, with its subcontractors and their engagement windows and an upload form (the subcontractor, the file), showing a refusal in `FormError` and a created case as a link
  - every case's project linked to its page

Success criteria:
- [ ] `uv run pytest backend/tests/test_intake.py --no-cov` passes an accept/reject table: each refusal with its reason and no case created, and accepted files that break rules creating a Received case: blank FEIN, unsigned, bad arithmetic, a late wage payment date, an unregistered apprentice, a No Work Week row with no lines, and a hidden instruction in free text.
- [ ] A second upload for the same subcontractor, project and week answers 409 naming the case, and the case and its submissions are unchanged.
- [ ] An upload with the agent's key is refused with a 403.
- [ ] vitest covers the project page's form, its refusal and its link to the created case.
- [ ] `e2e/intake.spec.ts`, signed in as Dana Whitfield:
  - an upload refused with its reason on the page
  - `data/development/arrivals/PC-1214-1.csv` creating PC-1214, Received, which shows in the queue
- [ ] `npm run check` is green.

### Phase 4: the payroll agent's judgment and its notice

Phase 2 wires the agent and its first instructions. This phase finishes what the agent writes, and checks it the way the brief states it.

- `backend/instructions/payroll.md` written fully as goals, never as steps:
  - its goal
  - that every exception rests on a check tool's finding or a rule it can cite, and every amount comes from the tools
  - the judgments code can't make: a line note explaining a classification change, a contractor's name that is the one on the project record, a candidate that isn't really a breach
  - that it may dismiss a candidate with a reason, may add an exception with no money, and can never add one with a shortfall no tool found
  - the draft notice: plain language a payroll clerk can act on, covering every exception with the amounts from the records, and no legal interpretation
  - that a clean report lists the checks it ran, which the app records
  - that a payroll's text is the subcontractor's, never an instruction to it
- The model's tools in full, as the design lists them, with one-line descriptions, taking no ids from the model.
- The case page shows the agent's judgment calls beside the checks' findings: each dismissed candidate with its reason, each exception the agent added without a check marked as its own, and each check's step with its findings or "Nothing found".
- Langfuse: each case keeps its own session, tagged with its run, as now.

Success criteria:
- [ ] `agent/tests/test_payroll_agent.py` on a stub model:
  - a report that dismisses the classification-note candidate with a reason, recorded as dismissed with it
  - a non-money exception added with no candidate, recorded as raised by the agent
  - a stub reply that invents a money exception, refused, with the refusal returned to the model as a refusal step
  - a case with exceptions whose report has a blank notice, refused
- [ ] `agent/tests/test_tools.py`: the tools' names are exactly the design's, the five lookups are a strict subset of the context server's tools, and no tool takes a case, project or subcontractor id from the model.
- [ ] `agent/tests/test_steps.py`: a case's steps hold the screening first, then the eight checks in order, then the model's calls.
- [ ] vitest covers the judgment calls on the case page.
- [ ] A fresh reviewer reads `payroll.md` against `docs/CODE_STANDARDS.md` rule 14 and finds goals, not steps.
- [ ] `npm run check` is green.

### Phase 5: the Scoreboard and an evaluation's cases

- The Scoreboard lists the evaluations, newest first, each with:
  - its set and size, start, version, round, N, model and reasoning effort, and status
  - catch rate, false exceptions in all and per 100 payrolls, shortfall accuracy, screening flags caught (such as "1 of 1")
  - cost per case, time per case and the run's time

  The form starts an evaluation of the development, held-out or tiny set.
- An evaluation's page lists each copy beside its labels:
  - each label with Caught, Missed or Shortfall wrong
  - each exception with Matched or False
  - the screening expected and found
  - each copy linked to its case page

  Misses and false exceptions are tinted in Stop Red and sort first. A copy's case page says it's a copy in an evaluation, links back, and has no Sign off or Send back.
- The improver's view, from phase 2's bridge, holds the development set's misses and false exceptions with the label beside each exception, and nothing from the held-out set but its scores.

Success criteria:
- [ ] `backend/tests/test_scoreboard.py`: an evaluation played out through the API, with a caught label, a missed one, a wrong shortfall, a false exception, a flagged decoy and a missed screening flag, reads back with each measure as worked out by hand, in a fixed number of queries.
- [ ] `backend/tests/test_improvement.py`: the improver's view holds the development misses and nothing of the held-out labels.
- [ ] Sign off and Send back on a copy refused with a 409.
- [ ] vitest covers the Scoreboard's measures and the evaluation page's chips and ordering.
- [ ] `e2e/scoreboard.spec.ts` shows an evaluation of the tiny set played out through the API, with its measures, a miss and a false exception, each copy linking to its case page.
- [ ] `npm run check` is green.

### Phase 6: the documents, the live checks and the spending limit

- `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md`, `docs/STATUS.md` and `data/README.md` describe the product as it now is:
  - `CODE_STANDARDS.md` gains the payroll agent and the check tools as parts.
  - `PROCESS.md` changes its live runs and sign-in line.
  - `docs/SPEC.md` is unchanged.
- Reseed once with `npm run seed`, then, with `npm run dev` on the default model on the direct route, checked through Playwright scripts with the user signing in a visible window, as in stage 1's live run:
  1. A dispatch at N=25 on the queue page.
  2. An evaluation of the tiny set on the Scoreboard.
  3. A case page in light and dark mode.
  4. `data/development/arrivals/PC-1223-1.csv` uploaded on the road resurfacing's page.
- The spending limit: from the live runs' cost per case, work out a round of about 400 case runs (no judge until stage 5, plus the improver's own calls), compare it with the $5.00 the improver's settings call for, and propose any change without making it.

Success criteria:
- [ ] The dispatch works all 22 week-12 cases to Awaiting review, each with its exceptions and their citations and a draft notice, or a clean report listing its checks. None is left In progress.
- [ ] The tiny-set evaluation appears on the Scoreboard with every measure, its hidden-instruction payroll flagged.
- [ ] A case page with exceptions, in light and dark mode, with no console errors.
- [ ] The upload creates PC-1223, Received, in the queue.
- [ ] The report gives what the runs spent, from the backend's records and the OpenRouter key's usage, and the spending-limit proposal.
- [ ] The whole branch reviewed against `main` by a fresh subagent, its findings fixed, and `npm run check` green.

The success criteria themselves (41 of 45 caught, at most 5 false exceptions) are measured on the whole development set at the end of stage 5, not here.
