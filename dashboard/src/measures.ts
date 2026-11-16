import type { Measures } from "./api";
import { duration, modelCost, percent } from "./format";

// A run that's running or stopped has no run time.
const NOT_FINISHED = "Not finished";
// Shortfall accuracy with no money label caught.
export const NONE_CAUGHT = "None caught";

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
  {
    label: "Shortfall accuracy",
    show: (m) =>
      m.shortfall_accuracy === null
        ? NONE_CAUGHT
        : percent(m.shortfall_accuracy),
  },
  {
    label: "Screening flags",
    show: (m) =>
      `${String(m.screening_caught)} of ${String(m.screening_expected)}`,
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
