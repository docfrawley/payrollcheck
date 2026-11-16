// A case as the backend gives it to the case page, with its exceptions, its
// notice and the agent's steps, for the page's tests.

import type { Case, ExceptionRecord, Step } from "./api";
import type { Source } from "./sources";
import { caseRecord, panel, renderAt, type Routes, stubApi } from "./testing";

export const checkedAt = "2026-11-23T14:06:16+00:00";

// A step of the agent's work, from no context file unless it's a lookup.
export const step = (
  step_id: number,
  kind: Step["kind"],
  content: string,
  sources: Source[] = [],
): Step => ({
  step_id,
  thread_id: "t-1",
  kind,
  content,
  sources,
  created_at: checkedAt,
});

export function showCase(shown: Case, stepsShown: Step[] = []) {
  const routes: Routes = {
    "GET /api/cases/PC-1201": shown,
    "GET /api/cases/PC-1201/steps": stepsShown,
  };
  const fetchMock = stubApi(routes);
  renderAt("/cases/PC-1201");
  return { routes, fetchMock };
}

export const reviewPanel = () => panel("Review");

export const baseShort: ExceptionRecord = {
  exception_id: 7,
  submission_no: 1,
  rule: "rate.base_short",
  severity: "high",
  worker_id: "W-001",
  line_no: 1,
  expected: "$60.85 an hour",
  actual: "$58.85 an hour",
  shortfall_cents: 6400,
  citation: "RD-MIDDLESEX-2026 row 3, Electrician Journeyman",
  raised_by: "PayrollCheck Agent, version 1",
  candidate_id: 3,
  status: "open",
};

export const unsigned: ExceptionRecord = {
  ...baseShort,
  exception_id: 8,
  rule: "form.unsigned",
  worker_id: null,
  line_no: null,
  expected: "",
  actual: "",
  shortfall_cents: null,
  citation: "MW-562 payroll certification",
  candidate_id: 4,
};

// A case the agent checked, with two open exceptions and its draft notice.
export const awaiting: Case = {
  ...caseRecord,
  status: "awaiting_review",
  thread_id: "t-1",
  attempts: 1,
  open_exceptions: 2,
  shortfall_cents: 6400,
  exceptions: [baseShort, unsigned],
  checks_run: ["check_form", "check_rates"],
  notice: {
    submission_no: 1,
    draft: "Please correct Kim Dimitrov's base rate and sign the payroll.",
    drafted_by: "PayrollCheck Agent, version 1",
    drafted_at: checkedAt,
  },
};

const cleanNotice = {
  submission_no: 1,
  draft: "",
  drafted_by: "PayrollCheck Agent, version 1",
  drafted_at: checkedAt,
};

// A case the agent checked and found clean.
export const clean: Case = {
  ...awaiting,
  open_exceptions: 0,
  shortfall_cents: 0,
  exceptions: [],
  notice: cleanNotice,
};
