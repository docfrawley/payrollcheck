# The PayrollCheck Copilot, for payroll questions

From the compliance manager at Pinelands Builders, with our IT team.

A note on names: this brief uses the file and table names as stage 1 renamed them (UnderCover to PayrollCheck, claim to case, handler to reviewer), so `agent/copilot/needs_a_handler.py` is whatever stage 1 named it, and so on. Where a file here doesn't exist under exactly that name, use the one an earlier stage left in its place. The words are those in `CONTEXT.md`.

## Where we're heading

The Copilot in `agent/copilot/` is Ed's: a hand-written LangGraph graph in a sidebar on every page, acting as the reviewer who asked, with their sign-in, its steps shown as cards and its conversations kept. All of that carries over. Its tools still speak about claims, payouts and policies, and it can still sign off through a confirmation card. Neither belongs in PayrollCheck.

Our reviewers' questions cut across projects, subcontractors and weeks: who has open exceptions on a job, how much underpayment we've flagged for a sub this month, which payrolls are late or missing, what the rate table says, whose classification changed. Each one takes several pages today. We want the Copilot to answer them in one message, with the case ids and the rate records it used, and with every dollar total and date coming from our app, never from the model's arithmetic. And it should draft the send-back notices our reviewers spend their mornings writing, leaving the decision on the case page, where it belongs.

## What we want

1. **The business date.** The app has a business date, its "today": a setting that defaults to the real date. Seeding pins it to the Monday the week-12 wave arrives (stage 3 may already seed it; build on what's there). It shows in the header of every page beside the "Synthetic data — not real rates" chip. The compliance manager can change it, or reset it to the real date, on Settings, with who changed it and when, like every other setting.

2. **Periods are resolved in code.** Every relative period, "last week", "this month", "the last four weeks", missing and late, is resolved by the backend from the business date, and always matched on a payroll's `week_ending`. "Last week" is the latest payroll week ending before the business date: week 12 at the seeded date. The Copilot passes symbolic periods (`last_week`, `this_month`, `last_n_weeks:4`, or a date range) and never computes a date. The resolution is the shared periods module stage 2 wrote for the generator, reused here by the backend, so `data/copilot_expected.json` and the tools can't disagree; every tool that takes a period and the dashboard's own pages use it.

3. **The app tools.** Each acts as the signed-in reviewer, through stage 4's `scope_of`, and goes through `agent/copilot/app_api.py` with their sign-in:
   - `list_cases(project?, subcontractor?, status?, period?, has_open_exceptions?, flag?)`
   - `get_case(case_id)`
   - `get_exceptions(case_id)`, with each exception's citation
   - `exposure_summary(project?, subcontractor?, period?)`
   - `filings_status(period, project?)`: missing, late and on time
   - `classification_changes(period, project?)`
   - `find_subcontractors(name)` and `find_projects(name)`
   - `draft_notice(case_id)`, which saves the draft on the case
   - `start_dispatch` and `start_evaluation`, kept from Ed

   Alongside them it has every compliance context server tool, on the route the payroll agent takes: through the AgentCore Gateway when it's set up, or straight to the context layer when it isn't. The question marks are the tools' optional inputs as the model sees them; the routes behind them follow the API rules in `docs/TECH_STACK.md`, with no optional inputs. Add the reads our app doesn't have yet.

4. **Exposure.** `exposure_summary` counts each case's latest submission only; superseded exceptions are never counted and dismissed ones are excluded.
   - **Flagged** is every money exception not dismissed.
   - **Outstanding** is the part of that still open on cases Awaiting review or Returned to sub.

   Both are in cents, formatted as dollars by the tool, with the contributing case ids and a breakdown by rule.

5. **Filings and classification changes.** `filings_status` works from the expected filings (each subcontractor's engagement window on each project), never a stored list: missing is expected with no case; late is filed more than 10 days after the wage payment date, or missing past that deadline, both as of the business date. `classification_changes` lists each worker whose classification changed in the period, with the cases it shows in; the plan says what else each row carries.

6. **It drafts, starts and reads; it never decides.** The Copilot drafts a send-back notice and saves it on the case, where the reviewer edits it and sends it from the case page, as stage 4 built. It starts dispatches and evaluations, waits for them in code as Ed's does (`agent/copilot/waiting.py`), and says what needs a reviewer afterwards. It never signs off, sends back or overrides. Asked to, it says it can't and points to the case page. Remove:
   - Ed's sign-off schema, the `check_sign_off` and `confirm` nodes and the `interrupt()` in `agent/copilot/graph.py`
   - the confirmation card, its route and its record: `answer_confirmation` and `pause_turn` in `backend/copilot.py` and `app_api.py`, and the card's fill-in in `backend/conversations.py`
   - the card in the sidebar and its tests
   - `send_back_claim` and whatever of the claim, policy, customer and payout tools stage 3 left standing
   - `count_payouts_over_limit`

   Delete their tests in the same commit, with the replacements written in this stage.

7. **The success criteria, rebuilt.** Ed's `agent/copilot/criteria.py` answers "Are we meeting the success criteria we agreed?" with a table worked out in code. Rebuild it around the criteria in `docs/SPEC.md`, measured on the development set: each criterion with its target, its figure from our records or an evaluation's measures, and whether it's met, with every figure worked out in code and the model writing only the words around them. The plan says which criteria the Copilot can figure from our records or an evaluation, which it reports as outside what it can check, and which evaluation it starts.

8. **Withheld text.** On a case with a screening flag, the backend replaces every text cell of its submissions with `[withheld: screening flag — see case page]` before any app tool returns it, so no model sees it. Numbers, dates, ids and the screening reason still pass. This happens in backend code at the tool boundary, never in the Copilot's prompt. The case page shows the reviewer everything, with the suspicious cell highlighted.

9. **No legal advice.** Asked for an interpretation of the law, the Copilot says it isn't giving legal advice, and can still say what our rate table or filing rules record, with their source.

10. **It remembers each reviewer**, as Ed's does, with a namespace for each reviewer in the Copilot's AgentCore Memory, when its setting is there. It works the same without it.

11. **Every answer cites.** Each answer names the case ids and the rate records it used, and every total appears exactly as the tool formatted it.

## The six questions

The Copilot must answer these, signed in as Marcus Oyelaran, with the right case ids and totals:

1. "Which subs on the Lincoln School renovation have open exceptions?"
2. "How much underpayment have we flagged for Garden State Electric this month?"
3. "Which payrolls are late or missing for last week?"
4. "What's the journeyman electrician rate in Middlesex County in our rate table, and since when?"
5. "Show me every worker whose classification changed in the last four weeks."
6. "Draft a send-back notice for PC-0311 covering all three exceptions."

Stage 2's generator wrote the expected answers to `data/copilot_expected.json`, computed in code for Marcus's scope: the case ids, the totals and the rate record for each question, for the state after seeding and before any dispatch. PC-0311 is a history case still Returned to sub with three open exceptions on its latest submission, so question 6 works without a live run.

## Our IT team's choices

- **The graph stays Ed's**: a node that calls the model, LangGraph's `ToolNode` and the loop between them, a `PostgresSaver` checkpointer, the reviewer's sign-in in the graph's context and never in its config or state, at most 25 model calls a turn. With the confirmation gone, a turn never pauses; the turn's states lose "waiting for a confirmation".
- **The tools are thin.** Each Copilot tool calls one app route and returns what it says; the scoping, the period, the exposure arithmetic, the cents-to-dollars formatting and the withholding are all in the backend. The plan puts the period resolution, exposure, filings and classification changes each in a backend module of its own.
- **`draft_notice`** saves the draft on the case as a notice, recorded as drafted by the Copilot for the reviewer, which the reviewer then edits and sends on the case page. The plan settles how the draft's wording is produced given the decided signature, `draft_notice(case_id)`, and what happens to a draft the reviewer has already edited.
- **The instructions** in `agent/copilot/instructions.md` are rewritten for PayrollCheck as goals: who it works for and what they can see, what it can and can't do, to pass periods symbolically, to cite case ids and rate records, to quote totals as the tools give them, and the not-legal-advice line. They don't script its steps.
- **What needs a reviewer**, after a dispatch, is worked out in code in place of `needs_a_handler.py`, from the cases in the reviewer's scope. The plan defines it from the statuses and flags in `CONTEXT.md`.
- **The cards** keep their kinds, with cases, subcontractors and projects in place of claims, customers and policies.
- **The tests** use a stub model that records every input it's given, so a test can show what reached the model.

## What stays the same

- The rules in `docs/SPEC.md`. Nothing reaches Accepted without a reviewer's sign-off on the case page.
- The sidebar, its cards, the conversations and their turns, one turn at a time, the sign-in passed through and never saved, and the Copilot as an AgentCore app of its own (`agent/copilot/entrypoint.py`, `runtime/copilot.py`).
- Stage 4's roles and scope; stage 5's improver. The Copilot never sees the labels.
- The API rules in `docs/TECH_STACK.md`, and `docs/CODE_STANDARDS.md`.
- Tests never call a model, AWS, Supabase Auth or the Gateway; `npm run check` never reads `.env`; the bars in `docs/PROCESS.md` and the test rule in `docs/ROADMAP.md` apply. `e2e/copilot.spec.ts` and `e2e/copilot_stand_in.ts` are rewritten here, since this stage changes the sidebar.
- Nothing in this change creates anything on AWS.

## What done looks like

- `npm run check` is green with `.env` moved out of the way. Tests cover:
  - **Layer 1, the tool tests** (pytest, no model): each of the six questions' tools, called as Marcus with the inputs the question implies, returns exactly what `data/copilot_expected.json` holds: case ids, totals and rate record
  - every period resolved from the business date and matched on `week_ending`, including a week that crosses a month; the business date changed and reset by the compliance manager and refused for a reviewer
  - exposure counting only latest submissions, never superseded exceptions, excluding dismissed ones, and outstanding only on Awaiting review and Returned to sub
  - filings computed from engagement windows, with missing and late as of the business date
  - the Copilot, signed in as Marcus, unable to report Priya's exposure: the road resurfacing isn't found, and exposure across all projects holds only his
  - withheld text: for every app tool, a flagged case's text cells withheld and its numbers, dates, ids and screening reason passed, and the stub model's recorded inputs never holding the flagged text
  - `draft_notice` saving a draft on the case, and the Copilot having no tool that signs off, sends back or overrides
  - the success-criteria table worked out in code from records and an evaluation's measures
  - the end-to-end tests drive the sidebar against the rewritten stand-in Copilot: a lookup, a draft notice that then shows on the case page, a refusal and a formatted answer, with no confirmation card anywhere
- **Layer 2, the live checks.** After one `npm run seed` and before any dispatch, with `npm run dev` running on the default model, on the direct route with memory off, signed in as Marcus Oyelaran, in one conversation, the six questions above:
  - for each, the expected tool was called, every expected case id appears in the answer, and every total appears exactly as the tool formatted it
  - for question 6, the draft is saved on PC-0311, covers all three exceptions, and is scored by stage 5's judge on its notice rubric; report the score
- **The guardrail checks**, live, in the same session:
  - an interpretation question ("Is our fringe payment legal if we pay it as cash?" or similar) gets the not-legal-advice line
  - a question about a flagged case answers without its free text, and the Copilot's recorded model inputs hold none of it
  - "sign off PC-0311" is refused, with a pointer to the case page
- Check the header's business date, Settings and the sidebar in light and dark mode through the Playwright MCP server, and report what the runs spent.
- `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/STATUS.md` describe the product as it now is.

## Not for now

- The Copilot signing off, sending back, overriding or changing settings, the configuration or rounds.
- The Copilot reading the labels or the held-out set.
- Streaming answers word by word, or stopping a turn partway.
- Sharing, renaming or deleting conversations.
- Legal interpretation.

## Planning

Follow `docs/PROCESS.md`, but write this plan to `docs/PLAN_COPILOT.md` (replacing Ed's file of that name) and tick it off there. Plan five or six phases and commit at the end of each. Start with the business date and the period resolution, then exposure, filings and classification changes in the backend with the layer 1 tool tests, then withheld text, then the Copilot's tools and instructions with the sign-off card and the old tools removed, then the success-criteria table and the sidebar, and last the live checks and guardrail checks, after reseeding once.
