# NJ Prevailing Wage Rules for PayrollCheck

Researched 2026-11-13. Statute text (the PWA and the PWCR Act) is from NJDOL's [statute page](https://www.nj.gov/labor/wageandhour/tools-resources/laws/prevailingwageact.shtml), and N.J.A.C. 12:60 is from the [Cornell LII mirror](https://www.law.cornell.edu/regulations/new-jersey/title-12/chapter-60). Rate-sheet facts come from a real NJDOL determination ([Union County, 1/8/2025](https://lwdwebpt.dol.state.nj.us/archivewages/008085140-union-1-8-25.pdf)).

## Summary

Certified payrolls are due every payroll period within 10 days of the date wages were paid, both to the public body and to NJDOL via NJ Wage Hub. Every contractor and subcontractor needs a current PWCR certificate to bid and to work. NJDOL publishes rates by county (building trades) and statewide (heavy/highway). Each record has an effective date, wage (W), fringe (B) and total (T), plus an apprentice schedule, a ratio and notes on overtime, shifts and holidays. **The binding rate is the determination in force on the contract award date, plus any pre-determined increases listed in it, each starting on its listed date.** It is not simply the latest rate in force on the work date. Caveat: rates are "in effect for two years," after which a new determination must be selected. Overtime comes from the craft's notes and is usually daily (over 8 hours, Saturdays, Sundays and holidays), which is stricter than the state floor of over 40 hours a week. Apprentices must be USDOL-registered and are paid a percentage of the journeyman rate within a ratio (1:4 by default). An unregistered "apprentice" is owed the journeyman wage plus benefits.

## 1. MW-562 fields and required payroll record content

**Header fields** on [MW-562 (2/25)](https://www.nj.gov/labor/wageandhour/assets/PDFs/wagehub/MW-562%20(12_16B)Payroll%20Cert-Public%20Works%20test%2012%2016B%20(2).pdf), from the form text and the PDF field names:
- Contractor or Subcontractor (checkbox) and Name
- F.E.I.N.
- Business Address
- Project Name
- Project Location
- Contract I.D. or Project I.D.
- Contractor Registration #
- Payroll No.
- Week Ending Date
- Final Certification (checkbox)
- No Work Week (checkbox)
- Date Wages Due & Paid
- "Check if additional sheets attached"

**Employee rows** (10 per page), as numbered columns:
1. Employee Name and Address
2. Work Classification / Occupational Category, with Job Title (e.g. apprentice, journeyman, foreman)
3. Demographics: Sex (M/F/N), Race (W/B/A/N/I/M), Ethnicity (H/N)
4. Day and Date: SU–SA, mm/dd
5. Hours worked each day, on separate S (straight) and O (overtime) lines
6. Total Hours, S and O
7. Hourly Rate, S and O
8. Total Fringe Benefit Cost/Hour
9. Gross Amount Earned, This Project and This Week
10. Deductions: FICA, Federal Tax, State Tax, Other (Specify), Total Deductions; then Net Wages Paid for Week

**Page 2 certification.** The signer, who "pay[s] or supervise[s] the payment" of the employees, certifies:
- **(1)** "the full weekly wages earned" were paid for the period, with no rebates and only permitted deductions.
- **(2)** Payrolls are "correct and complete," rates are "not less than the applicable wage rates contained in any wage determination incorporated into the contract," and classifications "conform with the work he performed."
- **(3)** Apprentices are "duly registered with the United States Department of Labor ... and enrolled in a certified apprenticeship program."
- **(4)** Fringe was paid to (a) approved plans, funds or programs and/or (b) in cash.
- **(5)** The record is filed "within 10 days of the payment of wages."

Box (6) is the e-signature (Name, Title, Date). Falsification can bring civil or criminal prosecution. **Section 4(c)** (required if 4(a) is checked) gives hourly amounts per plan for Health/Welfare, Vacation/Holiday, Apprenticeship/Training, Pension and Other, plus the administrator, the USDOL filing number/EIN and the trustee. It instructs: "divide 2,000 hours into the benefit cost per year per employee."

**Required fields.** The paper form marks none. Wage Hub requires Week Ending Date, and Project Name, Description and Location at setup. Title is optional ([User Guide](https://nj.gov/labor/wageandhour/assets/PDFs/wagehub/NJWH_Contractor_User_Guide.pdf) pp. 11, 19).

**Register content required by law.** [N.J.S.A. 34:11-56.29(a)](https://www.nj.gov/labor/wageandhour/tools-resources/laws/prevailingwageact.shtml) requires "name, craft or trade, and actual hourly rate of wages paid," kept 2 years. [N.J.A.C. 12:60-2.1](https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-12-60-2-1) adds "address, social security number, ... actual daily, overtime and weekly hours worked in each craft or trade, gross pay, itemized deductions, and net pay," plus fringe paid to plans and in cash. The record must be "attested to by the employer," an owner, an officer or an authorized agent. **Note:** the current MW-562 has **no SSN field**, although the regulation lists SSN.

## 2. Prevailing wage determinations

**Publication.** Under [N.J.S.A. 34:11-56.30](https://www.nj.gov/labor/wageandhour/tools-resources/laws/prevailingwageact.shtml), the Commissioner sets the rate per craft per locality. It is based on collective bargaining agreements, with CBA benefit contributions treated as "an integral part of the wage rate." A determination "shall be conclusive for a period of 2 years from date of issuance unless superseded."

On NJDOL's [public-works rates page](https://www.nj.gov/labor/wageandhour/prevailing-rates/public-works), rates "vary by county and statewide and by the type of work performed." Building trades are listed by county. Operators and Heavy & General Laborers are "Statewide." Posted rates are "for Informational Purposes Only": an official determination is requested per contract by the public body.

**Record structure**, from the [Union County 1/8/2025 determination](https://lwdwebpt.dol.state.nj.us/archivewages/008085140-union-1-8-25.pdf). Each County + Craft lists, per classification (Journeyman, Foreman, General Foreman...), an effective date with **W** (wage/hr), **B** (fringe/hr) and **T** (total/hr). Example: Carpenter Journeyman, eff. 05/09/24, W 56.01 / B 33.76 / T 89.77. Each craft also has an Apprentice Rate Schedule, a "Ratio of Apprentices to Journeymen," and free-text Comments/Notes (workday, foreman rules, shifts, overtime, holidays, scope). Statewide packages show several effective-date columns: Operating Engineers 07/01/2024 at 58.88 / 39.15 / 98.03, then 07/01/2025 at a total of 100.53, plus a "Rates Expiration Date."

**Change frequency.** No fixed schedule. Updates follow CBA changes, so dates vary by craft. A determination is conclusive for 2 years (56.30), and "rates that have expired will remain in effect until new rates are posted" (rate sheet intro).

**Which rate applies.** This is the key answer.
- The determination preamble (identical in [2015](https://www.nj.gov/labor/forms_pdfs/lsse/wagearchives/Burlington/2015/burlington31815.pdf) and 2025) says: "Applicable prevailing wage rates are those wages and fringe benefits in effect on the date the contract is awarded. All pre-determined rate increases listed at the time the contract is awarded must also be paid, beginning on the dates specified."
- The statute requires the contract to specify the rate for each craft "during the anticipated term thereof" ([56.28](https://www.nj.gov/labor/wageandhour/tools-resources/laws/prevailingwageact.shtml)).
- NJDOL's [June 2024 release](https://www.nj.gov/labor/lwdhome/press/2024/20240607_prevailingwage.shtml) adds: "Applicable rates are those wages and fringe benefits in effect on the date the contract is awarded to a general contractor ... All rates are in effect for two years, at which time a new rate determination must be selected from the date of expiration."
- "A separate wage rate determination must be ascertained for each separate public works contract" ([rates page](https://www.nj.gov/labor/wageandhour/prevailing-rates/public-works)).

Putting this together: **the controlling date is contract award, not bid advertisement and not simply the work date.** Within a contract, a week's required rate is the row of the award-date determination whose effective date is the latest one on or before the work date. Pre-determined increases listed at award therefore do kick in mid-project. A new determination published after award does **not** apply, *unless* the two-year window has run out.

How a subcontractor's rate is pinned is not addressed. The prime contract's award date is the reasonable reading, since the rates go into the prime contract (56.28) and "awarded to a general contractor" points the same way.

## 3. Fringe benefits

**Cash in lieu is allowed.** "Employers not providing such benefits must pay the fringe benefit amount directly to the employee each payday. Employers providing benefits worth less than the fringe benefit amount must pay the balance directly to the employee each payday" ([rate sheet intro](https://lwdwebpt.dol.state.nj.us/archivewages/008085140-union-1-8-25.pdf)). MW-562 box 4(b) certifies cash payment. Wage Hub notes "fringe benefits in cash count as wages" and that 4(a) and 4(b) may both be checked ([User Guide](https://nj.gov/labor/wageandhour/assets/PDFs/wagehub/NJWH_Contractor_User_Guide.pdf) p. 21–22).

**Plan credit.** Contributions go to "approved plans, funds or programs" (N.J.A.C. 12:60-2.1; MW-562 4(a)). They are itemized per hour by category in 4(c). Annual costs are converted with the rule "divide 2,000 hours into the benefit cost per year per employee."

**Shortfall.** No primary-source formula exists beyond the cash-the-balance rule. The implied computation is: shortfall/hr = required B − (plan credit/hr + cash fringe/hr), applied to the hours worked.

**On overtime hours:** "Unless otherwise stated ... the fringe benefit rate for overtime hours remains at the straight time rate." Where the overtime notes say "inclusive of benefits," B is multiplied by the same factor as W.

## 4. Overtime

**State law floor.** 1.5× the regular rate for hours over 40 in a week ([NJDOL MW-220 poster](https://www.nj.gov/labor/forms_pdfs/lsse/mw-220.pdf); N.J.S.A. 34:11-56a4).

**Prevailing wage overtime** comes from each craft's Comments/Notes and is usually stricter ([Union County 1/8/2025](https://lwdwebpt.dol.state.nj.us/archivewages/008085140-union-1-8-25.pdf)):
- **Carpenter and Electrician:** over 8 hours a day, outside the regular workday, or any Saturday hour at 1.5× "inclusive of benefits." Sundays and holidays at 2×. Carpenters may also work 4×10 Monday to Thursday at straight time.
- **Boilermaker:** Labor Day at 4×, plus a parity clause (double time if another craft gets it).
- Each craft lists its own holidays (Sunday holidays observed Monday) and its own shift differentials.

**Wage Hub mismatch.** Wage Hub's field help defines Overtime as hours "in excess of 40 hours a week" (User Guide p. 20), which conflicts with the daily rules in the sheets. Treat the rate sheet as controlling: MW-562 item (2) certifies against the wage determination.

## 5. Apprentices

**Definition.** An apprentice is "registered, in good standing, in an apprenticeship program approved or certified by the Office of Apprenticeship in the United States Department of Labor" ([12:60-6.1](https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-12-60-6-1)). The contractor must keep written evidence of registration on file ([6.2](https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-12-60-6-2)).

**Rates.** "The apprentice wage rate is a percentage of the journeyman wage rate ... The apprentice benefit rate is the full journeyman benefit rate, unless otherwise indicated" (rate sheet intro).

Periods vary by craft. Electrician: yearly 40/49/58/68/80% of both wage and benefit. Boilermaker: 1000-hour steps from 65% to 95%. Carpenter: benefit = 59.25% of apprentice wage + $0.57, with a grandfathered schedule for apprentices "registered as of 5-1-19."

**Ratio.** Set per craft (Electrician 2:3, Carpenter 1:3), with a default of 1:4 if the CBA is silent ([6.3(b)](https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-12-60-6-3)). With no apprentice schedule, the journeyman rate is owed ([6.3(c)](https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-12-60-6-3)). Some notes force the journeyman rate for particular tasks (Boilermaker "HIGH WORK").

**Not registered.** NJDOL audits and requires payment of "the difference between the rate of an apprentice and the rate of a journeyman plus any applicable benefits the worker is entitled to as a journeyman" ([6.4](https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-12-60-6-4)). Separately, any contractor that directly employs craftworkers must participate in a USDOL-registered apprenticeship program to hold PWCR registration ([56.52(a)(6)–(7)](https://www.nj.gov/labor/wageandhour/tools-resources/laws/prevailingwageact.shtml)).

## 6. Filing timeliness and NJ Wage Hub

**Statute.** [N.J.S.A. 34:11-56.29(b)(2)](https://www.nj.gov/labor/wageandhour/tools-resources/laws/prevailingwageact.shtml): records "shall be submitted ... to the public body awarding the contract ... and to the department through the secure process on its Internet website, each payroll period within 10 days of the date on which the wages were paid to a worker." Under (b)(3), online submission "does not relieve the contractor of the requirement to submit ... to the public body."

**Regulation.** [N.J.A.C. 12:60-5.1(c)(1)(i)](https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-12-60-5-1): "submitted each payroll period within 10 days of the payment of wages." The public body must "receive, file, store and make available for inspection" the records.

**Who files.** Every contractor and subcontractor files its own payroll. A prime sees its subcontractors' Wage Hub filings under "Subcontractor Submissions."

**Wage Hub.** Authorized by P.L.2023, c.138 ([Aug 2023 release](https://www.nj.gov/labor/lwdhome/press/2023/20230822_prevailingwage.shtml)). NJDOL's [July 17, 2024 release](https://www.nj.gov/labor/lwdhome/press/2024/20240717_publicworks.shtml) says: "Effective August 15, registered contractors performing public work are required to report certified payroll records" via [NJ Wage Hub](https://njwages.nj.gov/), "both online via NJ Wage Hub and in hard copy" to the public body. Per the [User Guide](https://nj.gov/labor/wageandhour/assets/PDFs/wagehub/NJWH_Contractor_User_Guide.pdf):
- Project setup captures public body, project ID, award date, amount, county, subcontractors (FEIN + registration number) and the contract file.
- Payroll can be entered manually, uploaded as an MW-562 PDF or CSV, or copied from a prior week.
- Each filing gets a confirmation number. Registration and debarment status at the time of filing are recorded.
- A correction is a resubmission with the same week-ending date. The prime's Final Certification closes the project.

## 7. Public Works Contractor Registration Act

**Who must register.** Contractors may not bid, and may not list a subcontractor in a bid, unless that party is registered "at the time the bid is made." No contractor or subcontractor, "including a subcontractor not listed in the bid proposal, shall engage in the performance of any public work ... unless ... registered" ([56.51](https://www.nj.gov/labor/wageandhour/tools-resources/laws/prevailingwageact.shtml)). Subcontractors not working at any covered site are exempt (56.51a). Certificates for listed subcontractors go to the public body before award, and an application does not count as a certificate (56.55).

**Validity and renewal.** "Valid for one calendar year from the date of registration. Registrations shall be renewed not less than 30 days before the expiration date" ([56.54](https://www.nj.gov/labor/wageandhour/tools-resources/laws/prevailingwageact.shtml)). The fee is $500 a year. After two consecutive years, a contractor may choose a 2-year registration for $750 (56.53). Contractors remain under a continuing compliance obligation between renewals, and NJDOL may revoke or suspend for violations (56.54a).

**Expired mid-project.** Performing public work while unregistered is itself prohibited (56.51), so any work after expiry is a violation. The [June 15, 2022 NJDOL/DCA/DOE letter](https://nj.gov/labor/wageandhour/assets/PDFs/PWPWC%20Registration%20Act%20Updates.pdf) warns of a Stop Work Order covering "the public body's project and potentially all other public works projects." It adds that the certificate "must be effective as of the date the contractor ... submitted its bid." Under 56.56, sanctions include a $2,500–$25,000 fine, up to 3 years' disqualification, denial or revocation for up to 5 years, a bond of up to $10,000 per worker, and immediate suspension.

**June 2022 "updates."** This is a reminder letter to public bodies, not a rule change. It notes three things. First, the Act "now also requires" USDOL-registered apprenticeship participation (P.L.2021, c.423; 56.52(a)(6)–(7), 56.55a). Second, under P.L.2021, c.301 (eff. May 7, 2022), a low bidder 10% or more below the next bid must certify it will pay prevailing wage (56.27a), and contracts must stipulate prevailing wage. Third, public bodies should check PWCR status and debarment before award.

**Number format.** Not published. Wage Hub also issues a separate 10-digit "Contractor Registration Reference ID" (User Guide p. 4). Secondary listings show 6-digit certificate numbers (unconfirmed).

## 8. Penalties and back-pay exposure (summary)

- **Back wages:** "the full amount of such prevailing wage less any amount actually paid," plus costs and fees. An agreement to work for less is "no defense" ([56.40](https://www.nj.gov/labor/wageandhour/tools-resources/laws/prevailingwageact.shtml)). Workers have 2 years to protest (56.34(b)).
- **Penalties and fees:** administrative penalties up to $2,500 for a first violation and $5,000 after ([56.35(b)](https://www.nj.gov/labor/wageandhour/tools-resources/laws/prevailingwageact.shtml), [12:60-8.3](https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-12-60-8-3)). A fee of 10%, 18% or 25% applies on wages paid through NJDOL ([8.4](https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-12-60-8-4)), plus possible interest.
- **Criminal:** $100–$1,000 and/or 10–90 days, with "each week ... and each worker so paid" a separate offense (56.35(a)).
- **Other:** stop-work order across all sites, at $5,000 a day for violating it (56.35(d)). Debarment for 3 years (56.37–.38). Up to 25% (max $100,000) withheld if records aren't produced within 10 days (56.31(d)).

## 9. Beyond current checks

- **Foreman/crew rules** from the rate-sheet notes, each tier with its own rate. Carpenter: 2 or more on a job requires 1 Foreman. Electrician: Foreman and Sub-Foreman counts tied to the number of journeymen.
- **Classification scope:** classification must "conform with the work he performed." Some variants are scope-limited (A/C service rates "may NOT be used for any work in new construction"). 12:60-6.2(b) bars invented job titles used to dodge apprentice ratios.
- **Shift differentials, task premiums** (e.g. hazmat +$5/hr) and holiday lists.
- **Worker orientation** with a signed form kept 6 years (unless a CBA applies), and posting rates at the site ([56.32](https://www.nj.gov/labor/wageandhour/tools-resources/laws/prevailingwageact.shtml)).
- **Debarment** (56.38), and the 56.33 sworn statement of wages owed before final payment.
- **Coverage thresholds:** $19,375 municipal, $2,000 for other public bodies ([12:60-1.4](https://www.law.cornell.edu/regulations/new-jersey/N-J-A-C-12-60-1-4)).
- **Permissible deductions** (Payment of Wages Law), and completeness of the demographics block.
- **Residency/local hiring:** no NJ PWA requirement found.

## Implications for PayrollCheck

**(a) Rate-table shape.** Key on `(determination_id, county|"STATEWIDE", craft, classification)`, each key holding **several dated rows** of `effective_date, wage, fringe, total`. The determination carries `issued_date` and a nullable `expiration_date`. Each craft carries `apprentice_schedule` (interval yearly or by hours, per-period wage %, benefit rule: full B, %, or % + constant), `apprentice_ratio`, `overtime_rules`, `shift_rules`, `holidays[]`, `foreman_rules` and `notes`. Return the source row so findings can cite W/B/T.

**(b) Which rate applies to a week.** Change `get_wage_rate(craft, county, date)` to take `project_id`:
1. Resolve the project's `award_date`.
2. Select the determination in force on that date.
3. Return the latest row with `effective_date <= work_date`.

This handles the "mid-project rate change" test correctly: a pre-listed increase applies, while a newly published determination does not. Add one edge case: if `work_date > award-date determination + 2 years`, switch to the determination in force on the expiry date, and flag this as low-confidence. Store `award_date` on the project. Note that Wage Hub captures it.

**(c) Overtime representation.** Make the rules data, not code. Use an ordered list of predicates (`daily_over: 8`, `weekly_over: 40`, `day_of_week: SAT → 1.5`, `SUN → 2.0`, `holiday → 2.0`, `named_holiday: Labor Day → 4.0`, `outside_regular_window`) plus `multiplier_applies_to: wage | wage+fringe`. Support an alternate schedule, such as 4×10 Monday to Thursday with Friday as make-up. Apply the rule that gives the highest multiplier per hour. Keep the 40-hour state floor as a fallback. Flag MW-562/Wage Hub rows where "O" hours only appear above 40 a week but the sheet requires daily overtime.

**(d) Apprentice representation.** `check_apprentice(worker_id)` should return: registered (bool); program sponsor/number; USDOL registration date; current period/level and its % (by year or hours); and status on the work date (in good standing, not cancelled). The checks are:
- the rate paid ≥ % × the journeyman W of the applicable row
- the benefit rule is met
- ratio per contractor per craft against the sheet ratio (default 1:4); the time window for measuring it (day or week) is not specified, so the per-day window is a design choice
- no schedule, or journeyman-only tasks, means the journeyman rate is owed
- unregistered means exposure = ((journeyman W − paid W) + (journeyman B − paid B)) × hours (12:60-6.4)

**(e) Timeliness rule.** `due = date_wages_paid + 10 days` (assume calendar days; see Open) (MW-562 field "Date Wages Due & Paid"). This is measured **per payroll period from payment**, not from week-end. Check filing to both the public body and Wage Hub. Treat "No Work Week" filings as valid members of the sequence. Treat same-week-ending resubmissions as corrections, not duplicates. A Final Certification marks the end of the sequence.

**(f) Registration data.** `check_registration(registration_no, date)` should return: legal name, FEIN, certificate number, `effective_date`, `expiration_date` (1 year, or 2 years under the 2-year option), status (active, expired, suspended, revoked) with status dates, and debarment. Check it against every **work date** in the week, not just the filing date, and against the bid date for listed subcontractors. Since the format is unpublished, generate synthetic 6-digit certificate numbers and do not hard-validate the format.

## Open / unconfirmed

- Whether a subcontractor's rates are pinned to the prime's award date or to the subcontract date. No primary text was found. The prime award date is inferred.
- How the "two years, then a new determination" rule works in practice. It appears in NJDOL press releases and in 56.30, not in the regulation.
- The PWCR certificate number format: no official specification. Six digits is seen only in third-party copies.
- MW-562 required fields: none are marked on paper. The MW-562 instruction page was not in the PDF obtained.
- Whether Wage Hub's "over 40/week" overtime help reflects actual validation logic.
- 34:11-56.50 is marked "effective until October 20, 2026." The text now in force was not found.
- Wage Hub start date: the rates page says "as of August 2023," while the July 2024 release says "effective August 15" (2024). The 2024 date is used here.
- The fringe-shortfall method beyond the 2,000-hour annualization.
- Whether the "10 days" are calendar or business days: the statute and the regulation say only "10 days."
