import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Case } from "./api";
import { awaiting, baseShort, showCase, unsigned } from "./caseTesting";
import type { RuleEntry } from "./exceptions";
import { shortfallInCents } from "./format";
import { Refusal, panel, sent } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const RULES: RuleEntry[] = [
  {
    rule: "sequence.gap",
    check: "check_timeliness",
    severity: "low",
    money: false,
    worker: false,
  },
  {
    rule: "rate.fringe_short",
    check: "check_rates",
    severity: "high",
    money: true,
    worker: true,
  },
];
const DISMISSAL = "POST /api/cases/PC-1201/exceptions/7/dismissal";

function showWithRules(shown: Case) {
  const shownCase = showCase(shown);
  shownCase.routes["GET /api/rules"] = RULES;
  return shownCase;
}

async function exceptionItem(rule: string) {
  const exceptions = await panel("Exceptions");
  const item = exceptions
    .getAllByRole("listitem")
    .find((li) =>
      li.querySelector(".exception-head")?.textContent.includes(rule),
    );
  if (!item) throw new Error(`No exception ${rule}`);
  return within(item);
}

it("dismisses an exception with a reason, and shows the refusal", async () => {
  const { routes, fetchMock } = showWithRules(awaiting);
  const item = await exceptionItem("rate.base_short");
  fireEvent.click(item.getByRole("button", { name: "Dismiss" }));
  const dismiss = item.getByRole("button", { name: "Dismiss" });
  fireEvent.click(dismiss);
  expect(sent(fetchMock, DISMISSAL)).toHaveLength(0);
  fireEvent.change(item.getByLabelText("Why dismiss it?"), {
    target: { value: "Paid in the next week's payroll" },
  });
  routes[DISMISSAL] = new Refusal(
    409,
    "Exception 7 isn't open, so it can't be dismissed",
  );
  fireEvent.click(dismiss);
  expect((await item.findByRole("alert")).textContent).toBe(
    "Exception 7 isn't open, so it can't be dismissed",
  );
  expect(sent(fetchMock, DISMISSAL)).toEqual([
    { reason: "Paid in the next week's payroll" },
  ]);
});

it("offers a fresh form once an exception is dismissed", async () => {
  const { routes, fetchMock } = showWithRules(awaiting);
  const item = await exceptionItem("rate.base_short");
  fireEvent.click(item.getByRole("button", { name: "Dismiss" }));
  fireEvent.change(item.getByLabelText("Why dismiss it?"), {
    target: { value: "Paid in the next week's payroll" },
  });
  const dismissed: Case = {
    ...awaiting,
    exceptions: [{ ...baseShort, status: "dismissed" }, unsigned],
  };
  routes[DISMISSAL] = dismissed;
  routes["GET /api/cases/PC-1201"] = dismissed;
  fireEvent.click(item.getByRole("button", { name: "Dismiss" }));
  const after = await exceptionItem("rate.base_short");
  expect(await after.findByRole("button", { name: "Restore" })).toBeDefined();
  expect(after.queryByLabelText("Why restore it?")).toBeNull();
  expect(sent(fetchMock, DISMISSAL)).toHaveLength(1);
});

it("restores a dismissed exception, and lists its overrides beside it", async () => {
  const dismissed: Case = {
    ...awaiting,
    open_exceptions: 1,
    exceptions: [{ ...baseShort, status: "dismissed" }, unsigned],
    overrides: [
      {
        override_id: 1,
        exception_id: 7,
        submission_no: 1,
        kind: "dismissed",
        reviewer_id: "HND-02",
        reviewer_name: "Marcus Oyelaran",
        reason: "Paid in the next week's payroll",
        created_at: "2026-11-23T14:05:00+00:00",
      },
    ],
  };
  const { routes, fetchMock } = showWithRules(dismissed);
  const item = await exceptionItem("rate.base_short");
  expect(item.getByRole("list", { name: "Overrides" }).textContent).toContain(
    "Dismissed by Marcus Oyelaran",
  );
  expect(item.getByText("Paid in the next week's payroll")).toBeDefined();
  fireEvent.click(item.getByRole("button", { name: "Restore" }));
  fireEvent.change(item.getByLabelText("Why restore it?"), {
    target: { value: "It wasn't paid after all" },
  });
  const restoration = "POST /api/cases/PC-1201/exceptions/7/restoration";
  routes[restoration] = awaiting;
  fireEvent.click(item.getByRole("button", { name: "Restore" }));
  await vi.waitFor(() => {
    expect(sent(fetchMock, restoration)).toEqual([
      { reason: "It wasn't paid after all" },
    ]);
  });
});

it("adds an exception, asking for the worker's line and a shortfall only where the rule needs them", async () => {
  const { routes, fetchMock } = showWithRules(awaiting);
  const form = await panel("Add an exception");
  await form.findByLabelText("Rule");
  expect(form.queryByLabelText("Worker and line")).toBeNull();
  expect(form.queryByLabelText("Shortfall, in dollars")).toBeNull();
  fireEvent.change(form.getByLabelText("Rule"), {
    target: { value: "rate.fringe_short" },
  });
  expect(form.getByLabelText("Worker and line")).toBeDefined();
  fireEvent.change(form.getByLabelText("Expected"), {
    target: { value: "$35.40/h" },
  });
  fireEvent.change(form.getByLabelText("Actual"), {
    target: { value: "$35.00/h" },
  });
  fireEvent.change(form.getByLabelText("Why the agent missed it"), {
    target: { value: "The fringe was short" },
  });
  const addIt = form.getByRole("button", { name: "Add the exception" });
  expect(addIt.getAttribute("aria-disabled")).toBe("true");
  fireEvent.change(form.getByLabelText("Shortfall, in dollars"), {
    target: { value: "19.00" },
  });
  expect(addIt.getAttribute("aria-disabled")).toBe("false");
  const adding = "POST /api/cases/PC-1201/exceptions";
  routes[adding] = new Refusal(
    422,
    "Line 1 of the latest submission isn't W-001's",
  );
  fireEvent.click(addIt);
  expect((await form.findByRole("alert")).textContent).toBe(
    "Line 1 of the latest submission isn't W-001's",
  );
  expect(sent(fetchMock, adding)).toEqual([
    {
      rule: "rate.fringe_short",
      worker_id: "W-001",
      line_no: 1,
      expected: "$35.40/h",
      actual: "$35.00/h",
      shortfall_cents: 1900,
      reason: "The fringe was short",
    },
  ]);
});

it("offers no overrides once a case is signed off", async () => {
  showWithRules({ ...awaiting, status: "accepted", open_exceptions: 0 });
  const item = await exceptionItem("rate.base_short");
  expect(item.queryByRole("button")).toBeNull();
  expect(screen.queryByRole("region", { name: "Add an exception" })).toBeNull();
});

it("reads a shortfall in dollars as whole cents", () => {
  expect(shortfallInCents("19")).toBe(1900);
  expect(shortfallInCents(" 0.32 ")).toBe(32);
  expect(shortfallInCents("0")).toBeUndefined();
  expect(shortfallInCents("1.234")).toBeUndefined();
  expect(shortfallInCents("-3")).toBeUndefined();
});

it("groups the exceptions by submission, the earlier ones superseded with no overrides", async () => {
  showWithRules({
    ...awaiting,
    latest_submission_no: 2,
    open_exceptions: 1,
    exceptions: [
      { ...baseShort, status: "superseded" },
      { ...unsigned, status: "dismissed" },
      { ...baseShort, exception_id: 9, submission_no: 2 },
    ],
  });
  const exceptions = await panel("Exceptions");
  const latest = within(
    exceptions.getByRole("region", { name: "Submission 2" }),
  );
  const earlier = within(
    exceptions.getByRole("region", { name: "Submission 1" }),
  );
  expect(
    latest.getByRole("heading", { name: "Submission 2, the latest" }),
  ).toBeDefined();
  expect(latest.getAllByRole("listitem")).toHaveLength(1);
  expect(latest.getByRole("button", { name: "Dismiss" })).toBeDefined();
  expect(
    earlier.getByRole("heading", { name: "Submission 1, before a correction" }),
  ).toBeDefined();
  expect(earlier.getByText("Superseded, submission 1")).toBeDefined();
  expect(earlier.getByText("Dismissed, submission 1")).toBeDefined();
  expect(earlier.queryByRole("button")).toBeNull();
});

it("shows the latest submission with no exceptions above the earlier ones", async () => {
  showWithRules({
    ...awaiting,
    latest_submission_no: 2,
    open_exceptions: 0,
    shortfall_cents: 0,
    exceptions: [{ ...baseShort, status: "superseded" }],
  });
  const exceptions = await panel("Exceptions");
  const groups = exceptions.getAllByRole("region");
  expect(groups.map((group) => group.getAttribute("aria-label"))).toEqual([
    "Submission 2",
    "Submission 1",
  ]);
  const latest = within(
    exceptions.getByRole("region", { name: "Submission 2" }),
  );
  expect(
    latest.getByRole("heading", { name: "Submission 2, the latest" }),
  ).toBeDefined();
  expect(latest.getByText("No exceptions.")).toBeDefined();
  expect(latest.queryByRole("listitem")).toBeNull();
  expect(
    within(exceptions.getByRole("region", { name: "Submission 1" })).getByText(
      "Superseded, submission 1",
    ),
  ).toBeDefined();
});
