# Plan: stage 2, Data & context

From `docs/stages/02_DATA.md`. This stage writes the generator that builds PayrollCheck's synthetic world, its output, the ground-truth labels and the new context layer, and adds the compliance context server's new tools beside the seven it has. It is purely additive: the app goes on working travel cases exactly as stage 1 left it, and nothing in `backend/` or `agent/` reads the new data until stage 3.

The work happens on a branch, `stage-2-data`, cut from `stage-1-rebrand`, with a commit at the end of every phase.

## The baseline: `npm run check` before the stage

On `stage-1-rebrand` at `c7b8359`, with no `.env`: ruff and pyright clean; pytest 834 passed at 99% coverage; the server, context and runtime import checks exit 0; Prettier, ESLint and tsc clean; vitest 178 passed (97.4% statements); Playwright 30 passed. Every phase ends with these tests still passing, the new ones added, and coverage of at least 80%.

## Decisions taken with the user while planning

The brief disagrees with itself in three places, and the user chose the first three below. The last two were settled while building phase 2:

1. **Week 12 has 24 expected filings: 22 filed and 2 missing.** Eight subcontractors on three projects make at most 24 (subcontractor, project) pairs, so the brief's "24 payrolls plus a couple missing" can't both hold. Every subcontractor is on every project in week 12, and seeding (stage 3) will load 22 Received cases, not 24.
2. **Week 12's late filings are late by the wage payment date the subcontractor entered.** At the business date, the Monday after week 12 ends, no week-12 payroll can honestly be late, since wages for the week can't be paid before it ends. So one or two of the eight `timeliness.late` errors sit in week 12, and their corruption is a `wage_payment_date` more than 10 days before the day the payroll was received. The rule stays the literal one: received more than 10 days after the wage payment date.
3. **The CSV template gets a `total_hours` column**, after `hours_sun`, as the MW-562 has it, so `arithmetic.hours_total` is the plain rule: the daily hours sum to `total_hours`.
4. **Wages are paid on the Monday after the week ends.** The plan first put each subcontractor's payday on the Thursday or Friday of the payroll week, which pays wages before the week's last days of work, while week 12's wave must arrive on the business date. So every subcontractor pays on the Monday after the week ends: history payrolls are received 1 to 4 days later, and week 12's on payday, the business date.
5. **Lateness can't be corrected.** The timeliness rule applies to each submission, as decision 2 says. A late history case stays Returned to sub with its exception open, as does the week of work while unregistered. Every other history correction arrives within the 10 days, so it is on time.

## Design

### The modules

| Module | Its one job |
|---|---|
| `context/wage_rules.py` | The one rate logic: which determination and row apply, the overtime split of a week's hours, the apprentice rate, and what a line is owed and short. Pure functions on plain data, standard library only, money in integer cents. |
| `context/sources.py` | What every context file's answer names: the file with its system, owner and review date, reading a YAML file with its source, and `Refused`. Moved out of `files.py`, which both the old and the new lookups now use. |
| `context/files.py` | The seven travel-era lookups, unchanged apart from importing from `sources.py`. Stage 3 deletes it. |
| `context/payroll_files.py` | The five new files, read once at start, and their lookups: `get_wage_rate`, `check_registration`, `check_apprentice`, `get_filing_rules` and `lookup_payroll_term`, the rate one through `wage_rules`. |
| `context/server.py` | Serves the seven old tools and the five new ones. |
| `data/generate.py` | The entry point: `npm run generate` (`uv run -m data.generate`) builds the three sets and writes every file. |
| `data/payroll_world/determinations.py` | The synthetic rate determinations: counties, crafts, classifications, dated rows, overtime rules, apprentice schedules and ratios. |
| `data/payroll_world/world.py` | A world drawn from a seed: projects, subcontractors with engagement windows, workers with their established crafts, the contractor registry and the apprentice registrations. |
| `data/payroll_world/clean.py` | Pass one: every expected filing as a correct payroll, paid by `wage_rules`. |
| `data/payroll_world/template.py` | The CSV template: its columns, how each value is written and read. Stage 3's intake reads with it. |
| `data/payroll_world/manifest.py` | Reads and validates a manifest: errors, decoys and hidden instructions. |
| `data/payroll_world/corruptions.py` | Pass two: applies each manifest entry to the clean payrolls and writes its label, with each shortfall from `wage_rules`. |
| `data/payroll_world/lifecycle.py` | The cases: ids, submissions, received dates, the reviewer and the outcome of each history case. |
| `data/payroll_world/periods.py` | The one periods module: last week, this month and the last N weeks from a business date, matched on `week_ending`. The backend reuses it in stage 6. |
| `data/payroll_world/expected_answers.py` | `data/copilot_expected.json`, computed from the world as seeding will leave it. |
| `data/payroll_world/writing.py` | Writes JSON, YAML and CSV byte for byte the same on every run and on Windows: sorted where order isn't meaningful, `\n` line endings, UTF-8. |

The dependencies run one way. `data/payroll_world/` imports `context.wage_rules` and `context.payroll_files` (for the filing rules' 10 days), and nothing from `backend/` or `agent/`. `context/` imports nothing from `data/`. The generator writes the three generated context files from `determinations.py` and `world.py`, and `payroll_files.py` reads them back, so the generator and the server compute rates from the same data with the same code.

The rate logic lives in `context/` because the context layer's Lambda package holds only `context/`, and `npm run check:context` must still pass. The generator can import from `context/`. This is a consequence for stage 3: its check tools, in the backend, will import `context.wage_rules`, so the backend's package will need that one file. Stage 3's plan settles how.

### The world's shape

- **Dates.** Weeks run Monday to Sunday, with `week_ending` on the Sunday. Week 1 ends Sunday 2026-09-06 and week 12 ends Sunday 2026-11-22. The business date is Monday 2026-11-23, so "last week" is week 12, and the business date's month, November, holds weeks 9 to 12. No one works on a Sunday or a holiday in either world. So every premium hour is at 1.5×, and the template's one `overtime_hours` column says it all; the crafts' rules still carry Sunday and holiday multipliers as data.
- **Projects** (development): the Lincoln School renovation (Middlesex), the municipal building (Monmouth) and the road resurfacing (Ocean), each with an award date between April and June 2026, a public body and a contract number.
- **Determinations.** One per county for the building trades, plus a statewide heavy-and-highway one for laborers and operating engineers, each with an issued date. Middlesex's determination in force at the Lincoln award lists a pre-set increase on 2026-10-01, in week 5. A second Middlesex determination issued in July 2026, after the award, must be ignored. A key is (determination, county or `STATEWIDE`, craft, classification), with dated rows of wage, fringe and total in cents. Each craft carries `overtime_rules`: an ordered list such as `daily_over: 8`, `day_of_week: SAT → 1.5`, `SUN → 2.0` and `holiday → 2.0`, each with `applies_to: wage` or `wage_and_fringe`, with the 40-hour weekly floor as a fallback, and the highest multiplier winning for each hour. It also carries an apprentice schedule (wage and fringe percentage by level) and a ratio of apprentices to journeymen. At least the electricians and carpenters pay daily overtime.
- **Eight crafts:** electrician, carpenter, plumber, ironworker, painter, bricklayer, laborer and operating engineer.
- **Eight subcontractors**, Garden State Electric among them, each with a legal name, a FEIN, a 6-digit registration number and a payroll contact at a `.example` domain. Each pair of a subcontractor and a project gets a fixed number from 01 to 24. Every pair is engaged in week 12, and the engagement windows start between weeks 1 and 9, so there are about 200 expected filings.
- **About 60 workers**, each with an established craft. Six are apprentices; one of them isn't registered and works one week only, so the brief's single `apprentice.unregistered` label is the only one.
- **The registry.** One subcontractor's registration expires partway through and is renewed a week later, so exactly one of its payrolls has a work date with no active registration.
- **Case ids** are `PC-WWPP`: the week and the pair's number. So PC-0311 is week 3, pair 11, and every id is stable across runs. The held-out world uses weeks 51 to 58 for its own ids, `PC-51PP` onwards, so the two sets never share an id.
- **Wage payment dates.** Wages are paid on the Monday after the week ends (decision 4). History payrolls are received 1 to 4 days after it, and late ones 11 to 20 days after. Week 12's are received on the business date.
- **Payroll numbers** run from 1 in the first week of the engagement window, one more each week, so a number is judged by its week, not by the week before.
- **History** (weeks 1 to 11). Most cases with labelled errors were Returned to sub, then got a clean corrected submission and are Accepted. A few are still Returned to sub with their exceptions open: those the manifest names, PC-0311 among them with exactly three, and every late filing and the week of work while unregistered, which a correction can't undo (decision 5). Clean cases are Accepted. Each history case names the reviewer who decided it: Marcus Oyelaran on his two projects, Priya Raman on the road resurfacing, and Dana Whitfield on a few. A label always belongs to the case's first submission, the one the manifest corrupted; corrections are clean.

### The CSV template

One file per submission, `PC-WWPP-N.csv`, where N is the submission's number. One row per worker-week line, the certification repeated on every row. The columns are the brief's, with `total_hours` added after `hours_sun`:

`contractor_name, fein, registration_no, project_id, payroll_no, week_ending, wage_payment_date, signed_by, signed_on, no_work_week, worker_id, worker_name, classification, apprentice_level, hours_mon, hours_tue, hours_wed, hours_thu, hours_fri, hours_sat, hours_sun, total_hours, base_rate, fringe_rate, fringe_cash, overtime_hours, gross, deductions, net, line_notes, payroll_notes`

- Dates are ISO (`2026-11-22`), hours are decimals to the quarter hour, and money is dollars and cents with two decimals and no symbol (`62.50`).
- `no_work_week` is `true` or `false`, and `apprentice_level` is blank for anyone who isn't an apprentice.
- `overtime_hours` is the hours paid at a premium. `gross` is the week's wages, including the overtime premium, with fringe cash not included. `fringe_cash` is the hourly cash paid in lieu of fringe. A line is owed, in fringe, the required fringe for every hour, multiplied for its premium hours when the craft's overtime applies to fringe, and `fringe_rate + fringe_cash` counts toward it.
- `net = gross − deductions` on every line.
- A No Work Week filing is one row with the certification filled, the worker columns blank and `no_work_week` set to `true`.
- `data/README.md` sets this out column by column.

### The manifest and the labels

`data/error_manifest.yaml` (development) and `data/held_out_manifest.yaml` each have three lists, written by hand once the clean world exists:
- `errors`: case → rule → worker (or none for a case-level rule) → corruption.
- `decoys`: case → the kind of decoy.
- `hidden_instructions`: case → the cell → the text.

Each rule code has one corruption, applied by `corruptions.py`:

| Rule | Corruption | Shortfall |
|---|---|---|
| `rate.base_short` | the line's base rate lowered, gross kept consistent | from `wage_rules` |
| `rate.fringe_short` | the fringe rate lowered | from `wage_rules` |
| `classification.mismatch` | paid as a lower-paid classification than the established craft | the difference to the established craft's rates |
| `classification.changed` | another classification of the same craft than last week, paid correctly, with no note | none |
| `arithmetic.hours_total` | `total_hours` disagrees with the daily hours | none |
| `arithmetic.gross` | `gross` understated against the line's own hours and rates | the difference |
| `overtime.underpaid` | Saturday hours, or hours over 8 a day in a week under 40, paid at straight time | the premium owed |
| `timeliness.late` | received 11 to 20 days after the wage payment date; in week 12, a wage payment date more than 10 days before receipt | none |
| `sequence.gap` | `payroll_no` skips one | none |
| `registration.inactive` | the week with no active registration | none |
| `apprentice.unregistered` | the unregistered apprentice, paid an apprentice rate | journeyman wage and fringe less what was paid |
| `apprentice.ratio` | more apprentices of a craft on a payroll than the craft's ratio allows | none |
| `form.missing_field` / `form.unsigned` | a blank FEIN; a blank `signed_by` and `signed_on` | none |

The labels go in `data/evals/development_labels.json`, `data/evals/held_out_labels.json` and `data/evals/tiny_labels.json`, beside the old files, whose names they don't share. Each file has `exceptions`, a list of `{case_id, rule, worker_id, line_no, expected_shortfall_cents}`, with `worker_id` and `line_no` null for case-level rules and the shortfall null where no money is owed. Each also has `screening_flags`, the case ids expected to be flagged for a hidden instruction. A decoy has no label. `line_no` counts a submission's worker lines from 1.

The development set has the brief's 45 errors by rule code, the 3 hidden instructions in text cells of any column, and 10 decoys:
- correct daily overtime
- correct Saturday overtime
- the pre-listed increase week paid correctly
- paid at the award-date rate below the later determination
- a classification change with a valid line note
- a No Work Week filing
- a corrected resubmission in week 12
- "Garden St. Electric" for Garden State Electric
- cash in lieu of fringe
- an apprentice paid correctly at their level

### The demo anchors

The manifest places errors so that, after seeding and before any dispatch, these hold:
- the Lincoln School renovation has subcontractors with open exceptions, on cases still Returned to sub
- Garden State Electric has a case still Returned to sub with money exceptions, with a week ending in November, on one of Marcus Oyelaran's projects
- PC-0311 is still Returned to sub with exactly three open exceptions
- the Middlesex journeyman electrician's row in force on the business date is the pre-listed increase of 2026-10-01
- at least two classification changes fall in weeks 9 to 12: the two `classification.changed` errors, and the decoy with its note
- week 12 has its 2 missing filings and 1 or 2 late ones, at least one of each on Marcus's projects

### The other sets

- **Held-out**, from its own seed and manifest: three new projects in the same three counties, five new subcontractors with their own workers and apprentices, and eight weeks, about 100 payrolls, with no history: each case has one submission. Its manifest has the same mix at about half the size: 23 errors with every rule code at least once, 2 hidden instructions and 5 decoys. Its subcontractors and apprentices are in the same registry and apprentice files.
- **Tiny:** 10 development cases, one for each of the eight check families, one hidden instruction and one decoy, listed in `tiny_labels.json` with their labels.

### The expected Copilot answers

`data/copilot_expected.json` holds, for each of the six questions in `docs/SPEC.md`, the case ids, totals in cents and rate record the answer must give. Each is for Marcus Oyelaran's scope (the Lincoln School renovation and the municipal building), at the business date, with the world as seeding will leave it:
- history exceptions open on cases Returned to sub
- superseded on corrected cases
- none yet on week 12's Received cases

`expected_answers.py` computes them with `periods.py`; nothing is typed in by hand.

### The context files

| File | Written by | Holds |
|---|---|---|
| `context/rate_determinations.yaml` | the generator | the determinations, their rows, overtime rules, apprentice schedules and ratios |
| `context/contractor_registry.yaml` | the generator | every subcontractor of both worlds: holder, FEIN, registration number, and the periods it was active, from which `check_registration` works out the status on a date |
| `context/apprentice_registrations.yaml` | the generator | the registered apprentices of both worlds, by worker id: sponsor, program, registration date and level by date |
| `context/filing_rules.yaml` | by hand | due within 10 calendar days of the wage payment date; No Work Week filings keep the sequence; a same-week resubmission is a correction |
| `context/payroll_glossary.yaml` | by hand | the payroll terms: MW-562, determination, award date, fringe, cash in lieu, No Work Week, journeyman, apprentice, registration and the others |

Each names its system, owner and review date as today's files do, and carries `notice: Synthetic data — not real rates`. None collides with an old file's name.

### The new tools

Each is read-only, follows the API rules (an operation id, a one-line description and no optional inputs), and names its file and source in every answer.

- `get_wage_rate(craft, classification, county, award_date, work_date)` returns everything in one answer:
  - the determination in force on the award date (the county's, or the statewide one for a statewide craft), with its id and issued date
  - its latest row dated on or before the work date: effective date, wage, fringe and total
  - the craft's overtime rules, apprentice schedule and ratio

  An unknown craft, classification or county, or an award date before any determination, is refused with the reason.
- `check_registration(registration_no, date)` returns the holder, the FEIN, the effective and expiry dates, and the status on the date. An unknown number is refused.
- `check_apprentice(worker_id, date)` returns whether the worker is a registered apprentice. If so, it adds the sponsor, the program, the registration date, and the level and its percentages on the date. A worker with no registration gets `registered: false`, not a refusal, since that is the answer. The brief allows "by worker ID or registration", but the API rules allow no optional inputs, so it takes the worker id alone.
- `get_filing_rules()` returns the filing rules.
- `lookup_payroll_term(term)` returns the term's definition, or, for a term it doesn't know, the terms it does. It is named apart from the old `lookup_term`, which stage 3 removes.

### What doesn't change

- No agent gets the new tools: `agent/context_tools.py` keeps its seven, and nothing in `backend/` or `agent/` changes.
- The travel records in `data/` and the old context files stay where they are, and `npm run seed` is untouched.
- `data/evals/`'s old files are left alone; this stage only adds the three label files.

### Where the checks change

- `pyproject.toml` adds `data` to pytest's `testpaths`, coverage's `source`, ruff's `include` and pyright's `include`, so the generator is held to the same bars as the rest of the code.
- `package.json` adds `"generate": "uv run -m data.generate"`.
- The determinism test is part of `npm run check`: it runs the generator into a temporary folder and compares every file with what's committed, so a change to the generator without its output fails the checks.

## Phase 1: The rate logic and the reference files

Move `file_source`, `read_yaml`, `Refused` and the folder into `context/sources.py`, with `files.py`, the server and their tests importing from there. Write `context/wage_rules.py`, then `data/payroll_world/determinations.py`, `writing.py` and a first `data/generate.py` that writes `context/rate_determinations.yaml`. Write `context/filing_rules.yaml` and `context/payroll_glossary.yaml` by hand. Write `context/payroll_files.py`, which reads the three files once at start.

- [x] `uv run pytest context --no-cov` passes, with `context/tests/test_wage_rules.py` covering:
  - the determination in force on an award date, and a later determination never chosen
  - the row before and after the pre-listed increase
  - daily overtime over 8 hours, Saturday at 1.5×, the 40-hour floor when the craft's rules don't apply
  - fringe multiplied only where the craft says so
  - the apprentice wage and fringe by level
  - base, fringe, overtime and unregistered-apprentice shortfalls to the cent, with the rounding rule (half up, to the cent) written once
- [x] `npm run generate` writes `context/rate_determinations.yaml`, and a second run changes nothing (`git status` clean)
- [x] Each new context file names its system, owner and review date and carries "Synthetic data — not real rates"
- [x] `npm run check:context` exits 0: `wage_rules.py` and `payroll_files.py` need only the `context` group
- [x] `npm run check` is green with no `.env`, with the baseline's counts plus the new tests
- [x] Commit: "Add the rate logic and the reference files"

## Phase 2: The clean world and the CSV template

Write `world.py`, `clean.py`, `template.py` and `lifecycle.py`. The generator now writes:
- the development set's `data/development/` (`world.json` with the business date and the projects, `subcontractors.json`, `workers.json` and `cases.json`) and one CSV for each submission in `data/development/payrolls/`
- `context/contractor_registry.yaml` and `context/apprentice_registrations.yaml`

Every payroll is clean in this phase, and every case is Accepted. Write the rule audit as a test helper, `data/tests/rule_audit.py`: a reference that tells whether a submission passes each rule, built on `wage_rules`. It's what the consistency tests check against.

- [x] `uv run pytest data --no-cov` passes, covering:
  - **The template:** every CSV has exactly the template's 31 columns in order, the same certification on every row, and money with two decimals; `template.py` reads back what it wrote
  - **The world:** 3 projects in three counties, Middlesex among them; 8 subcontractors, Garden State Electric among them; about 60 workers across the 8 crafts; 6 apprentices, 5 of them registered; the registry's one expiry and its renewal; 24 pairs engaged in week 12; about 200 expected filings
  - **Clean lines:** in every line the daily hours sum to `total_hours`, the line's pay follows its own hours and rates, and the rule audit passes every submission
- [x] **Determinism:** `data/tests/test_determinism.py` runs the generator twice into temporary folders, finds them identical, and finds the committed files the same as what it writes
- [x] `npm run generate` twice leaves `git status` clean
- [x] `npm run check` is green with no `.env`
- [x] Commit: "Build the clean world and the CSV template"

## Phase 3: The errors, the decoys and the demo anchors

Write `manifest.py` and `corruptions.py`. Write `data/error_manifest.yaml` by hand against the clean world: the 45 errors, 3 hidden instructions and 10 decoys, placed for the demo anchors. Then let `lifecycle.py` give the history cases their outcomes: corrected and Accepted, or still Returned to sub. The generator writes `data/evals/development_labels.json`, and week 12's 2 missing filings drop out.

- [ ] `uv run pytest data --no-cov` passes, covering:
  - **Labels and manifest:** every label matches a manifest entry and every entry a label
  - **Counts:** exactly the 45 errors by rule code from the brief's table, 3 screening flags and the 10 decoys
  - **Shortfalls:** every expected shortfall equals what `wage_rules` computes for that line
  - **The rule audit:** each labelled line or case fails its rule and no other; every decoy, every correction and every payroll outside the manifest passes every rule
  - **The lifecycle:** no Accepted case has a labelled error on its latest submission; a correction is a later submission on the same case; PC-0311 is Returned to sub with exactly three labels; week 12 has 22 cases and 2 missing filings
  - **The anchors:** each of the anchors above
- [ ] Determinism holds with the manifest applied
- [ ] `npm run check` is green with no `.env`
- [ ] Commit: "Seed the errors, decoys and anchors"

## Phase 4: The held-out and tiny sets, and the expected Copilot answers

Write `data/held_out_manifest.yaml` against a second world from its own seed, with its files in `data/held_out/` and its labels in `data/evals/held_out_labels.json`. Choose the tiny set into `data/evals/tiny_labels.json`. Write `periods.py` and `expected_answers.py`, and generate `data/copilot_expected.json`.

- [ ] `uv run pytest data --no-cov` passes, covering:
  - **Held-out:** about 100 payrolls, five subcontractors none of which is in the development set, its own workers, the same three counties and eight crafts, every rule code at least once, 2 screening flags, 5 decoys, and the same consistency checks as the development set
  - **Tiny:** 10 development cases, covering the eight check families, one hidden instruction and one decoy, with labels equal to the development labels for those cases
  - **Periods:** last week, this month and the last four weeks from the business date, on `week_ending`, including a business date that isn't a Monday
  - **Expected answers:** an answer for each of the six questions, every case in Marcus's scope; PC-0311's three exceptions; the Middlesex journeyman electrician's row and its effective date of 2026-10-01; recomputing the file gives the same answers
- [ ] The registry and apprentice files hold both worlds' subcontractors and apprentices
- [ ] Determinism holds across all three sets
- [ ] `npm run check` is green with no `.env`
- [ ] Commit: "Add the held-out and tiny sets and the Copilot's expected answers"

## Phase 5: The context server's new tools

Add the five tools to `context/server.py`, on `payroll_files.py`'s lookups.

- [ ] `uv run pytest context --no-cov` passes, with `context/tests/test_payroll_files.py` and `test_server.py` covering:
  - `get_wage_rate` on a work date before and after the pre-listed increase; an award date before the later determination, which isn't returned; a statewide craft; an unknown craft, classification and county, each refused clearly
  - `check_registration` before and after the expiry, and after the renewal; an unknown number, refused
  - `check_apprentice` for a registered apprentice at their level on a date, and for the unregistered apprentice
  - `get_filing_rules`, and `lookup_payroll_term` for a known term, whatever its case, and an unknown one
  - every answer naming its file and source
- [ ] Through the Lambda handler, `tools/list` names twelve tools, and every one is read-only and follows the API rules
- [ ] `npm run check:context` exits 0
- [ ] `npm run check` is green with no `.env`
- [ ] Commit: "Add the compliance context server's new tools"

## Phase 6: Through the running context layer, the docs, and the review of the branch

- [ ] With `npm run dev` running, a short script calls each new tool over MCP at `http://127.0.0.1:8006/mcp`. `get_wage_rate` for the Middlesex journeyman electrician, at the Lincoln School renovation's award date and the business date, returns the row `data/copilot_expected.json` names. No model is called.
- [ ] `data/README.md` describes the generator and how to run it, the manifests, the template column by column, the three sets and the labels. `docs/TECH_STACK.md` describes `wage_rules`, the new context files and tools, and the generator. `docs/STATUS.md` describes what's new and what stage 3 inherits: the backend package needing `context/wage_rules.py`, and seeding still loading the travel records.
- [ ] A fresh reviewer reads the whole branch against `stage-1-rebrand` with `docs/CODE_STANDARDS.md` and this plan, as `docs/PROCESS.md` describes. Whatever it would block the PR for is fixed, and the tests the fixes touch are run.
- [ ] `npm run check` is green with no `.env`, with coverage of at least 80% for Python and TypeScript
- [ ] Commit: "Record stage 2"

There are no live runs on a real model in this stage.

## Left for later stages

- Seeding the new world, the new schema, intake, the check tools and the payroll agent (stage 3), and the backend's package carrying `context/wage_rules.py`.
- Giving either agent the new tools (stages 3 and 6).
- Deleting the travel records, the old context files and the old tools (stage 3).
- The two-year expiry of a determination, which the research notes: every date in both worlds falls well inside two years of its award, so `wage_rules` doesn't handle it, and STATUS lists it as a known gap.
