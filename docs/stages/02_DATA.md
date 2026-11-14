# Our payroll world, and the rules it's checked against

From the compliance manager at Pinelands Builders, with our IT team.

## Where we're heading

PayrollCheck will check our subcontractors' certified payrolls against New Jersey's prevailing-wage rules (`docs/SPEC.md`). Before anything can be checked we need two things that don't exist yet: a world of payrolls to check, with the right answers known in advance, and the reference data the checks read.

Neither can be real. We won't put real workers' wages in a demo, and we won't call invented rates NJDOL's. So everything here is synthetic, made by a generator from a fixed seed, and labelled "not real rates". Because the errors are seeded on purpose, we know exactly what a perfect review would find, and code can score the agent against it to the cent.

This stage is purely additive. It writes the generator, its output, the labels and the new context layer, and adds the compliance context server's new tools beside the old ones. The app keeps running travel cases exactly as it does after stage 1; nothing reads the new data until stage 3.

Our research on the rules is in `docs/research/nj-prevailing-wage-rules.md`. Read it, especially "Implications for PayrollCheck", before designing the data's shape.

## What we want

1. **A deterministic generator.** `data/generate.py` builds our world from a fixed seed, so the same command always writes the same files, byte for byte. Its output is committed, and stage 3's `npm run seed` only loads it. You write the generator and the error manifest; nobody on our side authors either. It runs in two passes:
   - **The clean world**, with every payroll correct.
   - **The errors**, applied from `data/error_manifest.yaml` (case → rule → worker or line → corruption), with the ground-truth labels written from the manifest and every expected shortfall computed by the same rate logic the clean world used.

2. **The clean world**, the development set:
   - **3 projects:** the Lincoln School renovation, the municipal building and the road resurfacing, in three counties, Middlesex among them. Each has an award date, a county, a public body and a contract number.
   - **8 subcontractors**, Garden State Electric among them, each with its legal name, FEIN, public works contractor registration number (synthetic, 6 digits), the projects it's on with an **engagement window** (first and last week) on each, and a payroll contact with an email on a `.example` domain.
   - **About 60 workers across 8 crafts**, each with an **established craft**. Six are apprentices, and one of those is not registered.
   - **Rate determinations**, keyed by determination, county, craft and classification, each key with dated rows of wage, fringe and total in integer cents. Each craft carries its overtime rules as data (for example over 8 hours a day, Saturday at 1.5×, Sunday and holidays at 2×, and whether the multiplier applies to fringe), its apprentice schedule and its apprentice ratio. At least some crafts pay daily overtime.
   - **The mid-project rate change** is a pre-listed increase inside the determination in force on the award date, so it applies from the date it lists. One determination published after the award date must be ignored.
   - **The contractor registry**, with one subcontractor's registration expiring partway through the project.
   - **Apprentice registrations** for the registered five.
   - **Correct weekly payrolls** over 12 weeks, about 200 in all, in our CSV template (item 5): every expected filing in every engagement window, with week 12 holding 24 payrolls. A couple of week-12 expected filings are left out on purpose, so they're missing: expected filings with no case, beside the 24.

3. **The errors.** The manifest seeds 45 errors on the development set, each a label:

   | Rule | Count |
   |---|---|
   | `rate.base_short` | 10 |
   | `rate.fringe_short` | 5 |
   | `classification.mismatch` | 5 |
   | `arithmetic.hours_total` / `arithmetic.gross` | 5 |
   | `timeliness.late` | 8 |
   | `sequence.gap` | 2 |
   | `registration.inactive` | 1 |
   | `apprentice.unregistered` | 1 |
   | `overtime.underpaid` (Saturday at straight time; over 8 hours a day while under 40 a week) | 3 |
   | `form.missing_field` / `form.unsigned` (a blank FEIN, an unsigned payroll) | 2 |
   | `classification.changed` | 2 |
   | `apprentice.ratio` | 1 |

   Plus **3 hidden instructions**, each in any text cell (not only the notes columns), labelled "expected screening flag". Plus **about 10 decoys**, payrolls that look wrong but are clean: correct daily overtime, the pre-listed rate-increase week paid correctly, a later determination that must be ignored, a classification change with a valid line note, a No Work Week filing, a corrected resubmission, a contractor-name variant, and cash in lieu of fringe (paid in `fringe_cash`). Form errors are blank-but-parseable values, never something intake would refuse.

4. **The demo anchors.** The manifest guarantees what the Copilot's six questions in `docs/SPEC.md` need: open exceptions on the Lincoln School renovation; Garden State Electric with money exceptions in the business date's month; case PC-0311, a history case still Returned to sub, with exactly three open exceptions on its latest submission, so the draft-notice question works without a live run; a Middlesex journeyman electrician row with a known effective date; at least two classification changes in the last four weeks; and missing and late filings last week. Periods are resolved from the business date, the Monday the week-12 wave arrives, and always matched on a payroll's `week_ending`: "last week" is the latest payroll week ending before the business date, which is week 12. One shared periods module, written in this stage and reused by the backend in stage 6, resolves them, so `data/copilot_expected.json` and the Copilot's tools can't disagree.

5. **The CSV template.** One flat file per payroll, one row per worker-week line, the certification repeated on every row. The columns: `contractor_name, fein, registration_no, project_id, payroll_no, week_ending, wage_payment_date, signed_by, signed_on, no_work_week, worker_id, worker_name, classification, apprentice_level, hours_mon, hours_tue, hours_wed, hours_thu, hours_fri, hours_sat, hours_sun, base_rate, fringe_rate, fringe_cash, overtime_hours, gross, deductions, net, line_notes, payroll_notes`. The generator writes exactly what stage 3's intake will read, so seeding and uploading share one format. `fringe_cash` is the hourly cash paid in lieu of fringe benefits, and the fringe check counts `fringe_rate + fringe_cash` toward the fringe requirement. A No Work Week filing is one row with the certification columns filled, the worker columns blank and `no_work_week` set to `true`; intake turns it into a submission with no lines. The plan sets out the template in `data/README.md`: each column's type and how money is written.

6. **The other sets.**
   - **The held-out set:** a second world from a second seed and manifest, about 100 payrolls, with different subcontractors and workers but the same counties, crafts and mix of errors, hidden instructions and decoys. Only the improver's keep/rollback gate will score it.
   - **The tiny set:** about 10 development payrolls, one for each check family plus one hidden instruction, for people on free models.

7. **The expected Copilot answers.** The generator writes `data/copilot_expected.json`: for each of the six questions, the case IDs, totals and rate record the answer must give, computed in code (never by hand) for Marcus Oyelaran's scope (the Lincoln School renovation and the municipal building) at the seeded business date, as the database stands after seeding and before any dispatch.

8. **The context layer.** New read-only files in `context/`, synthetic and each marked "not real rates", naming its system, owner and review date as today's files do:
   - the rate determinations
   - the contractor registry
   - apprentice registrations
   - the filing rules: due within 10 days of the wage payment date (calendar days), No Work Week filings keep the sequence, a same-week resubmission is a correction
   - a glossary of the payroll terms

   They sit beside the old files under names that don't collide, since stage 3 deletes the old ones.

9. **The compliance context server's new tools**, read-only, added to `context/server.py` beside the seven it has, each answer naming its file and source:
   - `get_wage_rate(craft, classification, county, award_date, work_date)`: takes the determination in force on the award date, and returns its latest row dated on or before the work date, with wage, fringe and total and the row it came from. It returns the craft's overtime rules and apprentice schedule too, or a companion tool does; the plan chooses.
   - `check_registration(registration_no, date)`: the registration's holder, FEIN, effective and expiry dates and status on that date.
   - `check_apprentice`, by worker ID or registration: registered or not, the sponsor and program, the current level and its percentage, and status on the date.
   - `get_filing_rules`: the filing rules.
   - A glossary lookup for the new terms.

   `get_project`, `list_subcontractors` and `get_payroll_history` are **not** context tools: projects, subcontractors and payroll history are our records, served by the app in stage 3. The context server never reads our records: its caller reads the project's award date from the project record and passes it to `get_wage_rate`.

## Our IT team's choices

- **Where things live.** The generator, the manifests (development and held-out) and the CSVs in `data/`; the labels for all three sets in `data/evals/`, under new names beside the old files; the context files in `context/`. The plan chooses the folder layout and file names. The generator writes everything stage 3's seed will need to load the world without recomputing it: the projects, subcontractors, workers, engagement windows, the case IDs (`PC-nnnn`, stable across runs, since the labels and the anchors name them), each submission's received date and reviewer, and the outcome of each history case.
- **History follows the lifecycle.** Weeks 1 to 11 will be seeded as history, with exceptions taken from the labels and confirmed by a named reviewer. Most history cases with labelled errors were Returned to sub, then received a clean corrected submission and are Accepted, their earlier exceptions superseded. A few are still Returned to sub with open exceptions on their latest submission, PC-0311 among them. Clean history cases are Accepted. The generator's outcomes must obey `CONTEXT.md`: an Accepted case has no open exception on its latest submission, and a correction is a new submission on the same case.
- **Labels.** Each label is `case_id, rule, worker_id` (null for case-level rules), `line_no`, `expected_shortfall_cents`, or "expected screening flag". Shortfalls are integer cents. A decoy has no label.
- **One rate logic.** The rate lookup, the overtime rules and the apprentice percentages are computed one way, used by the generator for clean payrolls and for expected shortfalls and by `get_wage_rate`. Stage 3's check tools will reuse it rather than write their own. Put it where both `data/generate.py` and `context/` can import it and the context check (the context layer importing with only the `context` dependency group) still passes.
- **Money** is integer cents in every file except the CSVs, which carry dollars and cents as a payroll would.
- **Overtime rules are data**, in the shape the research suggests (ordered predicates with a multiplier and what it applies to), with the 40-hour weekly floor as a fallback.
- **The generator is not the app.** It imports nothing from `backend/` or `agent/`, and the backend never runs it. `uv run data/generate.py` (or a `package.json` script the plan names) rewrites the committed files, and a check fails if they differ from what it would write.
- **`data/evals/`** may be opened for this stage, to write the labels. Once written, the held-out labels are read only by tests and, later, scoring.

## What stays the same

- Everything the app does, with the stage 1 names. Seeding, the queue and the agents still use the travel records, and the claim-era files in `data/` and `context/` stay where they are.
- The context server's existing seven tools, and each agent's own list of context tools in `agent/context_tools.py`: neither agent gets the new tools until stage 3 (the payroll agent) and stage 6 (the Copilot).
- The API rules in `docs/TECH_STACK.md` and the context layer's way of naming its files and sources (`context/files.py`).
- Tests never call a model, `npm run check` never reads `.env` and needs no network, and the code follows `docs/CODE_STANDARDS.md`.
- Everything works on Windows too.

## What done looks like

- `npm run check` is green with `.env` moved out of the way, with coverage at least 80%, and these new tests:
  - **Generator consistency:** every label matches a manifest entry and every manifest entry a label; the development set has exactly the 45 errors above by rule code, 3 screening labels and the decoys; every expected shortfall equals the shortfall the shared rate logic computes for that line; in every clean line the daily hours sum to the total and hours × rate equals gross; every decoy and every payroll not in the manifest passes every rule; the held-out and tiny sets meet their descriptions; the demo anchors hold.
  - **Determinism:** running the generator twice writes identical files, and the committed files are what it writes.
  - **The template:** every CSV has exactly the template's columns and the same certification on every row.
  - **Context server:** each new tool against the files, including a work date before and after the pre-listed increase, an award date before the later determination (which must not be returned), the registration on dates before and after it expires, the unregistered apprentice, and an unknown key answered with a clear refusal. Each answer names its file and source.
  - **Expected answers:** `data/copilot_expected.json` holds an answer for each of the six questions, inside Marcus's scope.
- The new tools answer through the running context layer with `npm run dev`, for example a `get_wage_rate` call for the Middlesex journeyman electrician returning the row the anchor names.
- `data/README.md` describes the generator, the manifest, the template, the three sets and the labels; `docs/TECH_STACK.md` and `docs/STATUS.md` describe what's new.

## Not for now

- Seeding the new world, the new schema, intake, check tools and the payroll agent (stage 3).
- Giving either agent the new context tools.
- Deleting the travel records, the old context files or the old context tools (stage 3).
- Real NJDOL rates or the real registry, and PDFs.
- Anything on AWS.

## Planning

Follow `docs/PROCESS.md`, but write this plan to `docs/PLAN_DATA.md` and tick it off there. Plan five or six phases and commit at the end of each. Start with the shared rate logic and the context files, then the clean world and the CSV template, then the error manifest and the labels with the decoys and the demo anchors, then the held-out and tiny sets and `data/copilot_expected.json`, then the context server's new tools. There are no live runs on a real model in this stage.
