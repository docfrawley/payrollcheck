import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Candidate, Case } from "./api";
import type { ExceptionRecord } from "./exceptions";
import { awaiting, baseShort, showCase, unsigned } from "./caseTesting";
import { caseRecord, panel } from "./testing";

// The payroll agent's judgment calls on the case page, beside the check
// tools' findings.

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const rateFinding: Candidate = {
  candidate_id: 3,
  check: "check_rates",
  rule: "rate.base_short",
  severity: "high",
  submission_no: 1,
  worker_id: "W-001",
  line_no: 1,
  expected: baseShort.expected,
  actual: baseShort.actual,
  shortfall_cents: 6400,
  citation: baseShort.citation,
  dismissed_because: null,
};

const classificationFinding: Candidate = {
  ...rateFinding,
  candidate_id: 5,
  check: "check_classification",
  rule: "classification.changed",
  severity: "medium",
  shortfall_cents: null,
  citation: "Last week's payroll",
  dismissed_because: "The line note explains the move to foreman this week.",
};

const mismatch: ExceptionRecord = {
  ...unsigned,
  exception_id: 9,
  rule: "form.project_mismatch",
  source: "agent",
  candidate_id: null,
  citation: "Our project and subcontractor records",
};

// A case the agent judged: the rates finding raised, the classification
// finding dismissed with its reason, and an exception of its own.
const judged: Case = {
  ...awaiting,
  checks_run: ["check_form", "check_rates", "check_classification"],
  candidates: [rateFinding, classificationFinding],
  exceptions: [baseShort, mismatch],
};

it("shows each check that ran with its findings, and the agent's call on each", async () => {
  showCase(judged);
  const checks = await panel("Checks and judgment");
  const run = within(checks.getByRole("list", { name: "Checks run" }));
  const [form, rates, classification] = [
    "check_form",
    "check_rates",
    "check_classification",
  ].map((check) => run.getByRole("listitem", { name: check }));
  expect(form.textContent).toBe("check_form Nothing found");
  expect(rates.textContent).toContain(
    "rate.base_short W-001, line 1, $64.00 short",
  );
  expect(within(rates).getByText("Raised as an exception")).toBeDefined();
  expect(classification.textContent).toContain("classification.changed");
  expect(
    within(classification).getByText(
      "Dismissed: The line note explains the move to foreman this week.",
    ),
  ).toBeDefined();
});

it("marks an exception the agent raised with no check behind it as its own", async () => {
  showCase(judged);
  const checks = await panel("Checks and judgment");
  expect(checks.getByText("The agent's own judgment")).toBeDefined();
  expect(
    checks.getByText(
      "Raised with no check behind it: Our project and subcontractor records",
    ),
  ).toBeDefined();
  const list = await panel("Exceptions");
  const [rate, own] = list.getAllByRole("listitem");
  expect(within(own).getByText("Agent's own judgment").className).toBe(
    "chip judgment",
  );
  expect(within(rate).queryByText("Agent's own judgment")).toBeNull();
});

it("says when a finding isn't judged yet, or its exception is no longer open", async () => {
  showCase({
    ...judged,
    candidates: [
      rateFinding,
      { ...classificationFinding, dismissed_because: null },
    ],
    exceptions: [{ ...baseShort, status: "dismissed" }],
  });
  const checks = await panel("Checks and judgment");
  expect(
    checks.getByText("Raised as an exception, now dismissed"),
  ).toBeDefined();
  expect(checks.getByText("Not judged yet")).toBeDefined();
  expect(checks.queryByText("The agent's own judgment")).toBeNull();
});

it("shows no checks on a case no check ran on, and none of a reviewer's exceptions as the agent's", async () => {
  showCase({
    ...caseRecord,
    status: "returned_to_sub",
    exceptions: [
      {
        ...mismatch,
        expected: "",
        actual: "",
        raised_by: "Dana Whitfield",
        source: "reviewer",
      },
    ],
  });
  await panel("Exceptions");
  expect(
    screen.queryByRole("region", { name: "Checks and judgment" }),
  ).toBeNull();
  expect(screen.queryByText("Agent's own judgment")).toBeNull();
});

it("leaves out an own-judgment exception from an earlier submission", async () => {
  showCase({
    ...judged,
    latest_submission_no: 2,
    exceptions: [
      { ...baseShort, submission_no: 2 },
      { ...mismatch, submission_no: 1, status: "superseded" },
    ],
  });
  const checks = await panel("Checks and judgment");
  expect(checks.queryByText("The agent's own judgment")).toBeNull();
  expect(
    (await panel("Exceptions")).getByText("Agent's own judgment"),
  ).toBeDefined();
});

it("shows the agent's own judgment alone when no check has run", async () => {
  showCase({ ...awaiting, checks_run: [], exceptions: [mismatch] });
  const checks = await panel("Checks and judgment");
  expect(checks.queryByRole("list", { name: "Checks run" })).toBeNull();
  expect(checks.getByText("The agent's own judgment")).toBeDefined();
});
