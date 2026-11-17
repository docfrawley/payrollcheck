import type {
  Configuration,
  Project,
  ProjectInFull,
  Evaluation,
  Measures,
  NoticeGradeRecord,
  Run,
  RunCase,
  ScoredCase,
  ScoredEvaluation,
  VersionDetails,
  VersionSummary,
} from "./api";
import { summary } from "./testing";

// What the backend gives the pages, for the tests of more than one page: a
// dispatch at work, evaluations, and the payroll agent's versions.
export const waitingInRun: RunCase = {
  ...summary,
  case_id: "PC-1203",
  subcontractor_name: "Shore Line Concrete Inc.",
  started_at: null,
  seconds: 0,
  model_cost: 0,
};

export const runningDispatch: Run = {
  run_id: "run-4",
  number: 4,
  kind: "dispatch",
  agents: 3,
  version: 1,
  round_id: null,
  round_number: null,
  model: "openai/gpt-6-luna",
  reasoning_effort: "low",
  evaluation_set: null,
  status: "running",
  stopped_because: null,
  started_at: "2026-11-23T17:02:13+00:00",
  finished_at: null,
  seconds: null,
  summary: null,
  model_cost: 0.0125,
  other_projects: 0,
  cases: [
    {
      ...waitingInRun,
      case_id: "PC-1201",
      subcontractor_name: "Garden State Electric LLC",
      status: "awaiting_review",
      open_exceptions: 2,
      shortfall_cents: 6400,
      started_at: "2026-11-23T17:02:14+00:00",
      seconds: 41,
      model_cost: 0.0125,
    },
    {
      ...waitingInRun,
      case_id: "PC-1202",
      status: "in_progress",
      seconds: 12,
    },
    waitingInRun,
  ],
};

const measures: Measures = {
  catch_rate: 0.8,
  caught: 36,
  labels: 45,
  false_exceptions: 4,
  false_per_100: 1.9,
  shortfall_accuracy: 0.95,
  screening_caught: 1,
  screening_expected: 1,
  notice_score: 0.84,
  notices_graded: 30,
  model_cost_per_case: 0.0125,
  seconds_per_case: 40,
  run_seconds: 161,
};

export const finishedEvaluation: Evaluation = {
  run_id: "run-7",
  number: 7,
  kind: "evaluation",
  agents: 25,
  version: 1,
  round_id: null,
  round_number: null,
  model: "openai/gpt-6-luna",
  reasoning_effort: "low",
  evaluation_set: "development",
  status: "finished",
  stopped_because: null,
  started_at: "2026-11-23T17:02:13+00:00",
  finished_at: "2026-11-23T17:04:54+00:00",
  seconds: 161,
  model_cost: 0.3125,
  judge_cost: 0.0006,
  size: 207,
  measures,
};

export const scoredCopy: ScoredCase = {
  ...summary,
  case_id: "PC-0412-E9",
  started_at: "2026-11-23T17:02:14+00:00",
  seconds: 40,
  model_cost: 0.0125,
  status: "awaiting_review",
  open_exceptions: 1,
  shortfall_cents: 6400,
  copy_of: "PC-0412",
  labels: [
    {
      rule: "rate.base_short",
      worker_id: "W-001",
      line_no: 1,
      expected_shortfall_cents: 6400,
      result: "caught",
      shortfall_cents: 6400,
    },
  ],
  exceptions: [
    {
      exception_id: 31,
      rule: "rate.base_short",
      worker_id: "W-001",
      line_no: 1,
      expected: "$60.95/h",
      actual: "$59.35/h",
      shortfall_cents: 6400,
      matched: true,
    },
  ],
  notice: {
    result: "graded",
    score: 0.85,
    covers_every_exception: 0.9,
    amounts_match: 0.8,
    plain_language: 0.7,
    no_legal_interpretation: 1,
    cost: 0.00002,
  },
  screening_expected: false,
  screening_found: false,
  misses: 0,
  false_exceptions: 0,
};

const noGrade: NoticeGradeRecord = {
  result: "not_graded",
  score: null,
  covers_every_exception: null,
  amounts_match: null,
  plain_language: null,
  no_legal_interpretation: null,
  cost: 0,
};

export const scoredEvaluation: ScoredEvaluation = {
  ...finishedEvaluation,
  run_id: "run-9",
  number: 9,
  evaluation_set: "tiny",
  size: 3,
  success_criteria: null,
  cases: [
    scoredCopy,
    {
      ...scoredCopy,
      case_id: "PC-0507-E9",
      copy_of: "PC-0507",
      labels: [
        { ...scoredCopy.labels[0], result: "missed", shortfall_cents: null },
      ],
      exceptions: [
        {
          ...scoredCopy.exceptions[0],
          exception_id: 32,
          rule: "arithmetic.gross",
          matched: false,
        },
      ],
      misses: 1,
      false_exceptions: 1,
      notice: noGrade,
    },
    {
      ...scoredCopy,
      case_id: "PC-0809-E9",
      copy_of: "PC-0809",
      screening_flag: true,
      labels: [],
      exceptions: [],
      screening_expected: true,
      screening_found: true,
      notice: null,
    },
  ],
};

export const firstVersion: VersionSummary = {
  number: 1,
  status: "kept",
  model: "openai/gpt-6-luna",
  reasoning_effort: "low",
  model_before: null,
  reasoning_effort_before: null,
  based_on: null,
  lines_added: 0,
  lines_removed: 0,
  reason: "The payroll agent as the compliance team built it",
  proposed_by: "The compliance team",
  round_id: null,
  approved_by: null,
  approved_at: null,
  created_at: "2026-10-04T09:00:00+00:00",
  verdict: "kept",
  verdict_reason: "the first version",
  parameters: [
    {
      name: "rounding_tolerance_cents",
      label: "Rounding tolerance",
      unit: "cents",
      value: 0,
    },
  ],
  parameter_changes: [],
  motivating_cases: [],
  scores: { development: null, held_out: null },
};

export const secondVersion: VersionSummary = {
  ...firstVersion,
  number: 2,
  status: "current",
  model: "google/gemini-3.5-flash-lite",
  reasoning_effort: "minimal",
  model_before: "openai/gpt-6-luna",
  reasoning_effort_before: "low",
  based_on: 1,
  lines_added: 12,
  lines_removed: 3,
  reason: "Explain overtime on a weekend",
  proposed_by: "Round 1",
  approved_by: "Dana Whitfield",
  approved_at: "2026-10-05T14:05:00+00:00",
  parameters: [
    {
      name: "rounding_tolerance_cents",
      label: "Rounding tolerance",
      unit: "cents",
      value: 50,
    },
  ],
  parameter_changes: [
    {
      name: "rounding_tolerance_cents",
      label: "Rounding tolerance",
      unit: "cents",
      before: 0,
      after: 50,
    },
  ],
  motivating_cases: ["PC-0311", "PC-1210"],
};

export const configuration: Configuration = {
  current: 2,
  versions: [secondVersion, firstVersion],
};

export const versionDetails: VersionDetails = {
  ...secondVersion,
  instructions: "# Checking a payroll\n\n## What you work from",
  diff: {
    added: 1,
    removed: 1,
    hunks: [
      [
        { kind: "context", text: "Read the candidates." },
        { kind: "removed", text: "Dismiss a weekend premium." },
        { kind: "added", text: "Raise a weekend premium paid short." },
      ],
      [{ kind: "context", text: "Record the report." }],
    ],
  },
};

export const municipal: Project = {
  project_id: "PRJ-02",
  name: "Municipal building",
  county: "Middlesex",
  location: "New Brunswick",
  public_body: "City of New Brunswick",
  contract_no: "NB-2026-114",
  award_date: "2026-08-03",
};

export const project: ProjectInFull = {
  ...municipal,
  subcontractors: [
    {
      subcontractor_id: "SUB-01",
      legal_name: "Garden State Electric LLC",
      fein: "62-9917837",
      registration_no: "177511",
      first_week_ending: "2026-09-06",
      last_week_ending: "2026-11-22",
    },
    {
      subcontractor_id: "SUB-06",
      legal_name: "Delaware Valley Masonry LLC",
      fein: "98-5117616",
      registration_no: "941034",
      first_week_ending: "2026-09-13",
      last_week_ending: "2026-12-20",
    },
  ],
};
