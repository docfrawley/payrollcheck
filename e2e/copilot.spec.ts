import { type Locator, type Page, expect, test } from "@playwright/test";
import { stopTheWork } from "./api";

// The Copilot's sidebar on every signed-in page, driving a stand-in for the
// Copilot, which plays scripted turns through the backend with the reviewer's
// sign-in: a lookup, a draft notice, a refusal and a formatted answer.

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

test("a lookup, a draft notice, a refusal and a formatted answer, each with its cards", async ({
  page,
}) => {
  await page.goto("/");
  const copilot = sidebar(page);
  const answers = copilot.locator(".answer");

  await ask(
    page,
    "Which subs on the Lincoln School renovation have open exceptions?",
  );
  const lookup = copilot.locator(".card", { hasText: "list_cases" });
  await expect(lookup.getByLabel("Done")).toBeVisible();
  await expect(lookup.getByLabel("Cases")).toBeVisible();
  await expect(answers.nth(0)).toContainText("Garden State Electric LLC");
  await expect(
    answers.nth(0).getByRole("link", { name: "PC-0601" }),
  ).toBeVisible();

  await ask(
    page,
    "Draft a send-back notice for PC-0311 covering all three exceptions.",
  );
  const drafted = copilot.locator(".card", { hasText: "draft_notice" });
  await expect(drafted.getByLabel("Done")).toBeVisible();
  await expect(drafted).toHaveClass(/card-action/);
  await expect(answers.nth(1)).toContainText(
    "Edit and send it on the case page",
  );

  await ask(page, "Sign off PC-0311");
  await expect(answers.nth(2)).toContainText(
    "I can't sign off PC-0311: a reviewer signs off on its case page.",
  );

  await ask(page, "How much underpayment have we flagged this month?");
  const table = answers.nth(3).getByRole("table");
  await expect(table).toBeVisible();
  // The other specs add exceptions to the shared database, so the total isn't
  // fixed, but it is in dollars, above zero, from PC-1009 among others.
  await expect(table).toContainText(/\$[1-9][\d,]*\.\d{2}/);
  await expect(answers.nth(3)).toContainText(/From .*PC-1009/);
  await expect(
    copilot.getByText("3 model calls, $0.0021").first(),
  ).toBeVisible();
  // No card asks the reviewer to confirm anything: the Copilot never decides.
  await expect(copilot.getByRole("button", { name: /confirm/i })).toHaveCount(
    0,
  );
  await expect(copilot.locator(".card")).toHaveCount(3);

  await answers.nth(1).getByRole("link", { name: "PC-0311" }).click();
  await expect(page).toHaveURL("/cases/PC-0311");
  const notice = page.getByRole("region", { name: "Send-back notice" });
  await expect(
    notice.getByText(/^Drafted by PayrollCheck Copilot for Dana Whitfield/),
  ).toBeVisible();
  await expect(
    notice.getByLabel("The notice to the subcontractor"),
  ).toHaveValue(/^Certified payroll PC-0311, Municipal building/);
  await expect(
    notice.getByRole("button", { name: "Send again" }),
  ).toBeVisible();
});

test("the greeting offers the reviewers' questions", async ({ page }) => {
  await page.goto("/");
  const questions = sidebar(page).getByRole("list", {
    name: "Questions to ask",
  });
  await expect(questions.getByRole("button")).toHaveText([
    "What needs me today?",
    "Which subs on my projects have open exceptions?",
    "How much underpayment have we flagged this month?",
    "Which payrolls are late or missing for last week?",
  ]);
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
