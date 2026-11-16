import type { Measures } from "./api";
import { duration, modelCost, percent } from "./format";

// A run that's running or stopped has no run time.
const NOT_FINISHED = "Not finished";
// A notice score with no notice graded, or a notice the judge couldn't grade.
export const NOT_GRADED = "Not graded";
// Shortfall accuracy with no money label caught.
export const NONE_CAUGHT = "None caught";

// How a measure the rule weighs is shown, on the Scoreboard and on a round.
export const shortfallAccuracy = (m: Measures) =>
  m.shortfall_accuracy === null ? NONE_CAUGHT : percent(m.shortfall_accuracy);
export const noticeScore = (m: Measures) =>
  m.notice_score === null ? NOT_GRADED : m.notice_score.toFixed(2);

// The measures a round shows before and after its version, by the labels the
// Scoreboard gives them.
export const ROUND_MEASURES: {
  label: string;
  show: (measures: Measures) => string;
}[] = [
  { label: "Catch rate", show: (m) => percent(m.catch_rate) },
  { label: "False per 100", show: (m) => m.false_per_100.toFixed(1) },
  { label: "Shortfall accuracy", show: shortfallAccuracy },
  { label: "Notice score", show: noticeScore },
];

// The scoreboard's measures, in order, each with how it's shown.
export const MEASURES: {
  label: string;
  show: (measures: Measures) => string;
}[] = [
  {
    label: "Catch rate",
    show: (m) =>
      `${percent(m.catch_rate)} (${String(m.caught)} of ${String(m.labels)})`,
  },
  {
    label: "False exceptions",
    show: (m) =>
      `${String(m.false_exceptions)} (${m.false_per_100.toFixed(1)} per 100)`,
  },
  { label: "Shortfall accuracy", show: shortfallAccuracy },
  {
    label: "Screening flags",
    show: (m) =>
      `${String(m.screening_caught)} of ${String(m.screening_expected)}`,
  },
  {
    label: "Notice score",
    show: (m) =>
      m.notice_score === null
        ? NOT_GRADED
        : `${noticeScore(m)} (${String(m.notices_graded)} graded)`,
  },
  {
    label: "Model cost per case",
    show: (m) => modelCost(m.model_cost_per_case),
  },
  { label: "Time per case", show: (m) => duration(m.seconds_per_case) },
  {
    label: "Run time",
    show: (m) =>
      m.run_seconds === null ? NOT_FINISHED : duration(m.run_seconds),
  },
];
