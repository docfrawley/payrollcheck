# Plan: stage 5, Improver

From `docs/stages/05_IMPROVER.md`. After stage 4 our reviewers correct the payroll agent's reports by overrides, edit its notices and send them back, but the improver still learns only from the development set's misses, and a round's verdict weighs only the catch rate, cost and time. This stage turns it into the improver the business asked for:
- the **configuration** includes the check tools' tunable parameters, shown and diffed with the instructions, model and reasoning effort
- the improver reads **two signals**, the development set's misses and the reviewers' **overrides** and notice edits since the last round, and each proposal cites the cases behind it
- the verdict weighs the **four measures** the business cares about (catch rate, false exceptions, shortfall accuracy, notice score), beside cost and time
- the **judge** grades every draft notice in an evaluation against the business's rubric
- each round may spend **$5.00**
- the stage ends with the **development-set scoring run** against the success criteria in `docs/SPEC.md`

The work happens on a branch, `stage-5-improver`, cut from `main` at `f07ee89`, with a commit at the end of every phase.

## The baseline: `npm run check` before the stage

On `main` at `f07ee89`, with `.env` moved aside:
- ruff and pyright are clean, and pytest passes 1,231 at 99% coverage.
- The server, context and runtime import checks exit 0.
- Prettier, ESLint and tsc are clean, and vitest passes 208 at 98% of lines.
- Playwright passes 38.

Every phase ends with `npm run check` green and coverage of at least 80%. Tests are deleted only with the code they test, and each one's replacement is written in the same phase (the test rule in `docs/ROADMAP.md`).

## Decisions

### Taken with the user while planning

These are the points where the brief, the code and the budget didn't settle the answer.

1. **Free models: rounds run on the tiny set.** The brief says this is "as Ed's free path does", but Ed's rounds always ran on the whole sets: his free path only skipped the judge. Today (`docs/STATUS.md`, Known gaps) rounds can't run on free models at all. **Agreed:** with `MODEL_NAME` set, each of a round's three evaluations of a version, the first ones included, is on the tiny set. The first stands in for the development set (its misses are what the improver reads) and the other two for the held-out set (the rule compares them). The Improvement page and the round's evaluations say "tiny set". With the default models nothing changes.
2. **The OpenRouter key's daily limit.** Stage 3 found the key capped at $1.00 a day. This stage's live runs come to about $1.10 to $1.40 on the default model: a dispatch so Marcus has cases to override (about $0.02), the first round (about 806 case runs, about $0.85, plus the improver and the judge), and the development-set scoring run (about $0.21). A round that tries `google/gemini-3.5-flash-lite`, the dearest model allowed, could reach $2.50. **Agreed:** the user raises the key's daily limit to at least $5.00 before phase 6, and the live runs stop if it's hit, rather than being split over two days.

### Choices this plan makes, for your review

3. **The tunable parameter is the rounding tolerance alone.** `rounding_tolerance_cents` is the only number the check tools take from the version today: a line's shortfall or arithmetic difference at or under it is no finding. Every other number they use is law or the business's record (the filing rules' 10 days, the craft's overtime rules, the apprentice ratio), which the improver must not tune. Adding a new parameter would change the check tools, which the brief keeps as they are. The catalogue (`backend/parameters.py`) is data, so a later stage can add one in one place.
4. **A parameter has bounds, which work like the models allowed.** The rounding tolerance is a whole number of cents from 0 to 100 ($1.00). A proposal with a parameter outside its bounds, of an unknown name, or missing one goes back to the improver with the reason and never reaches a person, as a model outside the models allowed does now: the improver's tool answers it without pausing, and the backend refuses it with a 422 if it gets that far. The bounds are in code, not the settings, since the business sets them and the improver can't reach either.
5. **"Since the last round" runs from the start of the newest earlier round that finished to the start of this round.** A round reads the overrides and notice edits made in that window. A stopped round doesn't count as the last round, so what it never got to use is read by the next. The window ends at the round's own start, not when the improver reads it, so the view stays the same across a restart and two rounds never read the same correction twice unless one was stopped. The first round reads every override since seeding (none, after a reseed, until a reviewer makes one).
6. **The notice edits the improver reads** are the notices of queue cases whose reviewer's edit was saved in the window and differs from the agent's draft, each with the case, the draft, the edit, who edited it and when. An edit has no reason of its own (stage 4 didn't ask for one), so the improver reads the difference. A notice a reviewer wrote where the agent drafted none isn't an edit of the agent's work and isn't included.
7. **How much the improver's view holds.** At most 30 development cases with a mistake (misses, wrong shortfalls and false exceptions first, then screening mistakes, each kind by case id), the 5 lowest-scored notices, the 40 newest overrides and the 10 newest notice edits. Each list comes with its total, so the improver knows when it sees only part. The improver's instructions say so. At version 1's figures (stage 3's live dispatch got about one case in ten wrong) the whole view stays well under 30,000 tokens.
8. **The catch rate doesn't count screening flags.** The catch rate is the exception labels caught, of all exception labels. The screening runs on a model outside the versions, which nothing the improver proposes changes, so counting it would add noise to the rule without giving the improver anything to act on. The screening stays a measure of its own on the Scoreboard and in success criterion 2. A screening flag on a copy with no screening label still counts as a false exception, as it does today.
9. **The measures, exactly** (on one evaluation; a version's score on a set is the average of its round evaluations there, as today):
   - **Catch rate** = exception labels caught ÷ exception labels, where a label is caught by an open exception on its copy's latest submission with its rule code and worker, whatever its shortfall. With no exception labels, 1.
   - **False exceptions per 100 payrolls** = 100 × (open exceptions matching no label + screening flags on copies with no screening label) ÷ copies in the run. Every exception on a flagged copy is false, as today.
   - **Shortfall accuracy** = caught money labels whose exception's shortfall equals the label's to the cent ÷ caught money labels, where a money label is one with an expected shortfall. With no money label caught, none.
   - **Notice score** = the average of the judge's scores of the run's graded notices (decision 11). With none graded, none.
   - **Cost per case** = the run's model cost ÷ copies, and **seconds per case** = the copies' seconds of work ÷ copies, as Ed records them. The judge's cost isn't in either.
10. **How the rule compares them.** Catch rate, shortfall accuracy and notice score are better higher, false exceptions per 100, cost and seconds better lower. Catch rate, false exceptions, shortfall accuracy and the notice score are compared as differences, in their own units (a false exceptions noise of 1.0 is one per 100 payrolls); cost and seconds as fractions of the old value, as now. The objectives are floors for the three higher-is-better measures and a ceiling of 2.5 for false exceptions; cost and seconds have none. A measure the new version has no value for, where the current version has one, rolls it back ("it has no notice score"), as Ed rolls back a version with no grade. Where neither version has a value, as on free models where the judge isn't called, that measure is left out of the objectives and the comparison. Where only the current version has none, the objective applies and the comparison is skipped. So with a shortfall noise and tolerance of 0.00, any rise in shortfall accuracy is an improvement and any fall rolls the version back.
11. **The notice score of a case.** The judge answers four yes-or-no questions on each notice, one for each point of the rubric, each as the chance that it holds, from 0 to 1 (Jev's `noul` answer). The notice's score is the average of the four. A copy is graded when its latest submission has an open exception: the notice is the agent's draft. A copy with no open exception needs no notice and isn't graded. A copy with an open exception and no draft scores 0, and counts (the backend's guarantee makes this rare: a report with exceptions needs a notice). A notice the judge couldn't grade, on a timeout or an answer without the four points, is left out of the average and shown as "Not graded". The average rather than the lowest point, so the score moves with each point; the evaluation's page shows every point, so a notice that gives legal advice is plain to see. Phase 3 checks the four questions on real notices before any live round.
12. **What the judge reads.** The notice, and the copy's open exceptions as the records hold them: each rule's title, the worker's name and line, expected and actual, the shortfall in dollars and the citation. It reads no labels and no reference notice.
13. **The judge's cost** is recorded with each graded notice, shown on the evaluation as "Judge cost" apart from the model cost, and counted in the round's spending. The estimate that refuses a round's evaluations it can't afford stays on the model cost, since the judge costs about $0.00002 a notice.
14. **A proposal's motivating cases must come from the round's view.** Each case id a change cites must be one the improver's view holds this round: a development case with a mistake, a low-scored notice, an override or a notice edit. An id outside it is refused with a 422 that names it, which reaches the improver as a rejection. A change must cite at least one when the view holds any. The ids are the original cases' (`PC-1104`, never `PC-1104-E7`), and a held-out case can never be cited, since the view holds none.
15. **The change itself never names a case, and the backend makes sure.** A change whose instructions hold a case id (`PC-` and four digits) is refused with "The change names PC-0311. A change never names a case: give it in the reason." The reason may name any of them.
16. **Success criterion 4, from the labels and the decoys.** The generator writes each set's decoys, with their kinds, into the labels files beside the labels, and seeding loads them into a `decoys` table that only scoring reads. The criterion is met when the `rate_increase_week` and `later_determination` decoys' copies have no false exception, and every `rate.base_short` and `rate.fringe_short` label is caught with its shortfall right to the cent. A rate label's shortfall depends on which row of which determination applies, so right cents on every rate label and nothing raised on the two decoys shows the increase applied from the right week and the later determination ignored. The labels themselves don't change.
17. **The success criteria are shown on a whole development-set evaluation's page**, each with its figure and whether it's met: (1) exception labels caught of all, at least 41, every `registration.inactive` and `apprentice.unregistered` label among them, and every caught shortfall right; (2) screening flags caught of expected, all of them; (3) false exceptions, at most 5; (4) as decision 16. The thresholds are named once, in `backend/success_criteria.py`. The tiny and held-out sets' pages don't show them.
18. **The Settings page and Settings history.** The objectives, noise and tolerance become one setting per measure, with the brief's values, and the spending limit $5.00. Seeding writes them as settings row 1 from `data/improvement.json`; the history of changes works as now. The change in the settings' shape needs a reseed, as every change of the tables does.
19. **A version records its motivating cases.** `versions` gains `motivating_cases`, copied from the approved proposal, empty for version 1. The Configuration page lists them on a version's page, linked.

## Design

### The configuration

A version is its instructions, model, reasoning effort and `parameters`, as now. `backend/parameters.py` is the catalogue of tunable parameters, `PARAMETERS`: for each, its name, what it does, its unit and its bounds. Version 1's parameters are the catalogue's starting values, so `backend/first_version.py` reads them from there. `parameters.py` also refuses a set of parameters that doesn't match the catalogue (`refuse_out_of_bounds`), which proposing and making a version both use.

`backend/diffs.py`, which says what changed between two versions, gains `parameter_changes(before, after)`: each parameter whose value changed, with its value before and after. `VersionSummary` and `WaitingProposal` carry it beside the instructions' diff and the model and reasoning effort before and after, so every diff covers all four. The payroll agent reads its parameters as now: `get_version` gives them, `payroll_graphs` passes them to each case's context, and `agent/checks/findings.py`'s `Parameters.read` gives the checks theirs. Nothing in the agent changes for the parameters, but a test plays a run on a version with a tolerance and sees a finding under it go.

The round carries `parameters_allowed`, the catalogue, beside `models_allowed`, so the improver's tool can answer a proposal outside the bounds without pausing, as it does a model.

### The measures and the rule

`backend/scoring.py` keeps scoring pure and gains the notice score: `measures` takes the scored copies, each with its notice grade, and works out the four measures as decision 9 defines them. `Measures` gains `notice_score` and `notices_graded`. `backend/scoreboard.py` reads the grades with the copies, in the same fixed number of queries.

`backend/verdict.py` becomes a table of the six measures, each with where it is in the scores, whether higher is better, whether it is compared as a difference or a fraction, and its objective (a floor, a ceiling or none). `keep_or_roll_back` applies the objectives, then `compare`, with decision 10's rule for a missing value. `MeasureSettings` and `Objectives` in `backend/models.py` take the six and the four, and `data/improvement.json` seeds the brief's table and $5.00. `RULE`, the sentence the improver reads, says how each is compared.

### The judge and the notice grades

`backend/judge.py` stays the one module that calls Jev, with its address read once from `JUDGE_URL`, a 10-second timeout and no retries. Its `QUESTIONS` become the four points of the rubric, as `noul` questions on `notice` and `exceptions` in the state, and `grade(notice)` gives a `NoticeGrade` (the four chances, their average and the cost) or none. Everything of the explanation judge goes: `Explanation`, `RUBRIC`, the `grade` score question, `same_grounds` and `same_section`, `Letter` and `CaseGrade`, and their tests.

A new module, `backend/grading.py`, grades an evaluation's notices and reads the grades: `grade_notices(db, run)` picks the copies decision 11 grades, asks the judge about each on a thread of its own (as Ed's `grade_copies` did), and records each in `notice_grades`, graded or not, with its cost. With `MODEL_NAME` set, it grades nothing. `finish_run` calls it for an evaluation that isn't cut short, before marking it finished. `grades_of(db, case_ids)` reads them for scoring, and `judge_costs(db, run_ids)` and the round's spending read their cost.

### The improver's view

The view moves out of `backend/improvement.py`, which keeps the round's operations, into a module of its own, `backend/improver_view.py`, since it now draws on four sources:
- **the scores**, as now, from `scoreboard.py`
- **the development set's mistakes** from the current version's latest whole development-set round evaluation: each case with a missed label, a wrong shortfall, a false exception or a wrong screening, with each label beside the agent's exception that caught it, and the false exceptions with their expected, actual and shortfall
- **the lowest-scored notices** from the same evaluation, with the notice, the open exceptions and the judge's four points
- **the reviewers' corrections** in the window of decision 5: `overrides.py`'s `overrides_between`, which now gives each override with its exception (rule, worker, line, expected, actual, shortfall and what raised it), and `notices.py`'s new `edited_between`

It caps each list as decision 7 sets, and gives the totals. `cited_cases(view)` gives every case id the view holds, which `record_change_proposal` checks a proposal's cases against. Nothing from the held-out set but its scores goes in, as now.

### The proposal, the version and the improver

`ChangeProposalRequest` gains `parameters` and `case_ids`. `record_change_proposal` refuses, each with a 422 that the improver reads as a rejection: a model outside the models allowed (as now), parameters outside the catalogue (decision 4), a case id outside the view or none when the view has some (decision 14), and instructions that name a case (decision 15). `create_version` makes the version with the proposal's parameters and motivating cases, and checks the models and the bounds again.

`agent/improver.py` keeps Ed's shape: `create_agent` with its four tools, `HumanInTheLoopMiddleware` on the two propose tools, the checkpointer and the model call limit. `propose_change` takes the new instructions, model, reasoning effort, parameters, reason and motivating case ids; `needs_a_reviewer` pauses only for a model allowed and parameters inside their bounds. `read_results` gives the new view. `agent/improver_api.py`'s `record_change_proposal` sends the two new fields. `backend/instructions/improver.md` is rewritten as goals: what the payroll agent works from (its instructions, the check tools and their parameters, the context layer, the case and its submissions), the two signals and how much of each it sees, the four measures and the rule, that a change never names a case while its reason cites the cases behind it, and that nothing takes effect until the compliance manager approves it. `recipe.md`, the first recipe, is adapted from Ed's: try the models and reasoning efforts not yet tried, and otherwise weigh the reviewers' corrections beside the misses for a general change to the instructions or a parameter.

What the improver can't change stays out of its reach by construction: it has four tools, and `improver_api.py` has no function for the settings, the models allowed, the sets, the labels or the judge. A test reads both lists, and the backend's gate on `change_settings` already refuses the agent's key.

### The pages

- **Configuration:** the current version's parameters beside its model and reasoning effort, each version's parameter changes beside its line counts, and a version's page with its parameters, its changes before and after, and its motivating cases linked.
- **Improvement:** a change waiting shows its reason, the model and reasoning effort before and after, each changed parameter before and after, the instructions' diff, and its motivating cases, each linking to its case page. The rounds show the held-out measures before and after.
- **Scoreboard:** the measures with the notice score; an evaluation shows its judge cost apart from its model cost.
- **An evaluation:** each copy with its notice's score and the judge's four points, or "Not graded" or "No notice needed"; and on a whole development-set evaluation, the success criteria, each with its figure and whether it's met.
- **Settings:** the objective, noise and tolerance for each measure, with their units, and the spending limit; a round's frozen settings show the same.

### The modules, and how they depend

New: `backend/parameters.py` (the catalogue, used by `first_version.py`, `improvement.py`, `configuration.py` and the round), `backend/grading.py` (used by `runs.py`, `scoreboard.py` and `spending.py`; uses `judge.py`), `backend/improver_view.py` (used by `improvement.py`; uses `scoreboard.py`, `overrides.py`, `notices.py`, `round_state.py` and `grading.py` through `scoreboard.py`) and `backend/success_criteria.py` (pure, used by `scoreboard.py` for an evaluation's page). None of them imports a router. `judge.py` is still imported only by `grading.py`. Checked against `docs/CODE_STANDARDS.md`: each new module has one job; the judge is reached one way; no router borrows another's helpers, which is why the view leaves `improvement.py` rather than `improvement.py` reaching into `overrides.py` and `notices.py` itself; the improver stays on `improver_api.py` and the payroll agent's client gains nothing; and the improver's instructions are goals.

### The schema

- `settings`: the same columns, with `objectives`, `noise` and `tolerance` in their new shape.
- `versions`: `motivating_cases`, JSON, not null.
- `proposals.proposal`: a change's JSON gains `parameters` and `case_ids`.
- `notice_grades`, new: `case_id` (the copy, primary key), `run_id`, `score`, `covers_every_exception`, `amounts_match`, `plain_language`, `no_legal_interpretation` (each null when ungraded), `cost` and `graded_at`.
- `decoys`, new: `labelled_set`, `case_id` and `kind`, loaded from the labels files.

After pulling this stage, reseed with `npm run seed`.

## Phases

### Phase 1: the tool parameters in the configuration

`backend/parameters.py`, version 1's parameters from it, `parameter_changes` in `backend/diffs.py`, `VersionSummary`'s parameter changes, `versions.motivating_cases`, and the Configuration and version pages.

- [ ] `uv run pytest backend/tests/test_configuration.py backend/tests/test_diffs.py --no-cov` passes, with tests that `get_configuration` and `get_version_details` give each version's parameters and its changes before and after, version 1 changing none.
- [ ] A test plays a run on a version with `rounding_tolerance_cents` of 50, with a line 40 cents short of the base rate: the rates check's finding is gone on that version and present on version 1 (`agent/tests/test_check_node.py`).
- [ ] A test of `refuse_out_of_bounds` refuses -1, 101, 2.5, an unknown name and a missing one, each with its reason, and takes 0 and 100.
- [ ] `get_version`, which the payroll agent reads, still holds no scores and no motivating cases (`backend/tests/test_agent_routes.py`).
- [ ] vitest: the Configuration page shows the current version's rounding tolerance beside its model and effort, and a version's page its changed parameter before and after and its motivating cases as links (`Configuration.test.tsx`).
- [ ] `e2e/configuration.spec.ts` sees version 1's rounding tolerance, $0.00, on the page.
- [ ] `npm run check` green.

### Phase 2: the measures and the keep-or-roll-back rule

The six measures in `MeasureSettings`, the four objectives, `data/improvement.json` with the brief's table and $5.00, `Measures.notice_score` (none until phase 3), the rule in `backend/verdict.py`, and the Settings page's fields for them.

- [ ] `backend/tests/test_scoring.py` works out each measure by hand on a small scored run: a label caught, one missed, a false exception, a wrong shortfall, a missed screening flag and a flag on a decoy, with the catch rate, false exceptions per 100 and shortfall accuracy as decision 9 defines them.
- [ ] `backend/tests/test_verdict.py`: a version kept when false exceptions per 100 fall by more than 1.0 with nothing worse; one rolled back when they rise by more than 1.0, when cost doubles and a bit more, when seconds rise by more than a quarter, when shortfall accuracy falls from 1.00 to 0.98, when it misses any objective, and when it has no notice score where the current version has one; and the notice score left out when neither has one. Each reason names the measures.
- [ ] Seeding makes settings row 1 with the brief's table and $5.00 (`backend/tests/test_seeding.py`), and `change_settings` takes and records the new shape (`backend/tests/test_settings.py`).
- [ ] The round's spending tests use the $5.00 limit: an evaluation it can't afford refused, and one cut short by the limit stopped with its version rolled back (`backend/tests/test_spending.py`, `backend/tests/test_rounds.py`).
- [ ] vitest and `e2e/settings.spec.ts`: the Settings page shows an objective, noise and tolerance for each measure, false exceptions as "at most" and per 100 payrolls, and saves a change.
- [ ] `npm run check` green.

### Phase 3: the judge's notice rubric

`backend/judge.py`'s four questions, `backend/grading.py`, `notice_grades`, grading at `finish_run`, the notice score and judge cost on the Scoreboard and an evaluation's page, and the round's spending counting the judge. The explanation judge goes in the same commit, with its tests.

- [ ] `backend/tests/test_judge.py` (rewritten): the request carries the notice and the exceptions and the four questions; the four chances and their average come back with the cost; a timeout, an error and an answer missing a point each give none, logged.
- [ ] `backend/tests/test_grading.py`: finishing an evaluation grades each copy with an open exception, in parallel, and records it; a copy with no exception isn't graded; one with an exception and no draft scores 0; one the judge can't grade is recorded ungraded and left out of the average; with `MODEL_NAME` set the judge isn't called; a dispatch and an evaluation cut short grade nothing.
- [ ] `backend/tests/test_scoring.py` gains the notice score worked out by hand, the ungraded notice left out.
- [ ] A round's spending counts its judge cost (`backend/tests/test_spending.py`), and an evaluation's judge cost is apart from its model cost (`backend/tests/test_scoreboard.py`).
- [ ] `grep -rnE "same_grounds|same_section|CaseGrade|Letter|Explanation" backend agent dashboard/src e2e` finds nothing, and nor does a search for the explanation judge's rubric.
- [ ] `e2e/judge_stand_in.ts` answers the four points; `e2e/scoreboard.spec.ts` sees the notice score on an evaluation played out through the API, and a copy's four points on its page.
- [ ] Live, outside `npm run check`: a script in the scratchpad grades three notices from stage 4's live dispatch on Supabase, among them PC-1210's, with the real judge, and the report gives each one's four points and score beside my own reading of the notice. If the questions don't tell a good notice from a weak one, I rewrite them and grade again before going on. Its cost, about $0.0001, is reported.
- [ ] `npm run check` green.

### Phase 4: the improver's view, the overrides and its proposals

`backend/improver_view.py`, `overrides_between` with each exception, `notices.edited_between`, the proposal's parameters and motivating cases with the backend's refusals, `create_version` with both, the improver's tool and client, its instructions and first recipe rewritten, and the free models' rounds on the tiny set (if you agree to decision 1).

- [ ] `backend/tests/test_improvement.py`: the view holds the development misses, wrong shortfalls and false exceptions with labels beside exceptions, the lowest-scored notices with their four points, and the overrides and notice edits in the window; an override from before the last finished round left out, one from during a stopped round kept; each list capped with its total; and nothing from the held-out set but its scores (no held-out case id anywhere in the response).
- [ ] A proposal with a case id outside the view, with none when the view has some, with a case id in its instructions, or with parameters out of bounds is refused with a 422 naming why; a proposal with a model outside the models allowed is refused as now. A proposal changes nothing until the compliance manager approves it, and a reviewer is refused approving it with a 403 (`backend/tests/test_rounds.py`).
- [ ] An approved change becomes a version with its parameters and motivating cases (`create_version`), and a test that overrides, dismissed, added and restored, leave every label as seeding loaded it.
- [ ] `agent/tests/test_improver.py`: `propose_change` takes parameters and case ids; out of bounds, or a model not allowed, goes back to the improver without pausing; a rejection's reason reaches it; the improver has exactly the four tools, and `improver_api.py` no function that changes the settings, the models allowed, the sets, the labels or the judge.
- [ ] `agent/tests/test_boundaries.py`: `agent/api.py`, the payroll agent's client, reaches no path under `/rounds`, `/improvement`, `/settings` or `/evaluations` and nothing that gives scores, labels or overrides.
- [ ] A fresh reviewer reads `improver.md` and `recipe.md` against rule 14 of `docs/CODE_STANDARDS.md` and finds goals, not steps (the recipe is the improver's own steps, which Ed's design has it rewrite each round, so it keeps its numbered form).
- [ ] With `MODEL_NAME` set, a round's evaluations are on the tiny set and the verdict compares them, and the judge isn't called (if decision 1 stands).
- [ ] `npm run check` green.

### Phase 5: the Improvement, Scoreboard and Settings pages

The proposal waiting with its parameters before and after and its motivating cases; the rounds' new measures; the success criteria on a whole development-set evaluation's page, from the `decoys` table, with the generator writing the decoys into the labels files.

- [ ] `npm run generate` writes each set's decoys into its labels file, and the test that compares the generator's output with the committed files passes; the labels themselves are unchanged (`git diff` shows only the added `decoys`). Seeding loads them into `decoys`, and nothing but scoring reads it.
- [ ] `backend/tests/test_success_criteria.py`: each criterion met and not met, by its figure: 41 caught met and 40 not; a caught `registration.inactive` or `apprentice.unregistered` missing; a wrong shortfall; a screening flag missed; 5 false exceptions met and 6 not; a false exception on the `rate_increase_week` decoy, or a wrong rate shortfall, failing criterion 4.
- [ ] vitest: the proposal panel shows the rounding tolerance before and after and each motivating case linking to its page; an evaluation's page shows the four criteria with their figures, and none on a tiny or held-out evaluation.
- [ ] `e2e/improvement.spec.ts`: a proposal that changes the rounding tolerance, played out through the API, shows its diff, its parameter before and after and its motivating cases on the Improvement page; approving it reaches the agent's stand-in as `carry_round_on`.
- [ ] Browser check with the Playwright scripts (see "How the browser checks run" below), as Dana Whitfield, on `npm run dev` with the database the end-to-end tests leave, or a seeded SQLite one: the Improvement, Configuration, Scoreboard, an evaluation's and Settings pages in light and dark mode, with no console errors.
- [ ] `npm run check` green.

### Phase 6: the documents, the live round and the development-set scoring run

`docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md`, `docs/CODE_STANDARDS.md`, `docs/STATUS.md` and `data/README.md` describe the product as it now is. Then, after one `npm run seed`, with `npm run dev` on the default model:

- [ ] The documents say what this stage built: the parameters, the measures and the rule, the judge's rubric, the improver's two signals and the window, the decoys in the labels files, and the success criteria.
- [ ] As Marcus Oyelaran: a dispatch of the week-12 wave, then one exception dismissed with a reason and one notice edited and sent back, so the round has corrections to read.
- [ ] As Dana Whitfield, one round from the Improvement page: the first evaluations, a proposal that cites its cases, the approval, the held-out runs and the verdict. Reported: version 1's two held-out runs on each measure, how far apart they were, beside the noise and tolerance; the proposal, its cases and whether Marcus's corrections were among them; the verdict and why; and what the round spent against its $5.00.
- [ ] The development-set scoring run on the current version, from the Scoreboard. Reported: each success criterion with its figure and whether it's met, every missed label and every false exception by case, and the run's model and judge cost.
- [ ] If any criterion isn't met, I report what fell short and stop for you to decide. I don't change the agent outside a round to reach the target.
- [ ] What the live runs spent, from the backend's records and the OpenRouter key's usage, matches.
- [ ] `npm run check` green, then the review of the whole branch against `main`.

## How the browser checks run

As in the earlier stages: the Claude in Chrome extension can't reach `localhost`, so I write Playwright scripts. You sign Dana Whitfield, and for phase 6 Marcus Oyelaran, into a visible Playwright window, the scripts use the saved sessions headless, and the sessions are deleted afterwards. I'll ask before opening the window.

## Not in this stage

What the brief's "Not for now" lists: the improver changing the check tools' code, their order or the screening model; proposals to the labels, the rubric or the sets; rounds on a schedule; the Copilot starting or reporting rounds; and the success criteria measured on the held-out set.
