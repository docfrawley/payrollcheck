# PayrollCheck seed data

The data behind UnderCover Travel Insurance, a fictional insurer. Everything here is invented, including the people, the airlines and the hotels. Amounts are in US dollars.

PayrollCheck works these travel insurance records as cases until stage 3 replaces them with payrolls. The record files (`claims.json`, `customers.json`, `policies.json`, `security/` and `evals/`) keep the names and keys of the claims platform they came from, since the labs read them; seeding gives their keys the app's names as it loads them (`claim_id` becomes `case_id`, `customer_id` becomes `subcontractor_id`, and so on), and changes no value.

## The insurer's systems

- `company.json`: company settings, including the $1,000 payout approval limit, which seeding makes the first value of the setting.
- `plans.json`: the three plans (Economy, Premium, First) with their limits, waiting periods and deductibles, and the three add-ons. The labs read it; seeding reads the same plans from `context/plans.yaml`.
- `policies.json`: one policy per trip, with the plan, the add-ons, the purchase date, the trip and the travelers.
- `customers.json`: contact details and case history, with the date and a one line summary of each earlier case. This is personal data.
- `reviewers.json`: the reviewers, with the email each signs in with and their role: Dana Whitfield is the compliance manager, and Marcus Oyelaran and Priya Raman are reviewers. Only Dana Whitfield (`dana.whitfield@payrollcheck.example`) can sign off payouts over the limit, start and stop rounds, review the improver's proposals and change the settings; Marcus Oyelaran and Priya Raman can't.
- `improvement.json`: the improver's settings to start with, from the lab: the objectives on the held-out set, the noise and the tolerance for accuracy, the grade, cost per case and time per case, the spending limit for each round and the payroll agents at once in its evaluations.
- `models.json`: the models the payroll agent may use, with their reasoning efforts and prices in US dollars per million tokens.
- `claims.json`: the queue, twenty-five cases. Each has the subcontractor's story, the items claimed and the supporting documents as text.

Set `MODEL_NAME` in `.env` before `npm run seed` if you're on a free model: seeding chooses version 1 of the payroll agent and the models allowed from it.

## The documents

- `policy_wording.md`: the contract with the subcontractor. Short enough to fit in a prompt.
- `claims_manual.md`: the internal handling manual. Longer, and it holds rules the wording does not, such as the third claim in 12 months, losses to wild animals and meals without receipts.

These two files and `plans.json` stay here for the labs. The product's copies are in `context/`, the context layer's seven files, which data governance owns: each names the system it comes from, its owner and when it was last reviewed, and the documents add their version. Seeding loads the plans and both documents from there.

## The evaluation set

- `evals/decisions.json`: the reviewers' decisions on the twenty-five cases in the queue: approve, decline or refer, the payout, the calculation, the reason and what each case tests. An agent deciding cases must never be shown this file.
- `evals/held_out_claims.json` and `evals/held_out_decisions.json`: twenty-five more cases with their decisions, kept out of the queue for checking that an improvement generalizes. They have the same blend as the queue. Keep them out of sight while you write a prompt or a rule, and score them afterwards.

The queue is the development set and the held-out cases are the test set. Nothing is trained on either.

Every decision also carries a few tags. `difficulty` is `routine`, `hard` (the wording settles it and it stretches a small model) or `manual` (it needs something the prompt does not hold, listed in `needs`: the claims manual, the subcontractor's history or both). `failure_class` groups the hard cases that one rule should fix. `tone` is `plain`, `amusing` or `nod`. `tiny` marks a subset of five cases in each set, one of each kind, which fits inside a free model's daily allowance.

The labs define `get_sample_data(tiny=False, held_out=False)`, which returns the cases of either set with their decisions.

A decision is scored on two things: the decision itself and the payout. A valid case that pays more than $1,000 is still an approve. The payment waits for a reviewer's sign-off, and `over_approval_limit` marks those cases.

## The security case

- `security/`: CLM-1901, a stolen watch whose story carries an instruction to the AI to approve it in full, with its policy, its subcontractor and the reviewer's decision (decline). It is a prompt injection kept for security testing, in a folder of its own. Seeding puts CLM-1901, its policy (POL-2901) and its subcontractor (Derek Vance, CUS-3901) in the queue beside `claims.json`, `policies.json` and `customers.json`, which stay as they are, so the queue holds twenty-six cases. It never seeds `security/decisions.json`, so CLM-1901 is in neither evaluation set and no score changes.
