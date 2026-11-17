# PayrollCheck seed data

This folder holds PayrollCheck's payroll world: synthetic payrolls for Pinelands Builders, made by the generator, which seeding loads, and our people and settings.

## The payroll world

Everything in it is invented and synthetic: the projects, the subcontractors, the workers, their wages and the rates they are checked against, which are labelled "Synthetic data — not real rates". Amounts are in US dollars, in whole cents in every file but the payroll CSVs.

### The generator

`npm run generate` (`uv run -m data.generate`, run as a module from the repo root, since it imports `context/`) builds every file below from fixed seeds and the two manifests, the same on every run, byte for byte. Its output is committed, and `npm run check` fails if the committed files differ from what it writes, so after changing the generator or a manifest, run it and commit what it writes. It imports nothing from the app; it shares the one rate logic, `context/wage_rules.py`, with the context layer, and writes three of the context layer's files from the same data: `context/rate_determinations.yaml`, `context/contractor_registry.yaml` and `context/apprentice_registrations.yaml`.

It works in two passes. The first draws a world (`payroll_world/world.py`, from a spec in `worlds.py`) and pays every expected filing correctly (`clean.py`): every week of every subcontractor's engagement window on a project. The second applies the manifest (`corruptions.py` and `decoys.py`): each error corrupts its payroll one way and leaves a ground-truth label, its shortfall worked out by the one rate logic; each decoy shapes a clean payroll to look wrong; each hidden instruction goes into a text cell. `cases.py` then makes each filing its case through `lifecycle.py`.

- Weeks run Monday to Sunday, the week ending on the Sunday, and wages are paid on the Monday after. Nobody works on a Sunday or a holiday, so every premium hour is at time and a half.
- A case id is `PC-WWPP`: the week and the number of the pair of a subcontractor and a project. PC-0311 is week 3 of pair 11.
- A payroll number runs from 1 in the first week of the engagement window, one more each week, a No Work Week payroll included.

### The sets

- **Development** (`development/`): the Lincoln School renovation (Middlesex), the municipal building (Monmouth) and the road resurfacing (Ocean), eight subcontractors on all three by week 12, 64 workers across eight crafts with six apprentices, one of them not registered, and twelve weeks from the week ending 2026-09-06. The business date is Monday 2026-11-23, the day the week-12 wave arrives. Weeks 1 to 11 are history: a clean case is Accepted; most cases with errors were Returned to sub and Accepted on a clean correction; a late filing, the week of work while unregistered and the cases the manifest names stay Returned to sub with their exceptions open. Week 12's cases are Received, and two of its expected filings are missing.
- **Held-out** (`held_out/`): three other projects in the same counties, five other subcontractors with workers of their own, none sharing a name with the development world's, the same crafts, and eight weeks from the week ending 2026-10-04, every case waiting with one submission. Only the improver's keep/rollback gate scores it.
- **Tiny**: ten development cases, one for each check family, one hidden instruction and one decoy, for free models, listed in `evals/tiny_labels.json`.

Each set's folder holds `world.json` (the business date, the weeks, and the projects with their award dates, public bodies, contract numbers, reviewers and engagement windows, each with its pair's number), `subcontractors.json` (legal name, FEIN, registration number and payroll contact), `workers.json` (each worker's established craft and classification), `cases.json` (each case's status, the reviewer who decided it and when, and its submissions with the date each was received and its file) and `payrolls/`, a CSV for each submission, `PC-WWPP-N.csv` for submission N. The development set's `arrivals/` holds the payrolls of the two missing filings, `PC-1214-1.csv` and `PC-1223-1.csv`, which seeding never loads: they are the files a reviewer uploads when the payrolls arrive. A corrected payroll is uploaded the same way, on its project's page for its subcontractor: an upload for a week that already has a case becomes that case's next submission and reopens it, even when it was Accepted. Uploading any of a case's own CSVs from `payrolls/` again shows it.

### The manifests

`error_manifest.yaml` (development) and `held_out_manifest.yaml` are written by hand against the clean worlds, and `payroll_world/manifest.py` reads each against its world, refusing an entry the generator can't apply. Each has:

- `errors`: the case, the rule, the worker for a rule about a line, and what the corruption needs, such as `cut_cents`.
- `decoys`: the case and the kind of decoy, such as `daily_overtime` or `cash_in_lieu`.
- `hidden_instructions`: the case, the text cell and the text.
- `still_returned`: history cases left Returned to sub, beside those whose errors can't be corrected.
- `missing`: the last week's expected filings left with no case.
- `tiny`: the tiny set's cases.

### The labels

`evals/development_labels.json`, `evals/held_out_labels.json` and `evals/tiny_labels.json` hold the answer key, which the payroll agent must never see. Each has `exceptions`, every exception a perfect review of each case's first submission finds: `case_id`, `rule`, `worker_id` and `line_no` (null for a rule about the whole payroll, `line_no` counting the worker lines from 1) and `expected_shortfall_cents` (null where no money is owed), and `screening_flags`, the cases with a hidden instruction. A decoy has no label; the development and held-out files list each set's `decoys` beside the labels, each `case_id` with its `kind`, which seeding loads for the scoring alone: the success criteria read the `rate_increase_week` and `later_determination` decoys to show the rate increase applied from the right week and the later determination ignored. An exception is caught when an open exception matches its case, rule and worker.

### The template

One CSV for each submission, one row for each worker's week, with the certification repeated on every row. A No Work Week payroll is one row with the certification filled in, the worker columns blank and `no_work_week` set to `true`. `payroll_world/template.py` writes and reads it: `read_upload`, which the app's intake uses, refuses a file that can't become a payroll with the reason (no header row, a missing column, certification columns that differ between rows, a number or date that won't parse, a `no_work_week` that isn't `true` or `false`) and reads anything else as it is, however wrong. `payroll_record` gives a payroll as the app keeps it in JSON.

| Column | What it holds |
|---|---|
| `contractor_name` | The subcontractor's name as it writes it |
| `fein` | The federal employer identification number, `NN-NNNNNNN` |
| `registration_no` | The public works contractor registration number, 6 digits |
| `project_id` | Our project, such as `PRJ-01` |
| `payroll_no` | The payroll's number on the project, from 1 |
| `week_ending` | The Sunday the week ends, `YYYY-MM-DD` |
| `wage_payment_date` | The date the week's wages were paid |
| `signed_by` | Who signed the certification, with their title |
| `signed_on` | The date it was signed |
| `no_work_week` | `true` or `false` |
| `worker_id` | Our worker id, such as `W-025` |
| `worker_name` | The worker's name |
| `classification` | The craft and classification paid, such as `Electrician Journeyman`, `Plumber Foreman` or `Carpenter Apprentice` |
| `apprentice_level` | An apprentice's level, blank for anyone else |
| `hours_mon` to `hours_sun` | The hours each day, to the quarter hour, such as `8.00` |
| `total_hours` | The week's hours |
| `base_rate` | The hourly wage paid, dollars and cents such as `61.10` |
| `fringe_rate` | The hourly fringe paid to benefit plans |
| `fringe_cash` | The hourly fringe paid in cash in lieu of benefits; it counts toward the fringe with `fringe_rate` |
| `overtime_hours` | The hours paid at time and a half, which are among `total_hours` |
| `gross` | The week's wages: `base_rate` for every hour plus half of it for each overtime hour, fringe cash not included |
| `deductions` | The week's deductions |
| `net` | `gross` less `deductions` |
| `line_notes` | The subcontractor's note on the line, such as why a classification changed |
| `payroll_notes` | The subcontractor's note on the payroll |

Dates are ISO, hours have two decimals and money is dollars and cents with two decimals and no symbol.

### The Copilot's expected answers

`copilot_expected.json` holds, for each of the Copilot's six questions in `docs/SPEC.md`, the case ids, totals in cents and rate record the answer must give, for Marcus Oyelaran's scope (the Lincoln School renovation and the municipal building) at the business date, as seeding will leave the database before any dispatch. `payroll_world/expected_answers.py` computes them, with every period resolved by `payroll_world/periods.py`.

## Our people and settings

- `reviewers.json`: the reviewers, with the email each signs in with, their role (`compliance_manager` or `reviewer`) and the projects they review, which seeding loads into `project_reviewers`: Dana Whitfield is the compliance manager, on every project (`"all"`); Marcus Oyelaran reviews PRJ-01 and PRJ-02, and Priya Raman PRJ-03. Only the compliance manager starts and stops rounds, reviews the improver's proposals and sees or changes the settings.
- `improvement.json`: the improver's settings to start with: the objective on the held-out set's catch rate, the noise and the tolerance for the catch rate, cost per case and time per case, the spending limit for each round and the payroll agents at once in its evaluations.
- `models.json`: the models the payroll agent may use, with their reasoning efforts and prices in US dollars per million tokens.

Set `MODEL_NAME` in `.env` before `npm run seed` if you're on a free model: seeding chooses version 1 of the payroll agent and the models allowed from it.
