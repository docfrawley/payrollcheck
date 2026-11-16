# Plan: stage 4, Review & access

From `docs/stages/04_REVIEW.md`. After stage 3 the payroll agent checks every Received case and writes its exception report and a draft notice, and any reviewer can Sign off or Send back. This stage makes that a review our reviewers can run on a Monday morning:
- they correct the agent's report by **overrides**, each logged with who, when and why
- they edit the **notice**, and Send back writes it to the **outbox**
- a new upload **reopens** a case, even an Accepted one
- each person has a **role** and sees only the projects in their **scope**

The work happens on a branch, `stage-4-review`, cut from `main` at `27ab1c3`, with a commit at the end of every phase.

## The baseline: `npm run check` before the stage

On `main` at `27ab1c3` (the same tree as `stage-3-cases` at `b60e80f`), with no `.env`:
- ruff and pyright are clean, and pytest passes 1,147 at 99% coverage.
- The server, context and runtime import checks exit 0.
- Prettier, ESLint and tsc are clean, and vitest passes 190.
- Playwright passes 33.

Every phase ends with `npm run check` green and coverage of at least 80%. Tests are deleted only with the code they test, and each one's replacement is written in the same phase (the test rule in `docs/ROADMAP.md`).

## Decisions

### Taken with the user while planning

1. **Marcus's dispatch works the 22 week-12 cases the seed leaves Received.** The brief says 24, but PC-1214 and PC-1223 are the two missing filings, for an upload. The tests and the live run count 22, and the live run uploads a missing filing where the brief already has an upload.
2. **Any reviewer can open any evaluation copy.** Copies belong to evaluations, which every reviewer sees on the Scoreboard, not to the queue. Scope covers the queue's cases and everything hanging off them; a copy, whose project may be held out, is outside it. A copy still can't be signed off, sent back or overridden.
3. **A dismissal can be undone, by a new row.** An override has three kinds: `dismissed`, `added` and `restored`. Restoring reopens a dismissed exception, with its own reason. No override is edited or deleted, so the log shows a dismissal and then its restoring.
4. **A reviewer's added exception may carry a shortfall they enter.** An exception under a rule that carries money (`rate.base_short`, `rate.fringe_short`, `overtime.underpaid`, `arithmetic.gross`, `apprentice.unregistered`, `classification.mismatch`) needs a shortfall above zero, entered in dollars on the page and kept in cents. One under any other rule has none. The rule that an exception's shortfall must be a check tool's finding stays the agent's alone (`backend/reports.py`).

### Choices this plan makes, for your review

5. **Overrides only on a case Awaiting review, and only on its latest submission.** An Accepted case is final until a new submission reopens it. A Returned to sub case waits for its correction. Either way a dismissal, an addition or a restoring answers 409 with the case's status.
6. **An upload while the case is In progress is refused with a 409.** The message is "PC-1203 is being checked: upload the correction once it's awaiting review". Superseding the exceptions of a run still going would leave the agent reporting on a submission that's no longer the latest. Any other status reopens.
7. **Reopening resets the attempt.** The case's `thread_id`, `attempts`, `agent_failed`, screening flag and reason, `reviewed_by` and `reviewed_on` go back to none. The next dispatch then starts it on a new thread, as a first attempt. The earlier thread's candidates, check runs and steps stay, under that thread.
8. **Send back needs a notice.** The body is the reviewer's edited text, or the agent's draft when there's no edit. A blank body is refused with a 422. On a clean or flagged case, which has no draft, the reviewer writes the notice before sending. Send back needs no open exception, as the brief sets no such rule.
9. **The outbox record:**
   - **to:** the subcontractor's `contact_email`
   - **subject:** "Certified payroll {case id}, {project name}, week ending {date}: corrections needed"
   - **body:** the notice
   - **sent by:** the reviewer's name and email
   - **sent at:** the time

   One record per submission, unique on the case and submission, so a second Send back can't write a second record.
10. **The notice can be saved without sending.** That writes the edited text, who and when, on the latest submission's notice. Where the agent drafted none, the row is created with no draft. `notices.draft`, `drafted_by` and `drafted_at` become nullable for that.
11. **The rule catalogue reaches the dashboard by a read, `list_rules`** (`GET /api/rules`): each rule's code, check, severity and whether it carries money, for the add form. The catalogue stays written once, in `backend/rule_codes.py`.
12. **The override log is queryable by date in code, not yet by a route.** `overrides.created_at` gets an index. `overrides_between(db, start, end)` in `backend/overrides.py` is tested now, for stage 5's improver view to call.
13. **A held-out project is outside everyone's scope**, the compliance manager's too. That folds stage 3's held-out check on `get_project`, `list_subcontractors` and the upload into `scope_of`. The agent's key still reads held-out projects for an evaluation's copies.
14. **A dispatch's cost and time, as a reviewer sees them, are their own cases'.** The panel shows the cases in their scope, with those cases' cost and time, plus "and N cases on other projects". The compliance manager sees the whole dispatch. The agent's key reads the whole run, as now.
15. **The role is an enum, and its title comes from it.** `reviewers.role` is `reviewer` or `compliance_manager`. The header shows "Reviewer" or "Compliance Manager", from one map in the dashboard. The reviewers' ids stay `HND-01` to `HND-03`, since the brief doesn't ask to rename them.
16. **Improvement and Settings are the compliance manager's.** That covers their reads (`get_improvement`, `get_recipe`, `get_settings`) as well as their actions. A reviewer opening either page sees the `NotAllowed` message, and neither page is in their navigation. The Configuration page stays every reviewer's, as the brief leaves it.

17. **A reviewer keeps the appearance.** Made while building phase 1. The light or dark appearance is the browser's own, and it lived on the Settings page. So a reviewer's account menu has **Appearance** in place of Settings. It leads to `/settings`, where a reviewer sees only the appearance choice and "Only the compliance manager can see the settings", and nothing is read from the backend. The Improvement and recipe pages show a reviewer only their title and the not-allowed line.
18. **The Copilot's starts default to 3 payroll agents.** Made while building phase 1. With `get_settings` now the compliance manager's, the Copilot can no longer read the settings' number for a start the reviewer didn't size. Its `start_dispatch` and `start_evaluation` now default in code to 3, the number the queue page first offers.

## Design

### The scope

- **`backend/scope.py` owns scope, and nothing else defines it.**
  - `Scope` is the set of project ids a caller may see, or everything for the agent's key.
  - `scope_of(db, reviewer)` returns a reviewer's assigned projects from `project_reviewers`, or every project not held out for the compliance manager.
  - The dependencies `Scoped`, for a signed-in reviewer, and `ScopedOrAgent`, for the reads the agent shares, give a route its scope.
  - It also holds the two filters every query uses: `cases_in(scope)`, a case on a project in scope or an evaluation copy (decision 2), and `projects_in(scope)`.
- **A lookup by id takes the scope.** `backend/lookups.py`'s `find_case` and `project_row` take it, and an id outside it raises the same 404 with the same message as an unknown id. Every route that takes a case, project or subcontractor id gets its row through these lookups, writes included.
- **Lists filter by scope:**
  - `list_cases`, `list_projects`, `find_subcontractors` and `get_subcontractor`, with its projects and cases
  - the dispatch's cases
  - the upload, which goes through the scoped `project_row`
- **The scoping test reads the route table.** For every route whose path takes `{case_id}`, `{project_id}` or `{subcontractor_id}` and that a reviewer may call, Priya gets a 404 with the not-found message for an id on Marcus's projects.
  - Routes taking other ids (`run_id`, `round_id`, `proposal_id`, `number`, `conversation_id`, `turn_id`, `step_id`) are listed in the test as outside scope, each with its reason.
  - A route with a new id parameter, in neither list, fails the test, so a new route can't miss scope.

### Roles

- **`role` replaces `can_approve_over_limit`** in the table, `data/reviewers.json`, `Reviewer` and the dashboard's `api.ts`.
- **`compliance_manager(action)` in `backend/dependencies.py` checks the role.** Its 403 names the action, as now. It gates:
  - `start_round`, `stop_round`, `approve_proposal`, `reject_proposal` and `change_settings`, as now
  - `get_improvement`, `get_recipe` and `get_settings`, newly
- **`project_reviewers(reviewer_id, project_id)`** is loaded by seeding from a `projects` list on each reviewer in `data/reviewers.json`, with `"all"` for Dana. Its two columns are the key.

### Overrides

- **`backend/overrides.py`** holds the three moves and the log:
  - `dismiss(db, case, exception_id, reviewer, reason)`
  - `restore(...)`
  - `add(db, case, request, reviewer)`
  - `overrides_of(db, case_id)` and `overrides_between(db, start, end)`
- **Each move is one conditional update or insert with its override row, in one transaction:**
  - Dismissing moves an open exception of the latest submission to dismissed, checking the row count.
  - Restoring moves a dismissed one back to open.
  - Adding inserts an open exception with `source` reviewer, `raised_by` the reviewer's name, and the severity and citation from the catalogue.
- **The routes, all `SignedIn` and all scoped:**
  - `dismiss_exception`: `POST /api/cases/{case_id}/exceptions/{exception_id}/dismissal`, `{reason}`
  - `restore_exception`: `POST .../restoration`, `{reason}`
  - `add_exception`: `POST /api/cases/{case_id}/exceptions`, `{rule, worker_id, line_no, expected, actual, shortfall_cents, reason}`, every field present, `worker_id`, `line_no` and `shortfall_cents` nullable
- **Refusals, each a 422 that says what's wrong:**
  - a blank reason
  - a rule outside the catalogue
  - a worker rule without a worker and line, or with a line that isn't that worker's on the latest submission
  - a payroll rule with one
  - a money rule without a shortfall above zero, or a non-money rule with one
  
  An exception on another case, or another submission, is a 404.
- **Nothing reaches the labels.** No route reads or writes `labels` or `labelled_cases` but scoring and seeding. A test runs every override against a case and finds the labels table unchanged.

### Sign off, the notice, Send back and the outbox

- **Sign off** keeps stage 3's check of open exceptions on the latest submission, its 409 saying how many, and its conditional move, so two at once accept the case once.
- **`backend/notices.py`** holds `save_notice(db, case, text, reviewer)` and `notice_to_send(db, case)`, which returns the body or refuses a blank one. `save_notice` is `PUT /api/cases/{case_id}/notice`, `{text}`.
- **`backend/outbox.py`** holds the `outbox` table's writes and `deliver(outbox_row)`, which does nothing beyond the record for now. It's the one place a real email provider would plug in.
- **Send back, in one transaction:**
  1. moves the case Awaiting review → Returned to sub, conditionally
  2. marks the notice sent, by whom and when
  3. inserts the outbox row
  4. calls `deliver`

  So a case is never Returned to sub without its record, and a second Send back gets the 409 and writes nothing.
- **The case view (`Case`) gains:**
  - `overrides`, each with its exception, kind, reviewer, time and reason
  - `notice`, with its edited text and who sent it
  - `sent_notices`: the outbox records, newest first

### Reopening

- **`backend/intake.py` reopens instead of refusing.**
  - An upload whose case exists adds submission n+1 and moves the case to Received, conditionally on the submission number it read.
  - It supersedes the open exceptions of earlier submissions and resets the attempt (decision 7), in the same transaction as the insert.
  - It refuses a case In progress (decision 6).
- **Two uploads at once** make one submission n+1. The other gets a 409 naming the case, to upload again.
- **The case page shows each submission** with its exceptions under it: superseded ones marked as such, dismissed ones with their override. Sign off and exposure look only at the latest.

### The dispatch, as each person sees it

`find_run` takes a scope. For a reviewer it keeps the run's cases in scope, sums their cost and time, lists only them in the summary, and adds `other_projects`, the count of the run's cases outside it. `get_run`, as `ScopedOrAgent`, and `get_latest_dispatch` use it. The Copilot reads the same, with the reviewer's sign-in.

### The send-back-to-agent flow

Stage 3 removed it: the paused graph, the resume, the sent-back records and their routes and pages. What's left is the test helper `resume_case` in `agent/tests/invoking.py`, which no test calls, beside a test that the entry point refuses an unknown `resume_case` operation. Seeding keeps `sent_back_decisions` in its list of retired tables to drop.

`agent/tests/test_boundaries.py` already asserts no `interrupt` in `harness.py`. It gains:
- no route path with `send-back` but `send_back_case`'s
- no table named like the old records
- no `interrupt` anywhere in the payroll agent's modules (the improver's human-in-the-loop pause is its own, and stays)

### The modules, and how they depend

- **`scope.py`** uses `database.py` and `models.py`. `lookups.py` uses it. The routers take their dependencies from `dependencies.py` and their scope from `scope.py`.
- **`overrides.py`, `notices.py` and `outbox.py` each use `database.py`, `lookups.py` and `rule_codes.py`.** They don't use one another.
  - `main.py`'s routes call them.
  - Send back, in `main.py`, calls `notices.py` and then `outbox.py`.
- **`intake.py`** uses `lookups.py` for the scoped project and reopens with its own move.

No module borrows another's helpers, each literal (statuses, override kinds, messages, paths) is written once, and there are no cycles. That checks against `docs/CODE_STANDARDS.md` rules 7 to 12.

### The schema

- **New tables:**
  - `project_reviewers(reviewer_id, project_id)`
  - `outbox(outbox_id, case_id, submission_no, to_address, subject, body, sent_by, sent_at)`, unique on `(case_id, submission_no)`
- **Changed:**
  - `reviewers.role` now holds `reviewer` or `compliance_manager`, and `can_approve_over_limit` is gone
  - `overrides.kind` takes `restored`, and `created_at` has an index
  - `notices.draft`, `drafted_by` and `drafted_at` become nullable
- Reseed after pulling, as every stage that changes tables says.

## Phases

### Phase 1: roles, assignments and the leftovers of the old flow

- `data/reviewers.json` gives each reviewer `role` (`compliance_manager` or `reviewer`) and `projects` (decision 15), in place of `can_approve_over_limit`.
- Seeding loads `reviewers` and `project_reviewers`.
- `Reviewer` has `role`. `compliance_manager(action)` checks it, and now gates `get_improvement`, `get_recipe` and `get_settings` too (decision 16).
- The dashboard:
  - `api.ts`'s `Reviewer` has `role`
  - the header's title and the navigation come from it, with Improvement and Settings shown only to the compliance manager
  - the Improvement and Settings pages show `NotAllowed` to a reviewer
  - `ProposalPanel` reads the role
- `e2e/reviewers.ts` gains Priya, and the Auth stand-in signs her in.
- The leftovers: `resume_case` goes from `agent/tests/invoking.py`, and `test_boundaries.py` gains the three assertions above.

Success criteria:
- [x] `uv run pytest backend/tests/test_seeding.py backend/tests/test_roles.py --no-cov` passes:
  - `project_reviewers` holds Dana on PRJ-01, PRJ-02 and PRJ-03, Marcus on PRJ-01 and PRJ-02, and Priya on PRJ-03
  - no `can_approve_over_limit` column
- [x] Marcus and Priya get a 403 naming the action on `start_round`, `stop_round`, `approve_proposal`, `reject_proposal`, `change_settings`, `get_improvement`, `get_recipe` and `get_settings`. Dana gets each one's success. All three read `list_evaluations`, `get_evaluation` and `get_configuration`.
- [x] `grep -rn can_approve_over_limit backend agent dashboard/src e2e data` finds nothing.
- [x] vitest:
  - Priya's navigation has no Improvement or Settings, and Dana's has both
  - Priya on `/improvement` and `/settings` sees the not-allowed message
  - the header shows "Reviewer" and "Compliance Manager"
- [x] `uv run pytest agent/tests/test_boundaries.py --no-cov` passes with the new assertions.
- [x] `npm run check` green. Reviewed by a fresh subagent, findings fixed, committed.

### Phase 2: one scope, everywhere

- `backend/scope.py`, with `scope_of`, `Scoped`, `ScopedOrAgent`, `cases_in` and `projects_in`, as the design says.
- Scope-taking `find_case` and `project_row`, applied to every route listed in the design:
  - the case reads and `list_steps`
  - Sign off and Send back
  - the projects and the upload
  - the subcontractors
- `list_cases` and `list_projects` filtered.
- Stage 3's held-out checks folded in (decision 13).
- The Copilot needs no change: its `app_api.py` already sends the reviewer's sign-in.

Success criteria:
- [ ] `uv run pytest backend/tests/test_scope.py --no-cov` passes:
  - **every id route:** for every route the route table lists with a case, project or subcontractor id, Priya gets a 404 with the not-found message for one on PRJ-01, identical to an unknown id's
  - **a new route fails:** a route added with a new id parameter, outside both of the test's lists, fails the test (shown by a test that registers one on a throwaway app)
- [ ] The queue filters by scope:
  - Marcus's `list_cases` has only PRJ-01 and PRJ-02 cases
  - Priya's only PRJ-03
  - Dana's all 207
  - the agent's key all 207
- [ ] The other lists filter by scope:
  - `list_projects`
  - `find_subcontractors` (Priya's has only subcontractors on PRJ-03)
  - `get_subcontractor`'s projects and cases
  - `list_subcontractors`
  - an upload to PRJ-01 as Priya answers 404 "Project PRJ-01 not found"
- [ ] Evaluation copies are open to every reviewer: Priya opens a copy of a PRJ-01 case and of a held-out case, and neither appears in her queue.
- [ ] The agent's key reads a case, its history, project and subcontractors on any project, held-out ones included. It's refused with a 403 on Sign off and Send back.
- [ ] `uv run pytest agent/tests/test_copilot.py --no-cov`: the Copilot, signed in as Marcus, gets not found for PC-1217 (road resurfacing), and that refusal goes back to its model.
- [ ] vitest: Priya on `/cases/PC-1201` sees the case's not-found page.
- [ ] `npm run check` green. Reviewed, findings fixed, committed.

### Phase 3: overrides and the sign-off rule

- `backend/overrides.py` and its three routes, as the design says, with decisions 3, 4, 5 and 11.
- `list_rules`.
- `Case.overrides`.
- `overrides_between`.
- The case page:
  - each open exception on the latest submission has Dismiss, with a reason
  - each dismissed one has Restore, with a reason
  - an "Add an exception" form chooses a rule, then the worker and line from the submission's lines where the rule needs them, with expected and actual, a shortfall in dollars where the rule carries money, and a reason
  - the overrides are listed beside the exceptions they changed
  - Sign off is disabled while any exception is open, saying how many
  - flagged and agent-failed cases are worked the same way

Success criteria:
- [ ] `uv run pytest backend/tests/test_overrides.py --no-cov` passes:
  - **logged:** a dismissal, an addition and a restoring each logged with reviewer, time, kind and reason, never edited or deleted
  - **refusals:** each refusal in the design, with its message; an override on a case not Awaiting review, on an earlier submission or on a copy refused
  - **two at once:** two dismissals of the same exception at once record one
  - **the labels:** unchanged after every kind of override, and no route path reads or writes them
  - **by date:** `overrides_between` returns those in its window, in order
- [ ] The sign-off rule holds:
  - Sign off is refused with a 409 saying "1 open exception" while one is open, and accepted once it's dismissed
  - two sign-offs at once accept the case once
  - a flagged case with one exception added by hand signs off only after it's dismissed
- [ ] The agent's key is refused with a 403 on `dismiss_exception`, `restore_exception` and `add_exception`.
- [ ] vitest:
  - the dismiss, restore and add forms send their requests and show the refusals
  - the money field appears only for a money rule
  - Sign off is disabled with the count
- [ ] `npm run check` green. Reviewed, findings fixed, committed.

### Phase 4: the notice, Send back and the outbox

- `backend/notices.py`, `save_notice` and the nullable draft columns (decision 10).
- `backend/outbox.py` with `deliver`.
- Send back as the design says (decisions 8 and 9).
- `Case.sent_notices`.
- The case page:
  - the notice in an editor with Save and Send back, showing who edited it and when
  - after Send back, the email preview: to, subject, sender, time and body, with the agent's draft beside it when the text was edited
- `e2e/send_back.spec.ts` rewritten for this.

Success criteria:
- [ ] `uv run pytest backend/tests/test_send_back.py backend/tests/test_notices.py --no-cov` passes:
  - **one record:** Send back writes one outbox row with the subcontractor's `contact_email`, the subject, the edited body, the sender and the time, and calls `deliver` once with it
  - **both texts kept:** the draft and the sent text are both kept
  - **a blank notice:** refused with a 422, with nothing written
  - **two at once:** two Send backs at once write one row
  - **`deliver` fails:** the case stays Awaiting review with no row
- [ ] Saving an edit without sending keeps the case Awaiting review. On a clean case with no draft, it creates the notice with no draft.
- [ ] The agent's key is refused with a 403 on `save_notice`.
- [ ] Playwright, `e2e/send_back.spec.ts`: Marcus edits the draft notice, presses Send back, and sees Returned to sub and the email preview with the subcontractor's address.
- [ ] `npm run check` green. Reviewed, findings fixed, committed.

### Phase 5: a new submission reopens the case

- `backend/intake.py` reopens, with decisions 6 and 7.
- Stage 3's 409 for an existing case goes, with its test, replaced by these.
- The case page groups exceptions by submission, with superseded ones marked.
- `data/README.md` says how a correction is uploaded.

Success criteria:
- [ ] `uv run pytest backend/tests/test_intake.py backend/tests/test_reopening.py --no-cov` passes. A new submission on an Accepted case:
  - the case back to Received, at submission 2
  - the earlier submission's open exceptions superseded and its dismissed ones still dismissed
  - its thread, attempts, flags and review cleared
  - Sign off then looking only at submission 2
- [ ] The same holds for a Returned to sub case.
- [ ] An upload while In progress is refused with a 409 and changes nothing. Two uploads at once make one new submission.
- [ ] `uv run pytest agent/tests/test_dispatcher.py --no-cov`: the next dispatch works the reopened case on a new thread, as attempt 1, never carrying on the old one.
- [ ] Playwright: a corrected CSV uploaded for an Accepted case reopens it to Received, with submission 1's exceptions shown as superseded.
- [ ] `npm run check` green. Reviewed, findings fixed, committed.

### Phase 6: the dispatch as each person sees it, the end-to-end tests, the documents and the live checks

- `find_run` with scope and `other_projects` (decision 14).
- The dispatch panel's "and N cases on other projects".
- The rest of the brief's end-to-end tests.
- The documents:
  - `docs/SPEC.md`, checked and left as it is unless it no longer describes the product
  - `docs/TECH_STACK.md`, with scope, roles, overrides, the outbox and reopening
  - `docs/CODE_STANDARDS.md`, with scope as one module
  - `docs/PROCESS.md`, whose browser checks sign in as Marcus Oyelaran for a reviewer's work and Dana Whitfield for the compliance manager's
  - `docs/STATUS.md`
  - `data/README.md`
- After reseeding once, the live checks with `npm run dev` on the default model, through Playwright scripts with you signing Marcus and Priya in, in a visible window, as in stages 1 and 3.

Success criteria:
- [ ] `uv run pytest backend/tests/test_runs.py agent/tests/test_dispatcher.py --no-cov`: a dispatch started by Marcus works all 22 Received week-12 cases. His `get_latest_dispatch` lists his own, with their cost and time, and `other_projects` counts the rest; Dana's lists all 22.
- [ ] Playwright:
  - **scope:** Marcus doesn't see a road-resurfacing case in the queue, and its URL shows the not-found page (404 from the API)
  - **a dispatch:** Marcus's dispatch works the 22 against the agent's stand-in, and his panel shows his cases and "and N cases on other projects"
  - **sign-off:** Marcus dismisses an exception with a reason and signs off, Sign off disabled while one is open
  - **navigation:** Priya sees no Improvement or Settings in the navigation, and Dana does
  - **reopening:** passes, from phase 5
- [ ] The live checks, after one `npm run seed`:
  - **Marcus's review:** Marcus starts a dispatch of the week-12 wave. On one of his cases with exceptions he dismisses one with a reason, adds one, edits the notice and sends it back, and the email preview shows. On a clean case he signs off.
  - **A correction:** a corrected CSV for the case he signed off, uploaded on its project's page, reopens it. The next dispatch checks it again, and its earlier exceptions show as superseded.
  - **Priya's scope:** Priya's queue shows only the road resurfacing, and the URL of Marcus's case shows not found.
  - **Spend:** what the runs spent, from the backend's records and the OpenRouter key's usage.
- [ ] The documents describe the product as it now is.
- [ ] The whole branch reviewed against `main` by a fresh subagent, its findings fixed, and `npm run check` green with `.env` moved out of the way.
