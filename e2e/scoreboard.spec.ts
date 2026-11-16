import { expect, test } from "@playwright/test";
import type { LabelMatch, ScoredCase } from "../dashboard/src/api";
import { percent } from "../dashboard/src/format";
import { NONE_CAUGHT } from "../dashboard/src/measures";
import {
  type Finding,
  type Request,
  finishRun,
  getEvaluation,
  recordCheckFindings,
  recordExceptionReport,
  recordModelCall,
  recordScreeningFlag,
  recordWorkTime,
  startCase,
  startEvaluation,
  stopTheWork,
} from "./api";

// This test starts an evaluation of the tiny set as Dana Whitfield, which the
// app creates, then stands in for the agent and its payroll agents. It reads
// each copy's labels from the evaluation, as the Scoreboard shows them, and
// plays the copies out through the API: one copy's labels caught to the cent
// beside a false exception, the hidden instruction flagged, and every other
// copy reported clean, so its labels are missed. Its copies are its own.

test.afterEach(async ({ request }) => {
  await stopTheWork(request);
});

// A check's finding that catches a label to the cent.
const catching = (label: LabelMatch): Finding => ({
  rule: label.rule,
  worker_id: label.worker_id,
  line_no: label.line_no,
  expected: "As the rules require",
  actual: "As the payroll states",
  shortfall_cents: label.expected_shortfall_cents,
  citation: "The rule",
});

// A finding that matches no label on the copy: a rule about the certification
// that none of its labels has.
function falseFinding(copy: ScoredCase): Finding {
  const rule = ["form.unsigned", "form.missing_field", "sequence.gap"].find(
    (each) => !copy.labels.some((label) => label.rule === each),
  );
  return {
    rule: rule ?? "form.unsigned",
    worker_id: null,
    line_no: null,
    expected: "Signed",
    actual: "Not signed",
    shortfall_cents: null,
    citation: "MW-562 payroll certification",
  };
}

// Plays a copy out as the payroll agent would: the hidden instruction flagged,
// the copy chosen to be caught raising every label and one false exception,
// and any other reported clean.
async function playOut(request: Request, copy: ScoredCase, caught: ScoredCase) {
  if (copy.screening_expected) {
    await recordScreeningFlag(request, copy.case_id, "A hidden instruction");
    return;
  }
  const findings =
    copy === caught ? [...copy.labels.map(catching), falseFinding(copy)] : [];
  const candidates = await recordCheckFindings(
    request,
    copy.case_id,
    "check_form",
    findings,
  );
  await recordExceptionReport(request, copy.case_id, {
    raised: candidates.map((candidate) => candidate.candidate_id),
    notice: candidates.length > 0 ? "Please correct and resubmit." : "",
  });
}

// The Scoreboard's measures as worked out from the labels: the one copy's
// labels caught of all, one false exception, every caught shortfall right,
// each hidden instruction flagged, and each copy's cost and time.
function measuresShown(
  copies: ScoredCase[],
  caught: ScoredCase,
  size: number,
): string[] {
  const labels = copies.reduce((sum, copy) => sum + copy.labels.length, 0);
  const count = caught.labels.length;
  const withMoney = caught.labels.some(
    (label) => label.expected_shortfall_cents !== null,
  );
  const hidden = copies.filter((copy) => copy.screening_expected).length;
  return [
    `Tiny set, ${String(size)} payrolls`,
    `${percent(count / labels)} (${String(count)} of ${String(labels)})`,
    `1 (${(100 / size).toFixed(1)} per 100)`,
    withMoney ? "100%" : NONE_CAUGHT,
    `${String(hidden)} of ${String(hidden)}`,
    "$0.0125",
    "40 s",
  ];
}

test("the Scoreboard shows an evaluation played out through the API", async ({
  page,
  request,
}) => {
  const { run_id, number } = await startEvaluation(request, "tiny", 5);
  const { cases: copies, size } = await getEvaluation(request, run_id);
  const labelled = copies.filter((copy) => copy.labels.length > 0);
  expect(labelled.length).toBeGreaterThanOrEqual(2);
  const [caught, missed] = labelled;
  // The copy caught raises a false exception and expects no screening flag.
  expect(caught.screening_expected).toBe(false);
  expect(caught.labels.map((label) => label.rule)).not.toContain(
    falseFinding(caught).rule,
  );
  const hidden = copies.filter((copy) => copy.screening_expected);

  for (const { case_id } of copies) {
    await startCase(request, case_id, `e2e-${case_id}`);
    await recordModelCall(request, case_id, run_id, 0.0125);
    await recordWorkTime(request, case_id, run_id, 40);
  }
  for (const copy of copies) await playOut(request, copy, caught);
  await finishRun(request, run_id);

  await page.goto("/scoreboard");
  const evaluation = `Evaluation #${String(number)}`;
  const row = page.getByRole("row", { name: new RegExp(`^${evaluation} `) });
  await expect(row.getByText("Finished")).toBeVisible();
  for (const shown of measuresShown(copies, caught, size))
    await expect(row.getByText(shown, { exact: true })).toBeVisible();
  await expect(row.getByRole("cell").last()).toHaveText(/^\d+ s$/);

  await row.getByRole("link", { name: evaluation }).click();
  await expect(page).toHaveURL(`/scoreboard/${run_id}`);
  const table = page.getByRole("region", { name: "Copies" });
  const rows = table.locator("tbody tr");
  await expect(rows).toHaveCount(copies.length);
  // The copies the agent got something wrong on come first, tinted: the one
  // with a false exception, and every other labeled copy, each missed.
  await expect(table.locator("tbody tr.copy-off")).toHaveCount(labelled.length);
  for (let index = 0; index < labelled.length; index++)
    await expect(rows.nth(index)).toHaveClass("copy-off");

  const caughtRow = rows.filter({ hasText: caught.case_id });
  await expect(caughtRow).toHaveClass("copy-off");
  await expect(caughtRow.getByText("Caught", { exact: true })).toHaveCount(
    caught.labels.length,
  );
  await expect(caughtRow.getByText("Matched", { exact: true })).toHaveCount(
    caught.labels.length,
  );
  await expect(caughtRow.getByText("False", { exact: true })).toHaveCount(1);
  const missedRow = rows.filter({ hasText: missed.case_id });
  await expect(missedRow).toHaveClass("copy-off");
  await expect(missedRow.getByText("Missed", { exact: true })).toHaveCount(
    missed.labels.length,
  );
  for (const copy of hidden)
    await expect(
      rows.filter({ hasText: copy.case_id }).getByText("Expected and flagged"),
    ).toBeVisible();

  await missedRow.getByRole("link", { name: missed.case_id }).click();
  await expect(page).toHaveURL(`/cases/${missed.case_id}`);
  await expect(
    page.getByText(`A copy of ${missed.copy_of} in an evaluation`),
  ).toBeVisible();
  await page.getByRole("link", { name: "evaluation", exact: true }).click();
  await expect(page).toHaveURL(`/scoreboard/${run_id}`);
  await rows.filter({ hasText: caught.case_id }).getByRole("link").click();
  await expect(page).toHaveURL(`/cases/${caught.case_id}`);
  await expect(page.getByRole("button", { name: "Sign off" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Send back" })).toHaveCount(0);
});
