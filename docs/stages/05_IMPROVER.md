# An improver that learns from our reviewers

From the compliance manager at Pinelands Builders, with our IT team.

A note on names: this brief uses the file and table names as stage 1 renamed them (UnderCover to PayrollCheck, claim to case, handler to reviewer). Where a file here doesn't exist under exactly that name, use the one stage 1, 3 or 4 left in its place. The words are those in `CONTEXT.md`.

## Where we're heading

UnderCover's improver, in `agent/improver.py` and `backend/improvement.py`, reads the agent's misses on a labeled set, proposes a new version of its configuration, waits for a person's approval, and lets code keep or roll back the change on the held-out set. We keep all of that. What changes is what it learns from and what it's judged on.

The payroll agent now has two teachers. One is the development set: the 45 seeded errors, the decoys and the hidden instructions, scored by code against the labels. The other is our reviewers. Every time one of them dismisses an exception as wrong, adds one the agent missed, or rewrites a notice before sending it, that's a correction we want the next version to learn from. Stage 4 logs all three. This stage hands them to the improver.

The measures change too. UnderCover judged accuracy against a handler's decision and graded the agent's explanation. We care whether the agent catches what's wrong, how often it flags what isn't, whether every shortfall is right to the cent, and whether its notice is one a payroll clerk can act on. The judge stays, grading the notice.

This stage ends with the number we'll be held to: a live scoring run on the whole development set against the success criteria in `docs/SPEC.md`.

## What we want

1. **The configuration.** The payroll agent's configuration is its instructions, model, reasoning effort, and the check tools' tunable parameters, such as a rounding tolerance. It is kept in versions, as Ed's is. Version 1 is the payroll agent as stage 3 left it, with the check tools' parameters at their stage-3 values. Each version records what changed, the reason, who proposed it, who approved it and when, and a dispatch and an evaluation each record the version they used. The Configuration page shows the parameters beside the instructions, model and effort, and the diff between versions covers all four.

2. **The improver reads two signals.**
   - **The development set's misses**, from the current version's latest whole-set evaluation of it: each label not caught, each false exception, each shortfall that's wrong, each screening flag missed, with the case and the label beside the agent's exception. And the notices the judge scored lowest.
   - **Our reviewers' overrides since the last round**: exceptions dismissed as false, exceptions added as misses, and edits to notices, each with the reviewer's reason and the case. The plan settles exactly where "since the last round" starts.

   From the held-out set it sees the scores only, as now.

3. **A proposal cites its cases.** Each proposal names the case ids that motivated it, from either signal, and gives its reason. The Improvement page shows the change as a diff of the instructions, with the model, reasoning effort and every changed tool parameter before and after, and lists the motivating cases with links to their pages. The change itself never names a case; the reason does.

4. **The compliance manager decides.** Only the compliance manager starts or stops a round and approves or rejects a proposal, as stage 4 set up. A rejection carries their reason back to the improver, which may propose again. A proposal outside the models allowed goes back to the improver without reaching a person, as now; the plan says whether a tool parameter has bounds that work the same way.

5. **Code keeps or rolls back each version**, by Ed's rule in `backend/verdict.py`: an approved version is evaluated on the held-out set and kept only if it meets every objective, improves at least one measure by more than its noise, and makes none worse by more than its tolerance. Otherwise it is rolled back. The measures, on the held-out set, are seeded as:

   | Measure | Objective | Noise | Tolerance |
   |---|---|---|---|
   | Catch rate | at least 0.92 | 0.05 | 0.05 |
   | False exceptions per 100 payrolls | at most 2.5 | 1.0 | 1.0 |
   | Shortfall accuracy | 1.00 | 0.00 | 0.00 |
   | Notice score | at least 0.80 | 0.10 | 0.10 |
   | Cost per case | none | 0.15 | 1.0 |
   | Seconds per case | none | 0.15 | 0.25 |

   Catch rate, shortfall accuracy and notice score are better higher; false exceptions, cost and seconds are better lower. Cost and seconds are compared as fractions of the old value, as Ed's are; the plan chooses how the four new measures are compared, and what happens to a version whose runs have no notice score (Ed rolls back a version without a grade).

6. **What each measure is.** Every measure is worked out by code from the scoring stage 3 built, with the matching rules in `CONTEXT.md` (caught, shortfall correct, false exception, screening caught):
   - **catch rate**: from labels caught
   - **false exceptions per 100 payrolls**: open exceptions matching no label, per 100 payrolls in the run
   - **shortfall accuracy**: from caught money labels whose shortfall equals the label to the cent
   - **notice score**: the judge's scores for the run's notices, averaged
   - **cost per case** and **seconds per case**: as Ed records them

   The plan writes down each formula exactly, including whether screening flags count toward the catch rate, before any code.

7. **The judge grades notices.** The judge in `backend/judge.py` is repurposed to grade each draft send-back notice in an evaluation against our rubric:
   - it covers every exception in the report
   - its amounts match the records
   - it is in plain language a payroll clerk can act on
   - it gives no legal interpretation

   It needs no reference notice. Each notice gets a score on the scale the objective uses (0 to 1), shown on the evaluation's page beside the case with what the judge found on each point. A notice the judge couldn't grade is left out of the average, as Ed's ungraded claims are; the plan chooses how a case with no exceptions, or with exceptions but no notice, counts. The judge's cost is recorded with the evaluation, apart from the agent's. Remove the explanation judge: the grade against the handler's reason, its two checks, and their columns and tests, deleted in the same commit as the code, with the notice judge's tests written in the same stage.

8. **What the improver can't change.** It has no way to change the objectives, the noise and tolerance, the spending limit, the models allowed, the development, held-out or tiny sets, the labels, or the judge and its rubric. Overrides never change the labels. Nothing it proposes takes effect until the compliance manager approves it.

9. **A spending limit of $5.00 for each round**, seeded in place of Ed's $0.50, covering the improver's own model calls, every evaluation in the round (its first ones included) and the judge. A round is roughly 400 case runs: one whole development-set evaluation and two held-out ones. Everything else about the limit works as Ed's does: an evaluation likely to cost more than what's left is refused, and one cut short by the limit shows as stopped, and its version is rolled back.

10. **The development-set scoring run.** The stage ends with one live evaluation of the whole development set on the current version, scored against the success criteria:
    1. at least 41 of the 45 seeded errors caught, the expired registration and the unregistered apprentice among them, with every caught shortfall correct to the cent
    2. all 3 hidden-instruction payrolls flagged
    3. no more than 5 false exceptions across the set
    4. the mid-project rate increase applied from the right week, and the later determination ignored (the plan says how the run shows this from the labels and the decoys)

    The Scoreboard shows the run with its cases beside their labels, misses and false exceptions easy to spot, and a line for each criterion with its figure and whether it's met.

## Our IT team's choices

- **The improver stays in `agent/improver.py`**, a LangChain `create_agent` with its four tools (`read_results`, `propose_change`, `run_evaluation`, `propose_recipe`), the recipe and its versions, `HumanInTheLoopMiddleware` on the two propose tools and its own checkpointer, as Ed built it. Its client stays `agent/improver_api.py`, so the payroll agent's client still has no way to the scores, the labels or the overrides. Its instructions are rewritten for PayrollCheck as goals: what the payroll agent works from (its instructions, the check tools and their parameters, the context layer, the case and its submissions), the two signals, and that a change never names a case. The first recipe is adapted from Ed's and may now say to weigh the overrides beside the misses.
- **`read_results`** returns the improver's view in one read from `backend/improvement.py`: the current version and its scores on both sets, the development set's misses and lowest-scored notices with their labels, the overrides since the last round, the earlier rounds, the objectives, noise, tolerance and rule, what's left of the spending limit, and the models allowed. The plan chooses how many misses and overrides it holds so the view stays a sensible size, and says so in the instructions.
- **`propose_change`** takes the new instructions, model, reasoning effort, tool parameters, reason and motivating case ids.
- **The tool parameters** are data on the version, read by the check tools through the run's version, never constants in the tools. The plan names which parameters are tunable; the rounding tolerance is one.
- **Development misses are read by the backend**, which holds the labels; nothing in the agent reads `data/evals/` or the held-out labels, and the improver gets the development labels only as the backend chooses to show them. `docs/PROCESS.md`'s rule against opening `data/evals/` still holds for the coding agent.
- **The judge** stays in its own module, `backend/judge.py`, the one place that calls it, with its address read once from the environment, as Ed's is. The plan chooses how the four points become the 0 to 1 score and checks it on a few real notices before the live runs. It still grades in parallel when an evaluation finishes, with a timeout on each call and no retries, so finishing stays fast.
- **Settings** seeds the table above and the $5.00 limit in `data/improvement.json`, recording who changed what and when, as Ed's does. The Settings page and the round's frozen settings show the new measures in place of accuracy and grade.
- **Free models:** with `MODEL_NAME` set, everything builds and the tests pass, the judge isn't called, and rounds run on the tiny set only, as Ed's free path does.
- **The baseline:** before the first round, report version 1's two held-out runs and how far apart they were on each measure, beside the noise and tolerance, so we can see whether the seeded noise is right.

## What stays the same

- The rules in `docs/SPEC.md`. The payroll agent never sees the labels, and nothing but the scoring reads the held-out set's.
- The payroll agent, its check tools and their order, screening, the dispatcher and the swarm.
- Stage 4's roles, scope, overrides, notices and outbox. Evaluations work labeled copies and are visible to every reviewer.
- One dispatch, evaluation or stretch of the improver's work at a time; a round waiting for approval survives a restart.
- The API rules in `docs/TECH_STACK.md` and `docs/CODE_STANDARDS.md`.
- Tests never call a model, the judge, Supabase Auth or AWS; `npm run check` never reads `.env`; the bars in `docs/PROCESS.md` and the test rule in `docs/ROADMAP.md` apply.
- `npm run seed` takes the configuration and recipe back to version 1 and empties the rounds.

## What done looks like

- `npm run check` is green with `.env` moved out of the way. Tests on a stub model and the judge's stand-in cover:
  - each measure worked out by hand on a small scored run: a label caught, one missed, a false exception, a wrong shortfall, a missed screening flag, and a notice the judge couldn't grade
  - a version kept and one rolled back by the rule, with false exceptions, cost and seconds treated as lower-is-better
  - the improver's view holding the development misses and the overrides since the last round, and nothing from the held-out set but its scores; an override from before the last round left out
  - a proposal with its motivating case ids shown with the diff and its tool parameters before and after; one outside the models allowed going back to the improver
  - a proposal changing nothing until the compliance manager approves it, and a reviewer refused
  - the improver having no tool or route that changes the objectives, noise, tolerance, spending limit, models allowed, sets, labels or judge
  - overrides leaving the labels unchanged
  - a tool parameter from a version reaching the check tools in a run on that version
  - a $5.00 round refused an evaluation it can't afford, and one cut short shown as stopped
  - the payroll agent's client still unable to reach the scores, the labels or the overrides
  - nothing left of the explanation judge
- The end-to-end tests approve a proposal, played out through the API, that changes a tool parameter, and see its diff and motivating cases on the Improvement page.
- After one `npm run seed`, with `npm run dev` running on the default model, checked through the Playwright MCP server, signed in as Dana Whitfield:
  - As Marcus, first dismiss one exception with a reason and edit one notice before sending it, so the round has overrides to read.
  - Run one round from the Improvement page: the first evaluations, a proposal that cites its cases, an approval, the held-out runs and the verdict. Report version 1's two held-out runs and how far apart they were on each measure, beside the noise and tolerance, and what the round spent against its $5.00.
  - Then the development-set scoring run on the current version, as in item 10. Report each success criterion with its figure, every missed label and every false exception by case, and the run's cost. If any criterion isn't met, report what fell short and stop for us to decide; don't change the agent outside a round to reach the target.
- `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md`, `docs/CODE_STANDARDS.md`, `docs/STATUS.md` and `data/README.md` describe the product as it now is.

## Not for now

- The improver changing the check tools' code, the order of the checks, or the screening model.
- The improver proposing changes to the labels, the rubric or the sets.
- Automatic rounds on a schedule.
- The Copilot starting or reporting rounds.
- Measuring the success criteria on the held-out set: they're measured on the development set, and the held-out set only keeps or rolls back versions.

## Planning

Follow `docs/PROCESS.md`, but write this plan to `docs/PLAN_IMPROVER.md` and tick it off there. Plan five or six phases and commit at the end of each. Start with the tool parameters stage 3 put in the configuration, shown and diffed on the Configuration page, then the measures and the keep-or-roll-back rule, then the judge's notice rubric, then the improver's view with the overrides and its proposals, then the Improvement and Settings pages, and last the live round and the development-set scoring run, after reseeding once.
