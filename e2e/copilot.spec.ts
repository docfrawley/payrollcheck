import { type Locator, type Page, expect, test } from "@playwright/test";
import { nextStarted, started, stopTheWork } from "./api";

// The Copilot's sidebar on every signed-in page, driving a stand-in for the
// Copilot, which plays scripted turns through the backend with the reviewer's
// sign-in.

test.afterEach(async ({ request }) => {
  await stopTheWork(request);
});

const sidebar = (page: Page) =>
  page.getByRole("complementary", { name: "Copilot" });

async function ask(page: Page, message: string) {
  const box = sidebar(page).getByRole("textbox", { name: "Ask the Copilot" });
  await box.fill(message);
  await box.press("Enter");
}

// Where an element is once it's laid out. A busy machine may take a moment to
// lay the page out, and may render it again as it loads, so this asks until the
// element has a box.
async function boxOf(locator: Locator) {
  const boxes: NonNullable<Awaited<ReturnType<Locator["boundingBox"]>>>[] = [];
  await expect(async () => {
    const box = await locator.boundingBox();
    expect(box).not.toBeNull();
    if (box) boxes.push(box);
  }).toPass();
  const [box] = boxes;
  return box;
}

const PAGES = [
  "/",
  "/cases/PC-1201",
  "/scoreboard",
  "/improvement",
  "/configuration",
  "/settings",
];

test("the sidebar is open beside every page, and stays collapsed once collapsed", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  for (const path of PAGES) {
    await page.goto(path);
    await expect(sidebar(page)).toBeVisible();
    const main = await boxOf(page.getByRole("main"));
    const copilot = await boxOf(sidebar(page));
    expect(copilot.x).toBeGreaterThanOrEqual(main.x + main.width);
  }
  await sidebar(page)
    .getByRole("button", { name: "Collapse the Copilot" })
    .click();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Open the Copilot" }),
  ).toBeVisible();
  await expect(sidebar(page)).toHaveCount(0);
  await page.getByRole("button", { name: "Open the Copilot" }).click();
  await expect(sidebar(page)).toBeVisible();
});

test("on a narrow window the sidebar opens over the page, below the header, and Escape collapses it", async ({
  page,
}) => {
  await page.setViewportSize({ width: 800, height: 800 });
  await page.goto("/");
  // The header is laid out in full once the business date is in it.
  await expect(
    page.getByRole("banner").getByText(/^Business date/),
  ).toBeVisible();
  const main = await boxOf(page.getByRole("main"));
  const header = await boxOf(page.getByRole("banner"));
  const copilot = await boxOf(sidebar(page));
  expect(copilot.x).toBeLessThan(main.x + main.width);
  expect(copilot.x + copilot.width).toBeLessThanOrEqual(800);
  expect(copilot.y).toBeGreaterThanOrEqual(header.y + header.height);
  const who = page.getByLabel("Signed in");
  await who.getByRole("button", { name: "Account" }).click();
  // A click lands only on what's on top, so the sidebar leaves the menu clear.
  await who.getByRole("link", { name: "Settings" }).click();
  await expect(page).toHaveURL("/settings");
  await sidebar(page).getByRole("button", { name: "New conversation" }).focus();
  await page.keyboard.press("Escape");
  await expect(sidebar(page)).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Open the Copilot" }),
  ).toBeFocused();
});

test("the Copilot's steps show as cards, then its answer, and the page shows its action", async ({
  page,
  request,
}) => {
  await page.goto("/");
  const before = (await started(request)).length;
  await ask(page, "What needs me today?");
  const copilot = sidebar(page);
  const lookup = copilot.locator(".card", { hasText: "lookup_payroll_term" });
  await expect(lookup).toContainText("fringe");
  await lookup.getByRole("button").click();
  await expect(lookup).toContainText("Compliance manual, glossary, owned by");
  const action = copilot.locator(".card", { hasText: "start_dispatch" });
  await expect(action.getByLabel("Done")).toBeVisible();
  await expect(action).toHaveClass(/card-action/);
  const refused = copilot.locator(".card", { hasText: "get_case" });
  await expect(refused.getByText("Refused")).toBeVisible();
  await expect(refused).toContainText("Case PC-9999 not found");
  await expect(copilot.getByRole("table")).toBeVisible();
  await expect(copilot.getByText("3 model calls, $0.0021")).toBeVisible();
  expect(await nextStarted(request, before)).toMatchObject({
    operation: "work_run",
  });
  await expect(
    page.getByRole("region", { name: "Dispatch" }).getByText("Running"),
  ).toBeVisible();
  await copilot.getByRole("link", { name: "PC-0311" }).first().click();
  await expect(page).toHaveURL("/cases/PC-0311");
});

test("the earlier conversations hold each by its first question, and open it", async ({
  page,
}) => {
  await page.goto("/");
  await ask(page, "How did the latest dispatch go?");
  const copilot = sidebar(page);
  await expect(copilot.getByRole("table")).toBeVisible();
  await copilot.getByRole("button", { name: "New conversation" }).click();
  await expect(copilot.getByText("Hello, Dana.")).toBeVisible();
  await copilot.getByRole("button", { name: "Earlier conversations" }).click();
  const earlier = copilot.getByRole("button", {
    name: /How did the latest dispatch go\?/,
  });
  await expect(earlier.first()).toBeVisible();
  await earlier.first().click();
  await expect(
    copilot.getByText("How did the latest dispatch go?").first(),
  ).toBeVisible();
  await expect(copilot.getByRole("table")).toBeVisible();
});
