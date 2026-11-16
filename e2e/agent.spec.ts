import { expect, test } from "@playwright/test";
import {
  type Request,
  recordCheckFindings,
  recordExceptionReport,
  recordStep,
  startCase,
} from "./api";
import { REVIEWERS } from "./reviewers";

// These tests stand in for the payroll agent by calling the API through the
// dashboard's proxy, and watch the case page update without a reload. Each
// works a week-12 case no other test touches.

const CHECKS = [
  "check_form",
  "check_contractor_registration",
  "check_rates",
  "check_overtime",
  "check_arithmetic",
  "check_apprentices",
  "check_timeliness",
  "check_classification",
];

const BASE_SHORT = {
  rule: "rate.base_short",
  worker_id: "W-001",
  line_no: 1,
  expected: "$60.85 an hour",
  actual: "$58.85 an hour",
  shortfall_cents: 6400,
  citation: "The rate determination in force on the project's award date",
};

// Works a case to Awaiting review with no exceptions, every check finding
// nothing.
async function checkClean(request: Request, caseId: string) {
  await startCase(request, caseId, `e2e-${caseId}`);
  for (const check of CHECKS) await recordCheckFindings(request, caseId, check);
  await recordExceptionReport(request, caseId);
}

// Works a case to Awaiting review with one base rate short, raised from the
// rates check's finding, and a draft notice.
async function checkWithAnException(request: Request, caseId: string) {
  await startCase(request, caseId, `e2e-${caseId}`);
  const [candidate] = await recordCheckFindings(
    request,
    caseId,
    "check_rates",
    [BASE_SHORT],
  );
  await recordExceptionReport(request, caseId, {
    raised: [candidate.candidate_id],
    notice: "Please pay W-001 the base rate in the determination.",
  });
}

test("the case page shows the agent at work and its report", async ({
  page,
  request,
}) => {
  await page.goto("/cases/PC-1203");
  const heading = page.locator(".page-header");
  await expect(heading.getByText("Received")).toBeVisible();
  await expect(page.getByText(/No steps yet/)).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Submission 1" }).getByRole("table"),
  ).toBeVisible();

  await startCase(request, "PC-1203", "e2e-1");
  await recordStep(
    request,
    "PC-1203",
    "screening",
    "No instructions found. The notes are about hours.",
  );
  await expect(heading.getByText("In progress")).toBeVisible();
  await expect(
    page.getByText("The payroll agent is checking this payroll."),
  ).toBeVisible();
  await recordCheckFindings(request, "PC-1203", "check_form");
  const [candidate] = await recordCheckFindings(
    request,
    "PC-1203",
    "check_rates",
    [BASE_SHORT],
  );
  const steps = page.locator(".steps > li");
  await expect(steps).toHaveText([
    /Screening No instructions found\. The notes are about hours\./,
    /Checked check_form: Nothing found/,
    /Checked check_rates: 1 found/,
  ]);

  await recordStep(request, "PC-1203", "tool_call", "get_project()");
  await recordStep(
    request,
    "PC-1203",
    "tool_result",
    'get_project: {"project_id":"PRJ-01"}',
  );
  await recordExceptionReport(request, "PC-1203", {
    raised: [candidate.candidate_id],
    notice: "Please pay W-001 the base rate in the determination.",
  });
  await recordStep(request, "PC-1203", "message", "One exception, reported.");
  await expect(heading.getByText("Awaiting review")).toBeVisible();
  await expect(page.getByText("One exception, reported.")).toBeVisible();
  const exceptions = page.getByRole("region", { name: "Exceptions" });
  await expect(exceptions.getByText("rate.base_short")).toBeVisible();
  await expect(exceptions.getByText("High")).toBeVisible();
  await expect(exceptions.getByText("$64.00")).toBeVisible();
  await expect(exceptions.getByText(BASE_SHORT.citation)).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Send-back notice" })
      .getByText("Please pay W-001 the base rate in the determination."),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Review" }).getByText(/^1 open exception/),
  ).toHaveText("1 open exception, $64.00 short.");
});

test("the case page shows the agent's judgment beside the checks' findings", async ({
  page,
  request,
}) => {
  await startCase(request, "PC-1204", "e2e-judgment");
  await recordCheckFindings(request, "PC-1204", "check_form");
  const [rate] = await recordCheckFindings(request, "PC-1204", "check_rates", [
    BASE_SHORT,
  ]);
  const [change] = await recordCheckFindings(
    request,
    "PC-1204",
    "check_classification",
    [
      {
        rule: "classification.changed",
        worker_id: "W-002",
        line_no: 2,
        expected: "Electrician Journeyman",
        actual: "Electrician Foreman",
        shortfall_cents: null,
        citation: "Last week's payroll",
      },
    ],
  );
  const reason = "The line note explains the move to foreman this week.";
  await recordExceptionReport(request, "PC-1204", {
    raised: [rate.candidate_id],
    dismissed: [{ candidate_id: change.candidate_id, reason }],
    added: [
      {
        rule: "form.project_mismatch",
        worker_id: null,
        line_no: null,
        expected: "Lincoln School renovation",
        actual: "Lincoln Middle School",
        shortfall_cents: null,
        citation: "Our project and subcontractor records",
      },
    ],
    notice: "Please pay W-001 the base rate and name the project as awarded.",
  });

  await page.goto("/cases/PC-1204");
  const checks = page.getByRole("region", { name: "Checks and judgment" });
  await expect(checks.locator(".check")).toHaveText([
    "check_form Nothing found",
    /^check_rates.*rate\.base_short W-001, line 1, \$64\.00 short.*Raised as an exception$/,
    new RegExp(`^check_classification.*Dismissed: ${reason}$`),
  ]);
  await expect(
    checks.getByText(
      "Raised with no check behind it: Our project and subcontractor records",
    ),
  ).toBeVisible();
  const own = page
    .getByRole("region", { name: "Exceptions" })
    .getByRole("listitem")
    .filter({ hasText: "form.project_mismatch" });
  await expect(own.getByText("Agent's own judgment")).toBeVisible();
});

test("the case page shows each submission, every kind of step and the context used", async ({
  page,
  request,
}) => {
  const rates = {
    file: "rate_determinations.yaml",
    system: "NJDOL prevailing wage rate determinations, as we record them",
    owner: "Compliance manager",
    reviewed: "2026-09-01",
  };
  await page.goto("/cases/PC-1206");
  await expect(page.getByRole("heading", { level: 2 })).toContainText([
    "Submission 2",
    "Submission 1",
  ]);

  await startCase(request, "PC-1206", "e2e-steps");
  await recordStep(
    request,
    "PC-1206",
    "lookup",
    "Wage rate: Middlesex, electrician",
    [rates],
  );
  await recordStep(request, "PC-1206", "lookup", 'Glossary: "zeppelin"');
  await recordStep(
    request,
    "PC-1206",
    "refusal",
    "record_exception_report: Refused with status 422: No candidate has this shortfall",
  );
  const steps = page.locator(".steps > li");
  await expect(steps).toHaveText([
    /Looked up Wage rate: Middlesex, electrician.*owned by Compliance manager, reviewed Sep 1, 2026/,
    /Looked up Glossary: "zeppelin"/,
    /Refused record_exception_report: Refused with status 422/,
  ]);
  const used = page.getByRole("region", { name: "Context used" });
  await expect(used.getByRole("heading", { level: 3 })).toHaveText([
    "rate_determinations.yaml",
    "Found nothing",
  ]);
});

test("a clean case is signed off on the dashboard, which accepts it", async ({
  page,
  request,
}) => {
  await checkClean(request, "PC-1220");
  await page.goto("/cases/PC-1220");
  const heading = page.locator(".page-header");
  await expect(heading.getByText("Awaiting review")).toBeVisible();
  const review = page.getByRole("region", { name: "Review" });
  await expect(review.getByText("No open exceptions.")).toBeVisible();
  await review.getByRole("button", { name: "Sign off" }).click();
  await expect(heading.getByText("Accepted")).toBeVisible();
  await expect(review.getByText(/^Signed off on /)).toBeVisible();
  await expect(review.getByRole("button")).toHaveCount(0);
});

test("a sign-off is refused while an exception is open, with the reason", async ({
  page,
  request,
}) => {
  await checkWithAnException(request, "PC-1221");
  await page.goto("/cases/PC-1221");
  const review = page.getByRole("region", { name: "Review" });
  await review.getByRole("button", { name: "Sign off" }).click();
  await expect(review.getByRole("alert")).toHaveText(
    /^Case PC-1221 has 1 open exception/,
  );
  await expect(
    page.locator(".page-header").getByText("Awaiting review"),
  ).toBeVisible();
});

test.describe("signed in as Marcus Oyelaran", () => {
  test.use({ storageState: REVIEWERS.marcus.storage });

  test("any reviewer can sign off a case", async ({ page, request }) => {
    await checkClean(request, "PC-1222");
    await page.goto("/cases/PC-1222");
    await expect(
      page.getByLabel("Signed in").getByText("Marcus Oyelaran"),
    ).toBeVisible();
    await page.getByRole("button", { name: "Sign off" }).click();
    await expect(
      page.locator(".page-header").getByText("Accepted"),
    ).toBeVisible();
  });
});
