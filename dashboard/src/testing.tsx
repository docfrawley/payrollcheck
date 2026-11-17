import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";
import { App } from "./App";
import type { Case, CaseSummary, Reviewer, Submission } from "./api";
import type { Settings, SettingsPage } from "./settings";

// Stands in for the backend: answers "METHOD /path" with the JSON given, or
// with the status and detail given as an error, and a 404 for anything else.
export type Routes = Record<string, unknown>;

export class Refusal {
  constructor(
    readonly status: number,
    readonly detail: unknown,
  ) {}
}

const dana: Reviewer = {
  reviewer_id: "HND-01",
  name: "Dana Whitfield",
  role: "compliance_manager",
  email: "dana.whitfield@payrollcheck.example",
};

export const marcus: Reviewer = {
  reviewer_id: "HND-02",
  name: "Marcus Oyelaran",
  role: "reviewer",
  email: "marcus.oyelaran@payrollcheck.example",
};

export const priya: Reviewer = {
  reviewer_id: "HND-03",
  name: "Priya Raman",
  role: "reviewer",
  email: "priya.raman@payrollcheck.example",
};

const startingSettings: Settings = {
  number: 1,
  objectives: {
    catch_rate: 0.92,
    false_per_100: 2.5,
    shortfall_accuracy: 1,
    notice_score: 0.8,
  },
  noise: {
    catch_rate: 0.05,
    false_per_100: 1,
    shortfall_accuracy: 0,
    notice_score: 0.1,
    cost_per_case: 0.15,
    seconds_per_case: 0.15,
  },
  tolerance: {
    catch_rate: 0.05,
    false_per_100: 1,
    shortfall_accuracy: 0,
    notice_score: 0.1,
    cost_per_case: 1,
    seconds_per_case: 0.25,
  },
  spending_limit: 5,
  agents: 25,
  business_date: "2026-11-23",
  changed_by: null,
  changed_at: "2026-10-04T09:00:00+00:00",
};

export const settings: SettingsPage = {
  current: startingSettings,
  changes: [startingSettings],
  models_allowed: [
    {
      model: "openai/gpt-6-luna",
      reasoning_efforts: ["none", "low", "medium"],
      input_price: 0.1,
      output_price: 0.5,
    },
  ],
};

// Every page is signed in as Dana unless the routes say otherwise.
export function stubApi(routes: Routes) {
  const signedIn: Routes = {
    "GET /api/me": dana,
    "GET /api/settings": settings,
    "GET /api/business-date": { business_date: "2026-11-23", real_date: false },
  };
  const fetchMock = vi.fn((path: string, init?: RequestInit) => {
    const answer = { ...signedIn, ...routes }[
      `${init?.method ?? "GET"} ${path}`
    ];
    if (answer === undefined)
      return Promise.resolve(
        Response.json({ detail: "Not found" }, { status: 404 }),
      );
    if (answer instanceof Refusal)
      return Promise.resolve(
        Response.json({ detail: answer.detail }, { status: answer.status }),
      );
    return Promise.resolve(Response.json(answer));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

// The bodies of the requests sent to "METHOD /path", in order.
export function sent(fetchMock: ReturnType<typeof stubApi>, route: string) {
  return fetchMock.mock.calls
    .filter(([path, init]) => `${init?.method ?? "GET"} ${path}` === route)
    .map(([, init]) =>
      typeof init?.body === "string"
        ? (JSON.parse(init.body) as unknown)
        : undefined,
    );
}

export function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

// Matches the element whose whole text is the text given, even when its words
// are split across elements, such as an amount set in mono.
export function wholeText(text: string) {
  return (_: string, element: Element | null) =>
    element?.textContent === text &&
    [...element.children].every((child) => child.textContent !== text);
}

// Finds the panel headed by the given heading, to look inside it.
export async function panel(heading: string) {
  return within(await screen.findByRole("region", { name: heading }));
}

export const summary: CaseSummary = {
  case_id: "PC-1201",
  project_id: "PRJ-01",
  project_name: "Lincoln School renovation",
  subcontractor_id: "SUB-01",
  subcontractor_name: "Garden State Electric LLC",
  week_ending: "2026-11-22",
  status: "received",
  screening_flag: false,
  agent_failed: false,
  open_exceptions: 0,
  shortfall_cents: 0,
};

export const submission: Submission = {
  submission_no: 1,
  uploaded_by: "HND-01",
  uploaded_at: "2026-11-23",
  received_on: "2026-11-23",
  file_name: "PC-1201-1.csv",
  payroll_no: 12,
  wage_payment_date: "2026-11-23",
  certification: {
    contractor_name: "Garden State Electric LLC",
    fein: "62-9917837",
    registration_no: "177511",
    project_id: "PRJ-01",
    payroll_no: 12,
    week_ending: "2026-11-22",
    wage_payment_date: "2026-11-23",
    signed_by: "Rosa Medina, Payroll Manager",
    signed_on: "2026-11-23",
    no_work_week: false,
    payroll_notes: "",
  },
  lines: [
    {
      worker_id: "W-001",
      worker_name: "Kim Dimitrov",
      classification: "Electrician Journeyman",
      apprentice_level: null,
      hours: ["0.00", "8.00", "8.00", "8.00", "8.00", "0.00", "0.00"],
      total_hours: "32.00",
      base_rate: 5885,
      fringe_rate: 3465,
      fringe_cash: 0,
      overtime_hours: "0.00",
      gross: 188320,
      deductions: 39547,
      net: 148773,
      line_notes: "",
    },
  ],
};

export const caseRecord: Case = {
  ...summary,
  screening_reason: null,
  latest_submission_no: 1,
  thread_id: null,
  attempts: 0,
  evaluation_id: null,
  copy_of: null,
  reviewed_by: null,
  reviewed_on: null,
  submissions: [submission],
  workers: [
    {
      worker_id: "W-001",
      name: "Kim Dimitrov",
      craft: "electrician",
      classification: "journeyman",
    },
  ],
  exceptions: [],
  candidates: [],
  checks_run: [],
  notice: null,
  overrides: [],
  sent_notices: [],
};
