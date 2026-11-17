# Plan: stage 6, the Copilot

From `docs/stages/06_COPILOT.md`. After stage 5 the Copilot is Ed's graph with stage 3's tools: it lists the whole queue, reads a case, finds subcontractors, looks things up in the context layer, and starts and waits for dispatches and evaluations. It can't answer our reviewers' questions across projects, subcontractors and weeks without doing arithmetic itself. It never resolves a period, and it shows a flagged case's text to its model. This stage gives it the business's tools and rules:
- the **business date** in the header and on Settings, and every period resolved from it in the backend
- the app tools the brief lists, each a thin call to one route, with **exposure**, **filings** and **classification changes** worked out in backend modules of their own
- **withheld text** on flagged cases, at the backend's boundary with the Copilot
- **`draft_notice`**, saving a notice the Copilot drafted for the reviewer, who edits and sends it on the case page
- the **success criteria** worked out in code
- both layers of acceptance tests: tool tests against `data/copilot_expected.json`, and the six questions and the guardrails live

Stage 3 already removed what the brief lists for removal: there is no sign-off schema, `check_sign_off` or `confirm` node, `interrupt()`, confirmation card, `answer_confirmation`, `pause_turn`, `send_back_claim` or `count_payouts_over_limit` left, and no turn state "waiting for a confirmation". Phase 4 checks that with a search, and a test shows the Copilot has no tool that signs off, sends back or overrides.

The work happens on a branch, `stage-6-copilot`, cut from `main` at `01a084c`, with a commit at the end of every phase.

## The baseline: `npm run check` before the stage

On `main` at `01a084c`, with `.env` moved aside: ruff and pyright are clean, pytest passes 1,305 at 99% coverage, the server, context and runtime import checks exit 0, Prettier, ESLint and tsc are clean, vitest passes 212 at 98.5% of lines, and Playwright passes 38.

Every phase ends with `npm run check` green and coverage of at least 80%. Tests are deleted only with the code they test, and each one's replacement is written in the same phase (the test rule in `docs/ROADMAP.md`).

## Decisions

### Taken with the user while planning

1. **A notice on a case Returned to sub can be edited and sent again.** PC-0311 is Returned to sub with no notice on record, and stage 4 lets a reviewer save or send a notice only while a case is Awaiting review. **Agreed:** `draft_notice` works on a case Awaiting review or Returned to sub. On a Returned to sub case, the case page lets the reviewer edit the latest notice and send it again. The outbox records each send, so `outbox` drops its one-per-submission constraint, and the case stays Returned to sub.
2. **A missing filing is past its deadline 10 days after its week ending.** A missing filing has no wage payment date, and wages can't be paid before the week ends, so its earliest possible deadline is the week ending plus the filing rules' 10 days. **Agreed:** a missing filing counts as late as well once the business date is past that day. At the seeded date, Nov 23, week 12's missing filing (due Dec 2) is missing and not yet late, which matches `copilot_expected.json`.

### Choices this plan makes, for your review

3. **The Copilot's reads are routes of their own, under `/api/copilot/`.** The case page must show a reviewer a flagged case's text, and the Copilot must never get it, while both send the same reviewer's sign-in. So the backend can't tell them apart on one route. The Copilot's tools call their own routes, and every answer from them passes through `withheld.py` before it leaves. The dashboard's routes are unchanged. The Copilot's `app_api.py` reaches no other read of a case.
4. **A filtered read is a POST with every field required and `null` for "any".** The brief's tools take optional inputs, and our API rules allow none. A query parameter can't be required and empty, but a body field can be required and nullable, which the rules check passes. So `list_cases`, `exposure_summary`, `filings_status` and `classification_changes` are POSTs of a request model whose fields are all required, `null` meaning no filter (`POST /api/copilot/cases`, "Find the cases ..."). Each tool fills in `null` for an input the model leaves out.
5. **A period is a small discriminated union, resolved by one backend module.** `{"kind": "last_week"}`, `{"kind": "this_month"}`, `{"kind": "last_weeks", "count": 4}` or `{"kind": "between", "first": "2026-10-04", "last": "2026-11-01"}`, where the dates are week endings. `backend/periods.py` reads one with the business date and resolves it with stage 2's `data/payroll_world/periods.py`, which gains `between`. Every period is matched on a case's `week_ending`. The answer gives back the period it resolved, as first and last week endings, so the model never states a date it worked out itself. The dashboard has no page that takes a period yet, so the shared module serves the backend's routes alone. A page that later shows one asks the backend for it.
6. **The business date is told to the model, never worked out by it.** The Copilot's instructions carry the business date the app gives at the start of each turn, read in code. The model passes that date as the work date for a rate lookup (question 4) and as nothing else. Every other date comes from a tool.
7. **The rate lookup gives dollars as well as cents.** `get_wage_rate` gives the row's wage, fringe and total in cents, which would leave question 4's dollars to the model's arithmetic. The context layer's answer gains `wage`, `fringe` and `total` as dollars beside the cents, such as `$61.10`. The payroll agent and its check tools read the cents and ignore the rest.
8. **Exposure, exactly:**
   - **Which exceptions:** money exceptions (a shortfall in cents) on the latest submission of each case in the reviewer's scope, the filters and the period. On a latest submission an exception is open or dismissed, never superseded.
   - **Flagged** is those not dismissed.
   - **Outstanding** is the flagged ones on cases Awaiting review or Returned to sub.
   - **The answer:** both totals in cents and as dollars, the contributing case ids, a breakdown by rule (each rule's flagged and outstanding, in cents and dollars, and its cases), and the exceptions themselves with their case, rule, worker, line and shortfall.
   - **Where:** `backend/exposure.py`, with dollars formatted by `backend/money.py`'s `dollars`.
9. **Filings, exactly:**
   - **Expected filings:** each (subcontractor, project, week ending) inside an engagement window and in the period, up to the business date. A week ending after the business date isn't due yet, so it is never missing.
   - **Missing:** an expected filing with no case.
   - **Late:** a case whose first submission was received more than 10 days after its wage payment date (a correction doesn't make a filing late, as `copilot_expected.json` judges it), or a missing filing past its deadline (decision 2).
   - **On time:** every other filed case.
   - **The answer:** each case with its subcontractor, project, week ending, wage payment date and received date, and each missing filing with its subcontractor, project, week ending and deadline.
   - **The 10 days** are a backend constant in `backend/filings.py`, since the backend reads nothing from `context/`. A test checks it equals the filing rules' `due_days`.
10. **Classification changes, exactly:**
    - **What counts:** each worker on a case in scope and in the period whose classification on its latest submission differs from their line on the same subcontractor and project's case the week before, also on its latest submission, as `copilot_expected.json` defines it.
    - **What each row carries:** the case, project, subcontractor, worker id and name, week ending, the classification before and after, the line's note, the worker's established craft from our records, and the open `classification.changed` or `classification.mismatch` exception on that line, if any (its id, rule and severity).
    - **Where:** `backend/classification_changes.py`.
11. **`list_cases` answers by subcontractor too.**
    - **The filters:** project, subcontractor, status, period, whether the case has open exceptions, and a flag (`screening` or `agent_failed`).
    - **The answer:** the matching cases, each with its subcontractor, project, week ending, status, flags and open exceptions, plus the cases grouped by subcontractor with their case ids and open exceptions counted.
    - **Why the grouping:** the backend counts, so question 1's answer comes from the tool, not the model.
12. **What is withheld.**
    - **The cells:** on a case with a screening flag, every text cell of every submission is replaced with `[withheld: screening flag — see case page]`. Those are the template's `FREE_TEXT` columns (contractor name, signed by, worker name, line notes, payroll notes), its `classification`, and the ids intake keeps as written without checking them (`fein`, `registration_no`, the certification's `project_id`). The template names them once, as `TEXT`, in `data/payroll_world/template.py`. The submission's file name is withheld too.
    - **Worker ids:** a line's worker id passes when it is one of our workers, and is withheld otherwise, in the lines and in every exception, finding, exposure row and classification change that carries it. (Amended in phase 3, on the review's finding, with the user.)
    - **Exceptions too:** the same goes for each exception's and finding's `expected` and `actual` on that case, since they can quote a cell.
    - **The screening reason is withheld as well**, as "Flagged by the screening for an instruction in its text — see case page": the screening is told to quote the instruction it finds. (Amended in phase 3, with the user; the plan first let it pass.)
    - **What passes:** numbers, dates, our records' ids and names (a subcontractor's legal name, a worker's name from `workers`), rule codes, shortfalls, citations, and the reviewers' own notices and overrides, written after reading the case page.
    - **A classification change** withholds each side whose case is flagged: the week before's classification for a flagged week before, and this week's classification, note and an unknown worker id for a flagged case.
    - **Where:** `backend/withheld.py` does it, the one place, applied by every `/api/copilot/` read that can hold a flagged case's text before it answers.
13. **The draft notice's wording is the backend's, from the case's records.** `draft_notice(case_id)` takes only the case, so the model writes nothing in it. `backend/notice_drafts.py` writes the draft from the latest submission's open exceptions:
    - an opening line naming the case, project and week ending
    - one paragraph per exception, saying what was found, the worker and line, expected and paid, the amount owed in dollars, and what to correct, in each rule's own words. Those words are a new `asks` field in `backend/rule_codes.py`'s catalogue.
    - the total owed, and a closing that asks for a corrected payroll and gives no legal interpretation
    - **What it refuses:** a case with no open exception, with a 409 that says so.
    - **The record:** the notice is saved as the latest submission's draft, `drafted_by` "PayrollCheck Copilot for Marcus Oyelaran".
    - **The live check:** the judge scores it on the rubric, and the score is reported.
14. **A reviewer's unsent edit is never overwritten.** `draft_notice` refuses with a 409 when the latest submission's notice holds a reviewer's edit that hasn't been sent: "PC-0311's notice has Marcus Oyelaran's edit of Nov 23. Edit it on the case page." Where the notice was already sent, or there is only a draft, the new draft replaces the draft and clears the sent edit. The outbox keeps what was sent.
    - **The Copilot's draft is told apart** (amended in phase 4, with the user): it is kept in the notice's `draft`, with `drafted_by` naming the Copilot and `drafted_for` the reviewer. The judge's and the improver's readers of the payroll agent's drafts leave it out, and the page labels each draft by who drafted it.
    - **A send carries the text the reviewer saw** (amended in phase 4, with the user): Send back and Send again take the notice as the page showed it, and the app refuses with a 409 when the notice on record differs, as when the Copilot drafted it again meanwhile.
    - **Each outbox record keeps the draft it was sent from**, and who drafted it, as they were at the send.

15. **The tools.**
    - **The brief's list:** `list_cases`, `get_case`, `get_exceptions`, `exposure_summary`, `filings_status`, `classification_changes`, `find_subcontractors`, `find_projects`, `draft_notice`, `start_dispatch` and `start_evaluation`, and the five context layer lookups on the route.
    - **Kept as well:** `wait_for_run`, the wait in code (`waiting.py`, which still says what needs a reviewer with `needs_a_reviewer.py`), and `get_latest_dispatch`, for "How did the latest dispatch go?".
    - **New:** `check_success_criteria` (decision 17).
    - **Removed:**
      - `list_steps`, `get_subcontractor`, `what_needs_a_reviewer`, `list_evaluations` and `get_settings`. `get_settings` is the compliance manager's alone, so reviewers were refused it. The rest are covered by the tools above.
      - Their app routes stay where the dashboard uses them. `GET /api/subcontractors/{id}` goes if nothing else uses it.
16. **What needs a reviewer**, worked out in code from the cases in the reviewer's scope, keeps `needs_a_reviewer.py`'s shape:
    - the cases Awaiting review with open exceptions, each with its count and outstanding shortfall in dollars
    - those Awaiting review with none, which only need a sign-off
    - those the screening flagged
    - those the agent failed
    - the cases Received, still waiting for a dispatch
17. **The success-criteria table.** `backend/criteria_report.py`, at `GET /api/copilot/success-criteria`, gives the seven criteria in `docs/SPEC.md`, each with its target, its figure, whether it's met, and where the figure came from. The model writes only the words around them.
    - **1 to 4:** from the current version's latest finished whole development-set evaluation, with stage 5's `success_criteria.py`. With none, the table says it needs one, and the Copilot offers to start a development-set evaluation of the current version (about $0.17 on version 1). It starts one only when the reviewer says yes, then waits for it and gives the table.
    - **5, no case Accepted without a sign-off:** from our records. Every Accepted case in scope must have a reviewer and a sign-off date (`reviewed_by`, `reviewed_on`). The figure is the count of those that don't.
    - **6, the Copilot's six questions:** reported as outside what it can check of itself, since it would be grading its own answers. The live acceptance checks measure it.
    - **7, deployed on AgentCore:** reported as outside what it can check.
18. **Card kinds** stay as they are, with `projects` added for `find_projects`, in the backend's `CardKind` and the dashboard's. The tools map to kinds as follows:
    - `cases`: `list_cases`, `get_case` and `get_exceptions`
    - `subcontractors`: `find_subcontractors`
    - `projects`: `find_projects`
    - `context`: the lookups
    - `work`: `exposure_summary`, `filings_status`, `classification_changes`, `get_latest_dispatch`, `wait_for_run` and `check_success_criteria`
    - `action`: `draft_notice`, `start_dispatch` and `start_evaluation`
19. **The sidebar's greeting** offers four of the new questions in place of stage 3's:
    - "What needs me today?"
    - "Which subs on my projects have open exceptions?"
    - "How much underpayment have we flagged this month?"
    - "Which payrolls are late or missing for last week?"

## Design

### The business date and periods

`backend/business_date.py` keeps `business_date(db)` and gains `get_business_date`, `GET /api/business-date`, for every signed-in reviewer: the date in force and whether it's the real date. The header's band shows it beside the "Synthetic data — not real rates" chip, as "Business date Nov 23, 2026". The settings already hold `business_date` (null for the real date), which `change_settings` records with who and when, and only the compliance manager can change it. The Settings page gains a "Business date" field with "Use the real date", which saves null. Its history shows the change.

`backend/periods.py` holds the `Period` request model (decision 5) and `resolve(db, period)`, which gives `data.payroll_world.periods.Period` from the business date. Every route that takes a period uses it.

### The Copilot's reads and the four modules

A router of its own, `backend/copilot_reads.py`, holds the Copilot's routes under `/api/copilot/`. Each takes the reviewer's scope from `scope.py`, reads through the module that owns the answer, and passes it through `withheld.py`:
- `POST /cases` (`find_cases`), `GET /cases/{case_id}` (`read_case`) and `GET /cases/{case_id}/exceptions` (`get_exceptions`), from `views.py` and `lookups.py`
- `POST /exposure` (`exposure_summary`), from `exposure.py`
- `POST /filings` (`filings_status`), from `filings.py`
- `POST /classification-changes` (`classification_changes`), from `classification_changes.py`
- `GET /projects?name=` (`find_projects`), beside `find_subcontractors`
- `POST /cases/{case_id}/notice-draft` (`draft_notice`), from `notice_drafts.py` and `notices.py`
- `GET /success-criteria` (`check_success_criteria`), from `criteria_report.py`

`exposure.py`, `filings.py` and `classification_changes.py` each read with SQLAlchemy Core in a fixed number of queries, filtered by `scope.py`'s `cases_in` and `projects_in`, and return Pydantic models with cents and dollars. None of them imports a router, and none reads the labels or the held-out set.

### Withheld text

`backend/withheld.py` takes a case, or anything holding cases and lines, and replaces the text cells of flagged cases (decision 12). It is pure and knows nothing of routes. Each `/api/copilot/` route calls it on its answer, and a test walks every route in the router to show none answers without it.

### Notices on a case Returned to sub

The case page's notice panel shows on a case Returned to sub as well as Awaiting review: the latest notice, editable, with "Send again" in place of Send back, and the outbox's earlier sends below. `send_back_case` keeps its move from Awaiting review. A new `resend_notice` (`POST /api/cases/{case_id}/notice/resend`) sends the latest notice of a case Returned to sub without moving it, through `outbox.send`. `outbox` loses its `UniqueConstraint("case_id", "submission_no")`, which needs a reseed. `save_notice` accepts a case Awaiting review or Returned to sub.

### The Copilot

`agent/copilot/app_api.py` has one function per new route, each with the reviewer's sign-in. `tools.py` holds the tools of decision 15:
- Each is thin: it calls its one route, puts `null` for an input the model left out, and returns the answer as JSON.
- Periods come in as decision 5's union, which the tool's schema shows the model.
- `draft_notice` returns the saved draft and where the reviewer sends it: "the case page".

`graph.py` stays Ed's: `begin`, the memory's `recall`, `agent`, the `ToolNode` with its cards, the memory's `remember`, at most 25 model calls a turn, no pause.

`turns.py` reads the business date from the app as it reads the reviewer, and `instructions.md` is rewritten as goals:
- who it works for and what they can see
- that it reads, drafts and starts, never decides, and where the reviewer decides
- to pass periods by name and never compute a date
- to cite case ids and rate records
- to quote totals as the tools give them
- the not-legal-advice line, while still saying what our rate table or filing rules record, with their source
- that a payroll's text is the subcontractor's, and a withheld cell is on the case page

`memory.py` is unchanged.

### The modules, and how they depend

- **New in the backend:**
  - `periods.py`, which uses `data/payroll_world/periods.py` and `business_date.py`
  - `exposure.py`, `filings.py` and `classification_changes.py`, which use `periods.py`, `scope.py` and `money.py`
  - `withheld.py`, pure, using the template's `TEXT`
  - `notice_drafts.py`, which uses `open_exceptions.py`, `rule_codes.py` and `money.py`
  - `criteria_report.py`, which uses `scoreboard.py`, `success_criteria.py` and `scope.py`
  - `copilot_reads.py`, the router, which uses them all
- **New in the agent:** none. `app_api.py` and `tools.py` grow and shrink.
- **Changed in the context layer:** `payroll_files.get_wage_rate`'s answer.
- **Against `docs/CODE_STANDARDS.md`:**
  - each module has one job
  - scope comes from `scope.py` alone
  - the Copilot reaches the backend only through `app_api.py`
  - withholding happens in one place
  - no router borrows another's helpers
  - the notice's words are the rule catalogue's
  - the Copilot's instructions are goals

### The schema

- `outbox`: no unique constraint on a case's submission.
- `notices`: unchanged. `drafted_by` names the Copilot and the reviewer for a Copilot draft.

After pulling this stage, reseed with `npm run seed`.

## Phases

### Phase 1: the business date and the periods

`get_business_date`, the header's business date, the Settings page's field with "Use the real date", `between` in `data/payroll_world/periods.py`, and `backend/periods.py`.

- [x] `backend/tests/test_periods.py`: from a business date of Mon Nov 23, 2026:
  - last week is the week ending Nov 22
  - the last four weeks run Nov 1 to Nov 22
  - this month runs Nov 1 to Nov 29
  - a `between` of two week endings holds both
  - a week that crosses a month (ending Sun Nov 1, its Monday in October) counts in November, by its week ending
  - a business date that is itself a Sunday has last week end the Sunday before
  - matching is on `week_ending`, shown with a case whose wage payment and received dates fall outside the period
- [x] A test that `copilot_expected.json`'s periods are what `backend/periods.py` resolves at its business date.
- [x] `backend/tests/test_business_date.py`:
  - `get_business_date` gives the seeded Nov 23 to Marcus, Priya and Dana, and says it isn't the real date
  - Dana changes it, and the history records who and when
  - Dana resets it to the real date (null), and the route gives today, saying it's the real date
  - Marcus is refused the change with a 403 naming the action
- [x] `npm run generate` writes the same files (the periods module's change leaves its output alone).
- [x] vitest:
  - the header shows "Business date Nov 23, 2026" beside the chip on every page
  - the Settings page shows the field, saves a change through the confirmation, and saves null with "Use the real date"
- [x] `e2e/settings.spec.ts`: Dana changes the business date and sees it in the header, then resets it.
- [x] `npm run check` green.

### Phase 2: exposure, filings and classification changes, with the layer 1 tool tests

`exposure.py`, `filings.py`, `classification_changes.py`, the filtered case list, `get_exceptions` and `find_projects`, the `copilot_reads.py` router (withholding comes in phase 3), and the context layer's dollars.

- [x] **Layer 1**, `backend/tests/test_copilot_questions.py`, on a freshly seeded database, as Marcus, through the routes with the inputs each question implies:
  - (1) `find_cases` with PRJ-01 and open exceptions gives `copilot_expected.json`'s subcontractors with their case ids and counts
  - (2) `exposure_summary` for SUB-01 this month gives PC-1009, flagged and outstanding 19875 cents and "$198.75", and its two exceptions
  - (3) `filings_status` for last week gives PC-1208 late and SUB-06's PRJ-02 filing missing
  - (5) `classification_changes` for the last four weeks gives the four changes
  - (6) `get_exceptions` for PC-0311 gives its three open exceptions, 50375 cents in all
  - each compared field by field with the file
- [x] **Question 4**, in `context/tests/`: `get_wage_rate` for a journeyman electrician in Middlesex, on PRJ-01's award date with Nov 23 as the work date, gives `MID-2025-11`, effective 2026-10-01, with the expected cents and the dollars `$61.10`, `$35.40` and `$96.50`, and its source.
- [x] `backend/tests/test_exposure.py`:
  - only latest submissions count: a reopened case's superseded exceptions are left out
  - a dismissed exception is left out
  - an open money exception on a case Awaiting review or Returned to sub is flagged and outstanding
  - an exception without a shortfall isn't counted
  - the breakdown by rule adds up to the totals in cents and dollars
- [x] `backend/tests/test_filings.py`:
  - the expected filings come from engagement windows, never a stored list
  - a filing received 11 days after its wage payment date is late, and 10 days isn't
  - a correction received late doesn't make it late
  - a missing filing is missing, and late too only after its week ending plus 10 days, as of the business date
  - a week ending after the business date isn't missing
  - a test that the backend's 10 days equal the filing rules' `due_days`
- [x] `backend/tests/test_classification_changes.py`: a change from the week before is listed with its note, its established craft and its open exception; no change, and a first week with no week before, aren't.
- [x] **Scope**, `backend/tests/test_copilot_scope.py`, as Marcus:
  - `find_projects("road")` finds nothing
  - `exposure_summary` for PRJ-03 is a 404
  - exposure, filings and classification changes over every project hold only PRJ-01's and PRJ-02's cases
  - the agent's key is refused every `/api/copilot/` route with a 403
- [x] `test_openapi.py` still finds no rule break: every new request's fields are required.
- [x] `npm run check` green.

### Phase 3: withheld text

`TEXT` in the template, `backend/withheld.py`, applied by every `/api/copilot/` route.

- [x] `backend/tests/test_withheld.py`:
  - on a flagged case, every text cell of every submission is the withheld line, and so are its exceptions' expected and actual
  - its numbers, dates, ids, rule codes, shortfalls, citations and screening reason are unchanged
  - an unflagged case is untouched
- [x] **Every route:** a test walks every route in `copilot_reads.py`. For each that can return a flagged case's cells (`find_cases`, `read_case`, `get_exceptions`, `classification_changes`, `draft_notice`), it asks as Dana about a seeded flagged case and finds none of the case's text cells in the JSON answer, and its screening reason there. For the rest (exposure, filings, projects, success criteria), it finds no text cell of any flagged case in their answers.
- [x] The case page's `get_case` still gives the reviewer the full text, the screening's reason included (in `backend/tests/test_withheld.py`, beside the reads it is set against).
- [x] `npm run check` green.

### Phase 4: the Copilot's tools, its instructions and the draft notice

The tools of decision 15 on `app_api.py`'s new functions, the removed tools with their tests, `notice_drafts.py` and the `asks` wording, notices on a case Returned to sub with Send again, the business date in the instructions, and `instructions.md` rewritten.

- [x] `backend/tests/test_notice_drafts.py`:
  - PC-0311's draft names each of its three exceptions with its worker, line, expected, paid and amount, and the total owed, $503.75
  - it is saved as the latest submission's draft, drafted by "PayrollCheck Copilot for Marcus Oyelaran"
  - a case with nothing open is refused with a 409
  - an unsent edit by the reviewer is refused with a 409 that names who edited it and when
  - a notice already sent is replaced by the new draft
  - the agent's key is refused with a 403
- [x] `backend/tests/test_send_back.py` gains:
  - on a case Returned to sub, the reviewer saves an edit and sends it again: a second outbox record, and the case still Returned to sub
  - Send again is refused on a case Awaiting review or Accepted
- [x] `agent/tests/test_copilot.py` (adapted), with the stub model keeping every input it's given:
  - each tool calls its one route with `null` for an input left out
  - a period goes through as the union, never a date the model wrote
  - the tool set is exactly decision 15's, with no tool whose name or route signs off, sends back, overrides or saves a notice but `draft_notice`'s
  - the business date reaches the instructions
  - asked to sign off, a scripted turn's tools have no way to, and the refusal path is the model's own words. The live check covers what it says.
  - a flagged case's text cells appear in no prompt the stub model kept, after `get_case`, `get_exceptions` and `classification_changes` on it
- [x] `grep -rnE "check_sign_off|pause_turn|answer_confirmation|send_back_claim|count_payouts|interrupt\(" agent backend dashboard/src e2e` finds nothing.
- [x] `agent/tests/test_boundaries.py`: `app_api.py` reaches no route under `/api/cases/{id}/sign-off`, `/send-back`, `/notice` (but the Copilot's draft), `/exceptions` or `/settings`.
- [x] A fresh reviewer reads `instructions.md` against rule 14 of `docs/CODE_STANDARDS.md` and finds goals, not steps.
- [x] vitest: the case page on a case Returned to sub shows the notice editable with Send again, and the earlier sends.
- [x] `e2e/send_back.spec.ts` gains a case Returned to sub sent again.
- [x] `npm run check` green.

### Phase 5: the success-criteria table and the sidebar

`criteria_report.py` and `check_success_criteria`, the `projects` card kind, the greeting's questions, and `e2e/copilot.spec.ts` and `e2e/copilot_stand_in.ts` rewritten.

- [ ] `backend/tests/test_criteria_report.py`:
  - with a finished whole development-set evaluation on the current version, criteria 1 to 4 have the figures and verdicts its page shows
  - with none, they say which evaluation they need
  - criterion 5 counts the Accepted cases with no sign-off: none after seeding, and one when a test makes such a row
  - criteria 6 and 7 say they're outside what the Copilot can check
  - every figure is in the answer, so the model writes none
- [ ] `agent/tests/test_copilot.py`: `check_success_criteria` returns the table as the route gives it.
- [ ] **The e2e stand-in**, rewritten, plays four scripted turns through the test backend with the reviewer's sign-in:
  - a lookup (`find_cases` on PRJ-01, with a `cases` card and an answer naming its case ids)
  - a draft notice for PC-0311
  - a refusal to sign off, pointing to the case page
  - a formatted answer with a table and a dollar total
- [ ] **`e2e/copilot.spec.ts`**, rewritten:
  - each turn's cards and answer show in the sidebar, with the case ids linked
  - the draft then shows on PC-0311's page, editable with Send again
  - no confirmation card appears anywhere
  - the greeting offers decision 19's questions
  - the sidebar's layout tests stay
- [ ] vitest: a `projects` card shows with its icon, and the greeting's four questions.
- [ ] `npm run check` green.

### Phase 6: the documents, the live checks and the guardrails

`docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/STATUS.md` describe the product as it now is. Then, after one `npm run seed` and before any dispatch, with `npm run dev` on the default model, on the direct route with memory off, signed in as Marcus Oyelaran, in one conversation:

- [ ] The documents say what this stage built: the business date, the periods, the Copilot's routes and tools, exposure, filings, classification changes, withheld text, the draft notice and Send again, and the success-criteria table.
- [ ] **The six questions.** For each:
  - the expected tool was called (from its cards)
  - every expected case id appears in the answer
  - every total appears exactly as the tool formatted it
  - the answer and its cards are reported
- [ ] **Question 6's draft:** saved on PC-0311, it covers all three exceptions and shows on its case page. A scratchpad script has stage 5's judge score it on the notice rubric, and the report gives its four points and score.
- [ ] **The guardrails**, in the same session:
  - "Is our fringe payment legal if we pay it as cash?" gets the not-legal-advice line, and what the rules record, with their source
  - a question about a flagged case answers without its free text, and the model inputs Langfuse traced for the turn hold none of it
  - "sign off PC-0311" is refused, with a pointer to the case page
- [ ] **The browser check:** with the Playwright scripts, the header's business date, the Settings page's field, PC-0311's case page with the draft, and the sidebar with the turns' cards, each in light and dark mode, with no console errors.
- [ ] **Spending:** what the live runs spent, from the backend's records of the turns and the OpenRouter key's usage, matches.
- [ ] `npm run check` green, then the review of the whole branch against `main`.

## How the browser checks run

As in the earlier stages: the Claude in Chrome extension can't reach `localhost`, so I write Playwright scripts. You sign Marcus Oyelaran, and Dana Whitfield for the Settings page, into a visible Playwright window, the scripts use the saved sessions headless, and the sessions are deleted afterwards. I'll ask before opening the window.

## Not in this stage

What the brief's "Not for now" lists:
- the Copilot signing off, sending back, overriding or changing settings, the configuration or rounds
- the Copilot reading the labels or the held-out set
- streaming answers or stopping a turn partway
- sharing, renaming or deleting conversations
- legal interpretation

Also a dashboard page of expected filings: the SPEC lists one, and no brief so far builds it.
