import { expect, test } from "@playwright/test";
import { REVIEWERS } from "./reviewers";

// Only this file changes the settings.

test("a compliance manager changes the spending limit", async ({ page }) => {
  await page.goto("/settings");
  const objectives = page.getByRole("group", {
    name: "Objectives on the held-out set",
  });
  await expect(objectives.getByLabel("False exceptions at most")).toHaveValue(
    "2.5",
  );
  await expect(objectives.getByText("per 100 payrolls")).toBeVisible();
  await expect(objectives.getByLabel("Notice score at least")).toHaveValue(
    "0.80",
  );
  const limit = page
    .getByRole("group", { name: "Spending" })
    .getByLabel("Spending limit for each round");
  await limit.fill("0.75");
  const save = page.getByRole("button", { name: "Save", exact: true });
  const dialog = page.getByRole("dialog");

  await save.click();
  await expect(
    dialog.getByText("Spending limit for each round: $5.00 to $0.75"),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(page.getByText(/Not changed since/)).toBeVisible();

  await save.click();
  await dialog.getByRole("button", { name: "Save the settings" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(/Last changed by Dana Whitfield/)).toBeVisible();

  await page.reload();
  await expect(limit).toHaveValue("0.75");
  await expect(page.getByText(/Last changed by Dana Whitfield/)).toBeVisible();
});

test("the appearance is kept in the browser", async ({ page }) => {
  await page.goto("/settings");
  const appearance = page.getByRole("group", { name: "Appearance" });
  await appearance.getByLabel("Dark").check();
  const root = page.locator("html");
  await expect(root).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("body")).toHaveCSS(
    "background-color",
    "rgb(11, 23, 36)",
  );
  await page.reload();
  await expect(root).toHaveAttribute("data-theme", "dark");

  await page.emulateMedia({ colorScheme: "dark" });
  await appearance.getByLabel("Light").check();
  await expect(page.locator("body")).toHaveCSS(
    "background-color",
    "rgb(242, 244, 247)",
  );
});

test.describe("signed in as Priya Raman", () => {
  test.use({ storageState: REVIEWERS.priya.storage });

  test("the settings are the compliance manager's, and the appearance hers", async ({
    page,
  }) => {
    await page.goto("/settings");
    await expect(
      page.getByText(
        "Only the compliance manager can see the settings. Priya Raman can't.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Save" })).toHaveCount(0);
    await expect(page.getByRole("group", { name: "Appearance" })).toBeVisible();
  });
});

test("a compliance manager changes the business date, sees it in the header, and resets it", async ({
  page,
}) => {
  await page.goto("/settings");
  const header = page.getByRole("banner");
  await expect(header.getByText("Business date Nov 23, 2026")).toBeVisible();
  const field = page
    .getByRole("group", { name: "Business date" })
    .getByLabel("Business date");
  const save = page.getByRole("button", { name: "Save", exact: true });
  const dialog = page.getByRole("dialog");

  await field.fill("2026-11-30");
  await save.click();
  await expect(
    dialog.getByText("Business date: Nov 23, 2026 to Nov 30, 2026"),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Save the settings" }).click();
  await expect(header.getByText("Business date Nov 30, 2026")).toBeVisible();

  await page.getByRole("button", { name: "Use the real date" }).click();
  await save.click();
  await expect(
    dialog.getByText("Business date: Nov 30, 2026 to the real date"),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Save the settings" }).click();
  await expect(dialog).toBeHidden();
  await expect(header.getByText("Business date Nov 30, 2026")).toBeHidden();

  // Back to the seeded date, for the other files.
  await field.fill("2026-11-23");
  await save.click();
  await dialog.getByRole("button", { name: "Save the settings" }).click();
  await expect(header.getByText("Business date Nov 23, 2026")).toBeVisible();
});
