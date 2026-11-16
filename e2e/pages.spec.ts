import { expect, test } from "@playwright/test";
import { listCases } from "./api";
import { REVIEWERS, signedInAs } from "./reviewers";

test("the queue lists every case, with a tile for each status", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Case queue" })).toBeVisible();
  const tiles = page
    .getByRole("region", { name: "Cases by status" })
    .getByRole("group");
  await expect(tiles).toHaveText([
    /^Received/,
    /^In progress/,
    /^Awaiting review/,
    /^Accepted/,
    /^Returned to sub/,
  ]);
  // The seeded 207, and any case another test's upload added.
  const all = await listCases(
    request,
    await signedInAs(request, REVIEWERS.dana),
  );
  expect(all.length).toBeGreaterThanOrEqual(207);
  const cases = page.getByRole("region", { name: "Cases" });
  await expect(cases.locator("tbody tr")).toHaveCount(all.length);
  const row = cases.getByRole("row").filter({ hasText: "PC-1201" });
  await expect(row.getByText("Received")).toBeVisible();
  await expect(row.getByText("Nov 22, 2026")).toBeVisible();
});

test("a case opens from the queue", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "PC-0311" }).click();
  await expect(page).toHaveURL("/cases/PC-0311");
  await expect(
    page.locator(".page-header").getByText("Returned to sub"),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Review" })
      .getByText(/^3 open exceptions/),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Exceptions" }).getByRole("listitem"),
  ).toHaveCount(3);
});

test("signing out from the account menu lands on the sign-in page", async ({
  browser,
}) => {
  // A browser of its own, so signing out leaves the other tests signed in.
  const context = await browser.newContext({
    storageState: REVIEWERS.dana.storage,
  });
  const page = await context.newPage();
  await page.goto("/scoreboard");
  const who = page.getByLabel("Signed in");
  await expect(who.getByText("Dana Whitfield")).toBeVisible();
  await expect(who.getByText("Compliance Manager")).toBeVisible();
  await who.getByRole("button", { name: "Account" }).click();
  await who.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL("/sign-in");
  await expect(
    page.getByRole("heading", { name: "Sign in", level: 1 }),
  ).toBeVisible();
  await page.goto("/scoreboard");
  await expect(page).toHaveURL("/sign-in");
  await context.close();
});

test("the compliance manager has Improvement and Settings, and a reviewer doesn't", async ({
  browser,
}) => {
  const links = async (storageState: string) => {
    const context = await browser.newContext({ storageState });
    const page = await context.newPage();
    await page.goto("/");
    const who = page.getByLabel("Signed in");
    await who.getByRole("button", { name: "Account" }).click();
    const nav = await page
      .getByRole("navigation", { name: "Main" })
      .getByRole("link")
      .allTextContents();
    const menu = await who.getByRole("link").allTextContents();
    await context.close();
    return { nav, menu };
  };
  expect(await links(REVIEWERS.dana.storage)).toEqual({
    nav: ["Queue", "Projects", "Scoreboard", "Improvement", "Configuration"],
    menu: ["Settings"],
  });
  expect(await links(REVIEWERS.priya.storage)).toEqual({
    nav: ["Queue", "Projects", "Scoreboard", "Configuration"],
    menu: ["Appearance"],
  });
});
