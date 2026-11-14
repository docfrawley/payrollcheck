# Review and access: overrides, notices and who sees what

From the compliance manager at Pinelands Builders, with our IT team.

A note on names: this brief uses the file and table names as stage 1 renamed them (UnderCover to PayrollCheck, claim to case, handler to reviewer), so `data/handlers.json` is `data/reviewers.json`, `e2e/handlers.ts` is `e2e/reviewers.ts`, and so on. Where a file here doesn't exist under exactly that name, use the one stage 1 or stage 3 left in its place. The words are those in `CONTEXT.md`.

## Where we're heading

After stage 3 the payroll agent checks every Received case and writes its exception report and a draft send-back notice, and a reviewer can open the case and press Sign off or Send back. That's enough to show the agent working, but not enough to work our queue on a Monday morning.

Our reviewers need to correct the agent: dismiss an exception it got wrong and add one it missed, with a reason we can read later. They need to edit the notice before it goes to the subcontractor, and see exactly what was sent. A corrected payroll has to reopen the case, even one we already accepted. And each reviewer should see only the projects they're assigned to, as they would in any system we'd let near our payroll records.

This stage also takes out the last of UnderCover's review flow: sending a decision back to the agent, and the paused graph waiting for a sign-off. In PayrollCheck the agent's run ends when it writes the report. A person corrects the report; the agent is never asked to look again.

## What we want

1. **Overrides.** On the case page a reviewer can dismiss any open exception, with a reason, or add an exception the agent missed, with a reason. An added exception uses a rule code from our catalogue in `CONTEXT.md`, with its severity and the worker and line it applies to, and is recorded as raised by that reviewer. Every override is logged with who made it, when and why, and the case page lists them beside the exceptions they changed. Overrides never touch the ground-truth labels in `data/evals/` or the seeded labels in the database: the labels are what the agent is scored against, and nothing in this stage writes to them. The improver will read the override log in stage 5, so keep it complete and queryable by date.

2. **The send-back notice.** The payroll agent's draft notice is saved on the case, as stage 3 left it. On the case page the reviewer edits it in place and can save the edit without sending. Keep the draft as the agent wrote it and the text as the reviewer sent it, both, so the edits can be read later.

3. **Send back writes to the outbox.** Pressing Send back makes the case Returned to sub and writes one outbox record: to (the subcontractor's payroll contact from our records), subject, body (the notice as edited), sent by and sent at. The case page shows the sent notice as an email preview, with its to, subject, sender and time. No real email is sent. Seeded payroll contacts use `.example` domains. All sending goes through one function, `deliver(outbox_row)`, which for now does nothing beyond the record; it's the single place a real email provider would plug in later.

4. **Sign off only when no exception is open.** Sign off makes the case Accepted, and the backend refuses it while any exception on the latest submission is open, saying how many are. The reviewer dismisses each one first, with a reason. A case with a screening flag, or one the agent failed twice, is worked the same way by hand: the reviewer may add exceptions, and signs off only once none is open.

5. **A new submission reopens the case.** An upload for a subcontractor, project and week that already has a case adds a new submission to that case, whatever its status, Accepted included. The case goes back to Received, the previous submission's open exceptions become superseded, and the next dispatch gives it a fresh agent run on a new thread, never a resume of the old one. Superseded exceptions stay visible on the case page under their own submission, but count for nothing: sign-off looks only at the latest submission. Dismissed exceptions on an earlier submission stay dismissed.

6. **No sending back to the agent.** Stage 3 takes out the claim graph's pause and the sent-back records. Make sure nothing of Ed's send-back-to-agent flow or the `interrupt()` and resume that waited for a sign-off is left, and remove whatever is:
   - the `wait_for_handler` node and its resume in `agent/harness.py`
   - `agent/handler_answer.py`
   - `backend/sent_back.py` and its table
   - the routes and dashboard pieces that sent a decision back with a note to the agent (`dashboard/src/SendBack.test.tsx` and what it tests)
   - the resume work in `agent/work.py` and `backend/agent_work.py`

   Delete their tests in the same commit as the code (`agent/tests/test_send_back.py`, `agent/tests/test_pause.py`, `backend/tests/test_send_back.py` and any others that test only the removed flow), with the replacements written in this stage. Durable state still covers resuming a run that was interrupted by a crash or a restart.

7. **Two roles.** `reviewers.role` is `reviewer` or `compliance_manager`, replacing `can_approve_over_limit` in the table, in `data/reviewers.json` and in the models. The `senior(action)` dependency in `backend/dependencies.py` becomes a compliance-manager check, refusing anyone else with a 403 that names the action. The compliance manager can do everything a reviewer can, and alone starts and stops improvement rounds, approves or rejects the improver's proposals, and changes Settings. The Scoreboard and its evaluations are visible to every reviewer. The Improvement and Settings pages are the compliance manager's alone: a reviewer can't open them, and the backend refuses their reads and actions as well.

8. **Project assignments.** A new table, `project_reviewers(reviewer_id, project_id)`, holds who reviews which project. Seeding loads it from `data/reviewers.json` (or a file beside it, as the plan chooses):
   - Dana Whitfield, compliance manager, all projects
   - Marcus Oyelaran, reviewer: the Lincoln School renovation and the municipal building
   - Priya Raman, reviewer: the road resurfacing

   Their emails move to a PayrollCheck example domain. Assignments come from the seed; this stage adds no page for changing them.

9. **One scope, applied everywhere.** One backend function, `scope_of(reviewer)`, returns the projects a person may see and act on: their assignments, or every project for the compliance manager. Every query helper and every write applies it: cases, submissions, exceptions, overrides, notices, the outbox, uploads, subcontractors, workers, and the later reads for exposure, filings and classification changes, which must use the same function when stage 6 adds them. An id outside a reviewer's scope answers 404, with the same message as an id that doesn't exist, never 403. An upload to a project outside their scope is not found as well.

10. **The Copilot inherits it.** The Copilot already calls our app with the reviewer's own sign-in, so it sees exactly what the reviewer sees, through the same `scope_of`. Nothing about scope is left to its instructions.

11. **Dispatches work the whole queue.** A dispatch works every Received case, oldest first, whoever starts it, as SPEC.md says. The dispatch panel and the dispatch's summary show the person who looks at it only the cases in their scope, with their cost and time, plus a count of the cases worked on other projects ("and 8 cases on other projects").

12. **The agent's key.** The payroll agent's API key stays unscoped, so it can work every case. It can never take a person's action: sign off, send back, dismiss or add an exception. Those routes take a reviewer's sign-in only, and a request carrying the key is refused, as `signed_in_handler` in `backend/dependencies.py` already refuses it today.

## Our IT team's choices

- **Overrides are rows of their own**, in the `overrides` table stage 3 created: the exception, the case and submission, the kind (dismissed or added), the reviewer, the time and the reason. Dismissing sets the exception's status to dismissed; adding inserts an exception with `raised_by` the reviewer. An override is never edited or deleted. The plan chooses whether a dismissal can be undone and how that is recorded, without ever deleting the earlier row.
- **Notices and the outbox.** Stage 3's `notices` table holds the draft, the edited text, and who sent it and when; this stage fills in all of it, and adds an `outbox` table for what was sent. The outbox row is written and `deliver(outbox_row)` called in the same request as the status change, so a case is never Returned to sub without its record.
- **`scope_of` lives in one module** of the backend, and every router takes it from there. A query that reaches a case, a submission or anything hanging off them joins on the case's project and filters by the scope. The scoping tests reach every route that takes an id, so a new route without scope fails a test. Follow the API rules in `docs/TECH_STACK.md` for the new routes: an `operation_id`, a one-line docstring and no optional inputs.
- **Roles reach the dashboard** with the signed-in reviewer, as `can_approve_over_limit` does now, so the navigation shows Improvement and Settings only to the compliance manager. The backend still checks every action.
- **The status change and the checks are in code.** Sign off checks for open exceptions, and a new submission reopens and supersedes in the same transaction as its insert, as one move in `backend/records.py` or its successor. Two reviewers pressing Sign off at once accept the case once.
- **Browser checks sign in as Marcus Oyelaran** to act as a reviewer, as the demo will, and as Dana Whitfield for anything only the compliance manager can do. Update `docs/PROCESS.md` to say so, in place of Ed's "a handler who can't sign off over the limit".

## What stays the same

- The rules in `docs/SPEC.md`. Our reviewers sign in with their email and password, and the system checks the reviewer and their projects on every action.
- The payroll agent, its check tools and screening, and the exception report it writes. The agent flags; it never accepts.
- The dispatcher, the swarm of up to 25, durable state, retries and the heartbeat, and one dispatch, evaluation or round at a time.
- The Scoreboard and evaluations on labeled copies, which stage 3 built. Evaluation copies don't appear in the queue.
- The API rules in `docs/TECH_STACK.md`, and `docs/CODE_STANDARDS.md`.
- Tests never call a model, Supabase Auth or AWS, and `npm run check` never reads `.env`. The bars in `docs/PROCESS.md` stay where they are, and the test rule in `docs/ROADMAP.md` applies: a test for code that survives is adapted here; a test for code removed here is deleted in the same commit, with its replacement.
- `npm run seed` rebuilds everything, the assignments, overrides, notices and outbox included.

## What done looks like

- `npm run check` is green with `.env` moved out of the way. Tests on a stub model and the stand-ins cover:
  - a dismissal and an added exception each logged with who, when and why, and a request to change a label refused or impossible; the labels unchanged after a run of overrides
  - Sign off refused while one exception is open, and accepted once it's dismissed; two sign-offs at once accepting the case once
  - Send back writing one outbox record with the subcontractor's payroll contact, subject, the edited body, sender and time, and `deliver` called once with it; the draft and the sent text both kept
  - a new submission on an Accepted case: the case back to Received, the earlier submission's open exceptions superseded and its dismissed ones still dismissed, and the next dispatch running it on a new thread
  - the roles: Marcus and Priya refused rounds, proposals and settings with a 403, and refused the Improvement and Settings reads; Dana allowed them; every reviewer able to read the Scoreboard
  - scope: for every route that takes an id, an id on a project outside the reviewer's scope answers 404 with the not-found message; the queue, subcontractors, workers and uploads filtered to the scope; the compliance manager seeing every project
  - the agent's key refused on Sign off, Send back and both kinds of override, and still able to work a case on any project
  - a dispatch started by Marcus working all 24 week-12 cases, with its summary showing him his own and a count of the others
  - the Copilot, signed in as Marcus, getting not found for a road-resurfacing case
  - nothing left of the send-back-to-agent flow: no route, no table, no `interrupt()` in the payroll agent's graph
- The end-to-end tests:
  - Marcus can't see a road-resurfacing case in the queue, and opening its page gets the not-found page (404 from the API)
  - a dispatch started by Marcus works all 24 week-12 cases against the agent's stand-in, and his panel shows his cases and the count of the rest
  - `e2e/send_back.spec.ts` is rewritten: a reviewer edits the draft notice, presses Send back, and sees the case Returned to sub with the email preview
  - a reviewer dismisses an exception with a reason and signs off; Sign off is disabled while an exception is open
  - a corrected CSV uploaded for an Accepted case reopens it to Received
  - Priya sees no Improvement or Settings in the navigation; Dana does
- After one `npm run seed`, with `npm run dev` running on the default model, checked through the Playwright MCP server:
  - Signed in as Marcus, start a dispatch of the week-12 wave, then open one of his cases with exceptions. Dismiss one with a reason, add one, edit the notice and send it back; the email preview shows. On another clean case, sign off.
  - Upload a corrected CSV for a case Marcus has accepted. It reopens; the next dispatch checks it again, and the earlier exceptions show as superseded.
  - Signed in as Priya, the queue shows only the road resurfacing, and the URL of Marcus's case shows not found.
  - Report what the runs spent.
- `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md`, `docs/CODE_STANDARDS.md`, `docs/STATUS.md` and `data/README.md` describe the product as it now is.

## Not for now

- Sending real email. The outbox and `deliver(outbox_row)` are as far as it goes.
- A portal or reply channel for subcontractors.
- A page for assigning reviewers to projects.
- The improver reading the overrides: that's stage 5.
- The Copilot's new tools, the business date and exposure: that's stage 6.
- Asking the payroll agent to re-check a case. A reviewer overrides instead; a new submission gets a fresh run.

## Planning

Follow `docs/PROCESS.md`, but write this plan to `docs/PLAN_REVIEW.md` and tick it off there. Plan five or six phases and commit at the end of each. Start with the roles, `project_reviewers` and `scope_of`, so every later route is built scoped. Then clear out anything left of the send-back-to-agent flow and the sign-off pause, then overrides and the sign-off rule, then notices, Send back and the outbox, then reopening on a new submission, and last the dispatch panel's scope, the end-to-end tests and the live checks, after reseeding once.
