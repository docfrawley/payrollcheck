import { type Page, expect, test } from "@playwright/test";

// Uploading a payroll on a project's page, signed in as Dana Whitfield: a file
// the app refuses shows its reason, the week-12 arrival for the municipal
// building becomes PC-1214, Received, in the queue, and a corrected payroll for
// an Accepted case reopens it.

const ARRIVAL = "data/development/arrivals/PC-1214-1.csv";
const MASONRY = "Delaware Valley Masonry LLC";

async function upload(page: Page, project: string, file = ARRIVAL) {
  await page.goto("/projects");
  await page.getByRole("link", { name: project }).click();
  const form = page.getByRole("region", { name: "Upload a payroll" });
  await form
    .getByRole("combobox", { name: "Subcontractor" })
    .selectOption({ label: MASONRY });
  await form.getByLabel("Payroll file").setInputFiles(file);
  await form.getByRole("button", { name: "Upload" }).click();
  return form;
}

test("an upload on the wrong project's page is refused with its reason", async ({
  page,
}) => {
  const form = await upload(page, "Lincoln School renovation");
  await expect(form.getByRole("alert")).toHaveText(
    "This payroll is for PRJ-02, not PRJ-01.",
  );
  await expect(form.getByRole("status")).toHaveCount(0);
});

test("the week-12 arrival uploads as a Received case in the queue", async ({
  page,
}) => {
  const form = await upload(page, "Municipal building");
  const created = form.getByRole("status");
  await expect(created).toHaveText("Uploaded as PC-1214, Received.");
  await created.getByRole("link", { name: "PC-1214" }).click();
  await expect(page).toHaveURL("/cases/PC-1214");
  const heading = page.locator(".page-header");
  await expect(heading.getByText("Received")).toBeVisible();
  await expect(heading.getByText(MASONRY)).toBeVisible();

  await page.goto("/");
  const row = page.getByRole("row", { name: /PC-1214/ });
  await expect(row.getByText("Received")).toBeVisible();
  await expect(
    row.getByRole("link", { name: "Municipal building" }),
  ).toHaveAttribute("href", "/projects/PRJ-02");
});

test("a corrected payroll for an Accepted case reopens it", async ({
  page,
}) => {
  // PC-0506 was returned, corrected and accepted in the history, so its first
  // submission's exceptions are superseded.
  const form = await upload(
    page,
    "Lincoln School renovation",
    "data/development/payrolls/PC-0506-2.csv",
  );
  const reopened = form.getByRole("status");
  await expect(reopened).toHaveText("Uploaded as PC-0506, Received.");
  await reopened.getByRole("link", { name: "PC-0506" }).click();
  await expect(
    page.locator(".page-header").getByText("Received"),
  ).toBeVisible();
  const earlier = page
    .getByRole("region", { name: "Exceptions" })
    .getByRole("region", { name: "Submission 1" });
  await expect(
    earlier.getByRole("heading", { name: "Submission 1, before a correction" }),
  ).toBeVisible();
  await expect(
    earlier.getByText("Superseded, submission 1").first(),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Case" })
      .getByRole("definition")
      .filter({ hasText: /^3$/ }),
  ).toBeVisible();
});
