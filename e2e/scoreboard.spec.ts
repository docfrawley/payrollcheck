import { expect, test } from "@playwright/test";
import {
  finishRun,
  recordExceptionReport,
  recordModelCall,
  recordWorkTime,
  startCase,
  startEvaluation,
  stopTheWork,
} from "./api";

// This test starts an evaluation of the tiny set as Dana Whitfield, which the
// app creates, then stands in for the agent and its payroll agents, reporting
// every copy clean through the API, and checks the Scoreboard and the
// evaluation's page. Its copies are its own. A clean report raises nothing, so
// whatever the labels say, nothing is caught and nothing is false.

test.afterEach(async ({ request }) => {
  await stopTheWork(request);
});

test("the Scoreboard shows an evaluation played out through the API", async ({
  page,
  request,
}) => {
  const { run_id, number, cases } = await startEvaluation(request, "tiny", 5);
  expect(cases.length).toBeGreaterThan(0);
  for (const { case_id } of cases) {
    await startCase(request, case_id, `e2e-${case_id}`);
    await recordModelCall(request, case_id, run_id, 0.0125);
    await recordWorkTime(request, case_id, run_id, 40);
    await recordExceptionReport(request, case_id);
  }
  await finishRun(request, run_id);

  await page.goto("/scoreboard");
  const evaluation = `Evaluation #${String(number)}`;
  const row = page.getByRole("row", { name: new RegExp(`^${evaluation} `) });
  await expect(row.getByText("Finished")).toBeVisible();
  await expect(
    row.getByText(`Tiny set, ${String(cases.length)} payrolls`),
  ).toBeVisible();
  await expect(row.getByText(/^0% \(0 of \d+\)$/)).toBeVisible();
  for (const shown of ["0 (0.0 per 100)", "None caught", "$0.0125", "40 s"])
    await expect(row.getByText(shown, { exact: true })).toBeVisible();
  await expect(row.getByRole("cell").last()).toHaveText(/^\d+ s$/);

  await row.getByRole("link", { name: evaluation }).click();
  await expect(page).toHaveURL(`/scoreboard/${run_id}`);
  const copies = page.getByRole("region", { name: "Copies" });
  await expect(copies.locator("tbody tr")).toHaveCount(cases.length);
  await expect(copies.getByText("Expected, missed").first()).toBeVisible();

  const [first] = cases;
  const copyRow = copies.getByRole("row", { name: new RegExp(first.case_id) });
  await expect(copyRow.getByText("Awaiting review")).toBeVisible();
  await copyRow.getByRole("link", { name: first.case_id }).click();
  await expect(page).toHaveURL(`/cases/${first.case_id}`);
  const original = first.case_id.replace(/-E\d+$/, "");
  await expect(
    page.getByText(`A copy of ${original} in an evaluation`),
  ).toBeVisible();
  await expect(
    page.getByText("A copy in an evaluation can't be signed off or sent back."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign off" })).toHaveCount(0);
});
