import { type Page, expect, test } from "@playwright/test";

// Uploading a payroll on a project's page, signed in as Dana Whitfield: a file
// the app refuses shows its reason, and the week-12 arrival for the municipal
// building becomes PC-1214, Received, in the queue.

const ARRIVAL = "data/development/arrivals/PC-1214-1.csv";
const MASONRY = "Delaware Valley Masonry LLC";

async function upload(page: Page, project: string) {
  await page.goto("/projects");
  await page.getByRole("link", { name: project }).click();
  const form = page.getByRole("region", { name: "Upload a payroll" });
  await form
    .getByRole("combobox", { name: "Subcontractor" })
    .selectOption({ label: MASONRY });
  await form.getByLabel("Payroll file").setInputFiles(ARRIVAL);
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
