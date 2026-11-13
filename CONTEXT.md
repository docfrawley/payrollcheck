# PayrollCheck — domain glossary

The ubiquitous language for PayrollCheck. Code, tables, routes and UI use these terms; UnderCover's vocabulary (claim, payout, policy, customer) does not survive into the product.

## Terms

**Case** — The unit of work in the queue: one subcontractor's certified payroll obligation for one project and one week. A case moves through the statuses Received → Awaiting review → Accepted or Returned to sub. The dispatcher works cases; tables and plumbing say `case` (e.g. `cases`, `run_cases`, `held_out_cases`).

**Payroll** — The certified payroll document itself: the MW-562 payroll certification plus the payroll register for that week. Said of the document, never of the queue unit.

**Submission** — One upload of a payroll into a case. A case holds one or more submissions, numbered in order; a corrected upload after Returned to sub is a new submission on the same case, which reopens it.

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
