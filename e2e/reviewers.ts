import { type APIRequestContext, expect } from "@playwright/test";
import { AUTH_STAND_IN } from "./servers";

// The reviewers the end-to-end tests sign in as, with the password the Auth
// stand-in signs every reviewer in with, and where each one's signed-in browser
// storage is kept for the tests.
export const TEST_PASSWORD = "e2e-reviewer-password";

export const REVIEWERS = {
  dana: {
    reviewer_id: "HND-01",
    name: "Dana Whitfield",
    email: "dana.whitfield@payrollcheck.example",
    storage: "e2e/.auth/dana.json",
  },
  marcus: {
    reviewer_id: "HND-02",
    name: "Marcus Oyelaran",
    email: "marcus.oyelaran@payrollcheck.example",
    storage: "e2e/.auth/marcus.json",
  },
};

// Signs a reviewer in through the Auth stand-in, as the dashboard does, and
// returns the headers of a request from them.
export async function signedInAs(
  request: APIRequestContext,
  reviewer: { email: string },
) {
  const response = await request.post(
    `${AUTH_STAND_IN}/auth/v1/token?grant_type=password`,
    { data: { email: reviewer.email, password: TEST_PASSWORD } },
  );
  await expect(response).toBeOK();
  const { access_token } = (await response.json()) as { access_token: string };
  return { Authorization: `Bearer ${access_token}` };
}
