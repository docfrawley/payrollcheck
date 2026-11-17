import { expect, test } from "@playwright/test";
import { recordCheckFindings, recordExceptionReport, startCase } from "./api";
import { REVIEWERS } from "./reviewers";
import { AGENT_KEY_HEADERS } from "./servers";

// A reviewer edits the agent's draft notice on the case page and sends the case
// back with it, which returns it to the sub with its exception still open and
// shows the notice as the email the outbox recorded.

const NOTICE = "Please pay Kim Dimitrov the base rate in the determination.";
const EDITED = `${NOTICE} Line 1 is $2.00 an hour short.`;
// The subcontractor's payroll contact, at an example domain.
const SUBCONTRACTORS_CONTACT = /^payroll@.*\.example$/;

test.use({ storageState: REVIEWERS.marcus.storage });

test("Marcus edits the notice and sends the case back with it", async ({
  page,
  request,
}) => {
  await startCase(request, "PC-1215", "e2e-8");
  const [candidate] = await recordCheckFindings(
    request,
    "PC-1215",
    "check_rates",
    [
      {
        rule: "rate.base_short",
        worker_id: "W-001",
        line_no: 1,
        expected: "$60.85 an hour",
        actual: "$58.85 an hour",
        shortfall_cents: 6400,
        citation: "The rate determination in force on the project's award date",
      },
    ],
  );
  await recordExceptionReport(request, "PC-1215", {
    raised: [candidate.candidate_id],
    notice: NOTICE,
  });
  // The agent's key never takes a reviewer's actions.
  const byTheAgent = await request.post("/api/cases/PC-1215/send-back", {
    headers: AGENT_KEY_HEADERS,
  });
  expect(byTheAgent.ok()).toBe(false);

  await page.goto("/cases/PC-1215");
  const heading = page.locator(".page-header");
  await expect(heading.getByText("Awaiting review")).toBeVisible();
  const notice = page.getByRole("region", { name: "Send-back notice" });
  const text = notice.getByLabel("The notice to the subcontractor");
  await expect(text).toHaveValue(NOTICE);
  await text.fill(EDITED);
  await notice.getByRole("button", { name: "Send back" }).click();

  await expect(heading.getByText("Returned to sub")).toBeVisible();
  const review = page.getByRole("region", { name: "Review" });
  await expect(
    review.getByText(/^Sent back to the subcontractor on /),
  ).toBeVisible();
  await expect(review.getByRole("button")).toHaveCount(0);
  await expect(
    page
      .getByRole("region", { name: "Exceptions" })
      .getByText("Open, submission 1"),
  ).toBeVisible();
  const email = page.getByRole("region", { name: "Sent to the subcontractor" });
  await expect(email.getByText(SUBCONTRACTORS_CONTACT)).toBeVisible();
  await expect(email.getByText(/^Certified payroll PC-1215, /)).toBeVisible();
  await expect(email.getByText(/^Marcus Oyelaran </)).toBeVisible();
  await expect(email.getByText(EDITED)).toBeVisible();

  await page.goto("/");
  await expect(
    page.getByRole("row", { name: /PC-1215/ }).getByText("Returned to sub"),
  ).toBeVisible();
});

test("Marcus edits a returned case's notice and sends it again, and it stays returned", async ({
  page,
}) => {
  const AGAIN = "Line 2 is still $0.72 an hour short of the base rate.";
  await page.goto("/cases/PC-0601");
  const heading = page.locator(".page-header");
  await expect(heading.getByText("Returned to sub")).toBeVisible();
  const notice = page.getByRole("region", { name: "Send-back notice" });
  await expect(notice.getByRole("button", { name: "Send back" })).toHaveCount(
    0,
  );
  await notice.getByLabel("The notice to the subcontractor").fill(AGAIN);
  await notice.getByRole("button", { name: "Send again" }).click();

  const email = page.getByRole("region", { name: "Sent to the subcontractor" });
  await expect(email.getByText(AGAIN)).toBeVisible();
  await expect(email.getByText(/^Certified payroll PC-0601, /)).toBeVisible();
  await expect(heading.getByText("Returned to sub")).toBeVisible();
});
