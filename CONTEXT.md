# PayrollCheck — domain glossary

The ubiquitous language for PayrollCheck. Code, tables, routes and UI use these terms; UnderCover's vocabulary (claim, payout, policy, customer) does not survive into the product.

## Terms

**Case** — The unit of work in the queue: one subcontractor's certified payroll obligation for one project and one week. A case moves through the statuses Received → Awaiting review → Accepted or Returned to sub. The dispatcher works cases; tables and plumbing say `case` (e.g. `cases`, `run_cases`, `held_out_cases`).

**Payroll** — The certified payroll document itself: the MW-562 payroll certification plus the payroll register for that week. Said of the document, never of the queue unit.

**Submission** — One upload of a payroll into a case. A case holds one or more submissions, numbered in order; a corrected upload after Returned to sub is a new submission on the same case, which reopens it.

**Intake** — Turning an uploaded CSV (one flat template, one row per worker-week line, certification repeated on every row) into a submission, by a deterministic parser with no model. The reviewer uploads on the subcontractor's behalf. A No Work Week filing is one row with the certification filled, the worker columns blank and `no_work_week` set to `true`, and becomes a submission with zero lines. Intake rejects only a file that can't become a submission (not CSV, missing columns, certification differing between rows, unparseable value, unknown project); an *intake error* creates no case. Anything a valid file says that the rules forbid is accepted and becomes an exception.

**Payroll agent** — The agent that checks a case's latest submission and writes its exception report. It flags; it never accepts.

**Reviewer** — The general contractor's compliance reviewer: works the queue, signs off or sends back each case, asks the Copilot. Replaces UnderCover's *handler*. UI copy may say "compliance reviewer".

**Compliance manager** — The reviewer's senior: approves or rejects the improver's proposed configuration changes and watches exposure by project. Replaces UnderCover's *senior handler*.

**Subcontractor** — The firm whose crew's wages a payroll certifies; submits payrolls but does not use the dashboard. Always `subcontractor` in code (never `sub`, which collides with subtract/subscription); "sub" is allowed in UI copy and notices. Replaces UnderCover's *customer*.

**Sign off / Send back** — The reviewer's two actions on a case awaiting review: Sign off makes it Accepted; Send back makes it Returned to sub, with a notice to the subcontractor.

**Send-back notice** — The plain-language message to the subcontractor that goes with Send back. Drafted by the payroll agent (or the Copilot on request), edited by the reviewer, and sent only when the reviewer presses Send back on the case page.

**Override** — A reviewer's correction to the payroll agent's exception report: dismissing an exception (a false positive) or adding one (a miss). Every override is logged with who, when and why, and is a signal for the improver. Overrides never rewrite ground-truth labels. The agent is never sent a case back to re-check; the reviewer overrides instead.

**PayrollCheck Copilot** — The sidebar chat for reviewers. Reads, drafts send-back notices, and starts dispatches and evaluations; never signs off or sends back.

## Renaming rule

A term with a PayrollCheck counterpart is renamed (above; also `UNDERCOVER_*` → `PAYROLLCHECK_*`, packages → `payrollcheck`). A term with no counterpart — *policy*, *plan*, *payout*, *payment* — is not renamed but replaced by what the domain model defines (project, wage rate, filing rule, exception, shortfall) or dropped.

## Records and context

**Context layer** — Reference data the GC doesn't own, as read-only files served by the compliance context server and cited by every answer: rate determinations, the contractor registry, apprentice registrations, filing rules, glossary. **App records** — what the GC owns, in the database, reached by the agent only through the app: projects, subcontractors, workers, cases, submissions, exceptions, overrides, notices.

**Rate determination** — NJDOL's published rates for a county and craft, with dated rows (wage, fringe, total), the craft's overtime rules (as data) and apprentice schedule. The rate for a line is the determination in force on the project's **award date**, taking its latest row dated on or before the work date.

**Engagement window** — The first and last week a subcontractor is on a project. Every week in it needs a filing, a "No Work Week" filing (a submission with no lines) included.

**Expected filing** — A (subcontractor, project, week) inside an engagement window. Computed, never stored. **Missing** = expected with no case; **late** = filed, its first submission received, more than 10 days after the wage payment date, or missing past that deadline. A correction never makes a payroll late, nor a late one on time (`context/filing_dates.py`).

**Established craft** — A worker's craft in the GC's records, from their first payroll on the job or the apprentice registry. Paying them under a lower-paid classification is a misclassification.

## Case lifecycle

Statuses: **Received** → **In progress** → **Awaiting review** → **Accepted** or **Returned to sub**. A case flagged by the hidden-instruction screening (*screening flag*) or failed twice by the agent (*agent failed*) reaches Awaiting review with that flag and is worked by hand. Any new submission — even after Accepted — reopens the case to Received, and the previous submission's open exceptions become **superseded**. Sign off requires no open exceptions: each must first be dismissed with a reason (an override).

## Exceptions

**Exception** — One rule breach found in a submission: rule code, severity (high / medium / low), worker, line, expected vs actual, shortfall, citation, raised by (agent or reviewer), status (open, dismissed, superseded). Rule codes: `form.missing_field`, `form.unsigned`, `form.project_mismatch`, `registration.inactive`, `rate.base_short`, `rate.fringe_short`, `overtime.underpaid`, `arithmetic.hours_total`, `arithmetic.gross`, `apprentice.unregistered`, `apprentice.ratio`, `timeliness.late`, `sequence.gap`, `classification.changed`, `classification.mismatch`. A hidden instruction is a screening flag, not an exception.

**Shortfall** — The dollars underpaid on an exception, in integer cents, always computed by a check tool, never by the model.

**Check tool** — Deterministic code for one check (e.g. `check_rates`, `check_overtime`), returning **candidate findings** with expected, actual, shortfall and citation filled in. The payroll agent runs them in order, judges fuzzy cases, may dismiss a candidate with a reason, may add non-money exceptions, and writes the notice — but can never create an exception with a shortfall that no tool found, nor add one under a rule its check alone decides (`timeliness.late`, `sequence.gap`): those come only from the check's finding. A reviewer may still add either as an override. Tools read tunable config parameters (e.g. a rounding tolerance) that the improver may propose changing.

## Synthetic data and scoring

**Generator** — `data/generate.py`, deterministic (fixed seed): builds a clean world, then applies the **error manifest** (`data/error_manifest.yaml`: case → rule → worker/line → corruption) and writes ground-truth labels from it. Its output is committed; seeding only loads it. Written by the coding agent during the build.

**Development set** — The brief's world (Pinelands Builders, 3 projects, 8 subcontractors, ~200 payrolls over 12 weeks): the seeded history, the demo wave, what the improver learns from, and where the success criteria are measured. **Held-out set** — A second generated world (different seed and subcontractors, same counties, crafts and error mix, ~100 payrolls), used only by the improver's keep/rollback gate. **Tiny set** — ~10 development payrolls, one per check family plus one hidden instruction, for free models.

**Decoy** — A seeded payroll that looks wrong but is clean (e.g. correct daily overtime, the pre-listed rate increase week, a later determination that must be ignored). Flagging one is a false exception.

**Ground-truth label** — `case_id, rule, worker_id (null for case-level rules), line_no, expected_shortfall_cents`, or "expected screening flag". An exception is **caught** when an open exception matches its case, rule code (exact, not family) and worker; its **shortfall is correct** when it equals the label to the cent; an open exception matching no label is a **false exception**.

## Copilot

**Business date** — The app's "today": a setting that defaults to the real date; seeding pins it to the Monday the week-12 wave arrives. Every relative period ("last week", "this month", the last N weeks, missing, late) is resolved from it in code, always matched on a payroll's `week_ending`.

**Exposure** — From each case's latest submission only (superseded never counted; dismissed excluded): **flagged** = money exceptions not dismissed; **outstanding** = those still open on cases Awaiting review or Returned to sub. In cents, with contributing case IDs.

**Withheld text** — On a case with a screening flag, app tools replace every text cell of its submissions with `[withheld: screening flag — see case page]`, in backend code, before any model sees it. Numbers, dates, IDs and the screening reason still pass.

## Access

**Role** — `reviewer` or `compliance_manager` (replaces Ed's `can_approve_over_limit`). **Scope** — The projects a person may see and act on: a reviewer's assigned projects (`project_reviewers`), or every project for the compliance manager. `backend/scope.py` alone applies it to every query and write; an out-of-scope ID is a 404. Its queue holds no evaluation's copy: only opening a case by its id and reading a run's cases reach the copies, by asking for them. The Copilot inherits it through the reviewer's own sign-in. Dispatches work the whole Received queue but show the starter only their scope; the agent's API key is unscoped but never takes a person's actions.

**Outbox** — Where a sent notice is recorded: to (the subcontractor's payroll contact), subject, body, sent by, sent at, shown on the case page as an email preview. No real email is sent; seeded contacts use `.example` domains. A real provider would replace one `deliver(outbox_row)` function.
