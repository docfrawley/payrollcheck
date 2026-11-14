import { expect, test as setup } from "@playwright/test";
import { REVIEWERS, TEST_PASSWORD } from "./reviewers";

// Signs in on the sign-in page as each reviewer the tests use, and keeps each
// browser's storage, with its session, for the tests.
for (const reviewer of Object.values(REVIEWERS)) {
  setup(`sign in as ${reviewer.name}`, async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL("/sign-in");
    await page.getByLabel("Email").fill(reviewer.email);
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(
      page.getByLabel("Signed in").getByText(reviewer.name),
    ).toBeVisible();
    await page.context().storageState({ path: reviewer.storage });
  });
}
