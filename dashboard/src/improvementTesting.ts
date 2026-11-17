import type {
  Evaluation,
  Improvement,
  Measures,
  RecipeDetails,
  RoundView,
  WaitingProposal,
} from "./api";
import { renderAt, type Routes, stubApi } from "./testing";

// A round of the improver as the backend gives it to the Improvement page, for
// the page's tests.
export const ROUND_ID = "round-1";
export const PROPOSAL_ID = "proposal-2";
export const START = "POST /api/improvement/rounds";
export const APPROVAL = `POST /api/improvement/rounds/${ROUND_ID}/proposals/${PROPOSAL_ID}/approval`;
export const REJECTION = `POST /api/improvement/rounds/${ROUND_ID}/proposals/${PROPOSAL_ID}/rejection`;

export function measures(catchRate: number): Measures {
  return {
    catch_rate: catchRate,
    caught: Math.round(catchRate * 45),
    labels: 45,
    false_exceptions: 2,
    false_per_100: 2,
    shortfall_accuracy: 1,
    screening_caught: 1,
    screening_expected: 1,
    notice_score: null,
    notices_graded: 0,
    model_cost_per_case: 0.002,
    seconds_per_case: 20,
    run_seconds: 60,
  };
}

export const evaluation: Evaluation = {
  run_id: "run-3",
  number: 3,
  kind: "evaluation",
  agents: 25,
  version: 1,
  round_id: ROUND_ID,
  round_number: 1,
  model: "openai/gpt-6-luna",
  reasoning_effort: "low",
  status: "finished",
  stopped_because: null,
  started_at: "2026-10-04T09:00:00+00:00",
  finished_at: "2026-10-04T09:02:00+00:00",
  seconds: 120,
  model_cost: 0.05,
  judge_cost: 0.0002,
  evaluation_set: "held_out",
  size: 98,
  measures: measures(0.6),
};

export const change: WaitingProposal = {
  proposal_id: PROPOSAL_ID,
  kind: "change",
  reason: "Two weekend premiums were missed on the rates check",
  proposed_at: "2026-10-04T09:10:00+00:00",
  diff: {
    added: 1,
    removed: 0,
    hunks: [
      [
        { kind: "context", text: "# Working a case" },
        {
          kind: "added",
          text: "A weekend premium is paid at time and a half.",
        },
      ],
    ],
  },
  model_before: "openai/gpt-6-luna",
  reasoning_effort_before: "low",
  model_after: "google/gemini-3.5-flash-lite",
  reasoning_effort_after: "minimal",
  parameter_changes: [
    {
      name: "rounding_tolerance_cents",
      label: "Rounding tolerance",
      unit: "cents",
      before: 0,
      after: 2,
    },
  ],
  case_ids: ["PC-0311", "PC-1210"],
};

export const open: RoundView = {
  round_id: ROUND_ID,
  number: 1,
  status: "open",
  stage: "change_waiting",
  progress: null,
  started_by: "Dana Whitfield",
  started_at: "2026-10-04T09:00:00+00:00",
  finished_at: null,
  stopped_by: null,
  stopped_because: null,
  recipe: 1,
  settings: 1,
  spending_limit: 5,
  cost: 0.1234,
  version: null,
  model: null,
  reasoning_effort: null,
  reason: null,
  verdict: null,
  verdict_reason: null,
  held_out_before: null,
  held_out_after: null,
  reviews: [],
  waiting: change,
  evaluations: [evaluation],
};

export const empty: Improvement = {
  round: null,
  rounds: [],
  first_version: { number: 1, verdict: null, catch_rate: null },
  versions_tried: [],
  recipes: [
    {
      number: 1,
      current: true,
      reason: "The lab's recipe",
      proposed_by: "The compliance team",
      round_id: null,
      approved_by: null,
      approved_at: null,
      created_at: "2026-10-04T08:00:00+00:00",
      lines_added: 0,
      lines_removed: 0,
    },
  ],
};

export function improvement(
  round: RoundView | null,
  more: Partial<Improvement> = {},
) {
  return {
    ...empty,
    round,
    rounds: round ? [round] : [],
    ...more,
  };
}

// Shows the Improvement page with the backend answering from the routes given,
// which a test may change to play out what the next refresh brings.
export function showPage(page: Improvement, routes: Routes = {}) {
  routes["GET /api/improvement"] ??= page;
  const fetchMock = stubApi(routes);
  renderAt("/improvement");
  return fetchMock;
}

// Recipe 1 as its page shows it.
export const firstRecipe: RecipeDetails = {
  ...empty.recipes[0],
  recipe: "1. Read the results.\n",
  diff: null,
};

// A round that finished with its version kept.
export const finishedRound = {
  ...open,
  status: "finished",
  stage: null,
  waiting: null,
  version: 2,
  reason: "Two weekend premiums were missed",
  verdict: "kept",
  verdict_reason: "catch_rate improved",
  held_out_before: measures(0.6),
  held_out_after: measures(0.72),
} as const;
