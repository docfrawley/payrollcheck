import { expect, test } from "@playwright/test";
import { recordCheckFindings, recordExceptionReport, startCase } from "./api";
import { AGENT_KEY_HEADERS } from "./servers";

// A reviewer sends a case with an open exception back to its subcontractor on
// the case page, which returns it to the sub with its exception still open and
// its notice drafted.

const NOTICE = "Please pay Kim Dimitrov the base rate in the determination.";

test("a case with an exception is sent back to the subcontractor", async ({
  page,
  request,
}) => {
  await startCase(request, "PC-1224", "e2e-8");
  const [candidate] = await recordCheckFindings(
    request,
    "PC-1224",
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
  await recordExceptionReport(request, "PC-1224", {
    raised: [candidate.candidate_id],
    notice: NOTICE,
  });
  // The agent's key never takes a reviewer's actions.
  const byTheAgent = await request.post("/api/cases/PC-1224/send-back", {
    headers: AGENT_KEY_HEADERS,
  });
  expect(byTheAgent.ok()).toBe(false);

  await page.goto("/cases/PC-1224");
  const heading = page.locator(".page-header");
  await expect(heading.getByText("Awaiting review")).toBeVisible();
  const review = page.getByRole("region", { name: "Review" });
  await review.getByRole("button", { name: "Send back" }).click();

  await expect(heading.getByText("Returned to sub")).toBeVisible();
  await expect(
    review.getByText(/^Sent back to the subcontractor on /),
  ).toBeVisible();
  await expect(review.getByRole("button")).toHaveCount(0);
  await expect(
    page
      .getByRole("region", { name: "Exceptions" })
      .getByText("Open, submission 1"),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Send-back notice" }).getByText(NOTICE),
  ).toBeVisible();

  await page.goto("/");
  await expect(
    page.getByRole("row", { name: /PC-1224/ }).getByText("Returned to sub"),
  ).toBeVisible();
});
