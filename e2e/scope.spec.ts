import { expect, test } from "@playwright/test";
import {
  getRun,
  listCases,
  nextStarted,
  recordRunCases,
  started,
  stopTheWork,
} from "./api";
import { REVIEWERS, signedInAs } from "./reviewers";
import type { CaseSummary } from "../dashboard/src/api";

// Signed in as Marcus Oyelaran, who reviews the Lincoln School renovation and the
// municipal building: the road resurfacing's cases don't exist for him, and a
// dispatch he starts works the whole queue while showing him his own cases and
// a count of the rest.

const ROAD = "PRJ-03";

test.use({ storageState: REVIEWERS.marcus.storage });

test.afterEach(async ({ request }) => {
  await stopTheWork(request);
});

test("Marcus sees no road-resurfacing case, and its page isn't found", async ({
  page,
}) => {
  await page.goto("/");
  const cases = page.getByRole("region", { name: "Cases" });
  await expect(cases.getByRole("row", { name: /PC-1201/ })).toBeVisible();
  await expect(cases.getByRole("row", { name: /PC-1217/ })).toHaveCount(0);
  await expect(
    cases.getByRole("link", { name: "Road resurfacing" }),
  ).toHaveCount(0);
  const answer = page.waitForResponse("**/api/cases/PC-1217");
  await page.goto("/cases/PC-1217");
  expect((await answer).status()).toBe(404);
  await expect(
    page.getByText("Case not found. Choose one from the queue."),
  ).toBeVisible();
});

test("Marcus's dispatch works the whole queue, and shows him his own cases", async ({
  page,
  request,
}) => {
  const everyone = (await listCases(
    request,
    await signedInAs(request, REVIEWERS.dana),
  )) as CaseSummary[];
  const received = everyone.filter((line) => line.status === "received");
  const theirs = received.filter((line) => line.project_id === ROAD);
  expect(theirs.length).toBeGreaterThan(0);

  await page.goto("/");
  const panel = page.getByRole("region", { name: "Dispatch" });
  const before = (await started(request)).length;
  await panel.getByRole("button", { name: "Start a dispatch" }).click();
  const payload = await nextStarted(request, before);
  const runId = String(payload.run_id);
  // The agent's stand-in records every Received case, whoever started it.
  await recordRunCases(
    request,
    runId,
    received.map((line) => line.case_id),
  );
  expect((await getRun(request, runId)).cases).toHaveLength(received.length);

  await expect(panel.getByRole("row")).toHaveCount(
    received.length - theirs.length + 1,
  );
  await expect(
    panel.getByText(`And ${String(theirs.length)} cases on other projects.`),
  ).toBeVisible();
  await expect(panel.getByRole("row", { name: /PC-1217/ })).toHaveCount(0);
});
