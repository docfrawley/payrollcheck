import type { Measures } from "./api";
import { duration, modelCost } from "./format";

// A run that's running or stopped has no run time.
const NOT_FINISHED = "Not finished";
// A notice score with no notice graded, or a notice the judge couldn't grade.
export const NOT_GRADED = "Not graded";
// Shortfall accuracy with no money label caught.
export const NONE_CAUGHT = "None caught";

// The measures the rule weighs are shown to one place more than their objectives
// and rounded toward missing them: a measure better higher rounds down, false
// exceptions round up. So a score just short of its objective, such as a notice
// score of 0.7955 against 0.80, never shows as meeting it.
const PLACES = { share: 1, falsePer100: 2, noticeScore: 3 };
// Floating point can put an exact value a hair under or over itself.
const EPSILON = 1e-9;
const roundedDown = (value: number, places: number) =>
  (Math.floor(value * 10 ** places + EPSILON) / 10 ** places).toFixed(places);
const roundedUp = (value: number, places: number) =>
  (Math.ceil(value * 10 ** places - EPSILON) / 10 ** places).toFixed(places);

export const shareWeighed = (share: number) =>
  `${roundedDown(share * 100, PLACES.share)}%`;
export const shortfallAccuracy = (m: Measures) =>
  m.shortfall_accuracy === null
    ? NONE_CAUGHT
    : shareWeighed(m.shortfall_accuracy);
export const noticeScore = (m: Measures) =>
  m.notice_score === null
    ? NOT_GRADED
    : roundedDown(m.notice_score, PLACES.noticeScore);
export const perHundred = (falsePer100: number) =>
  roundedUp(falsePer100, PLACES.falsePer100);
export const falsePer100 = (m: Measures) => perHundred(m.false_per_100);

// The measures a round shows before and after its version, by the labels the
// Scoreboard gives them.
export const ROUND_MEASURES: {
  label: string;
  show: (measures: Measures) => string;
}[] = [
  { label: "Catch rate", show: (m) => shareWeighed(m.catch_rate) },
  { label: "False per 100", show: falsePer100 },
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
      `${shareWeighed(m.catch_rate)} (${String(m.caught)} of ${String(m.labels)})`,
  },
  {
    label: "False exceptions",
    show: (m) => `${String(m.false_exceptions)} (${falsePer100(m)} per 100)`,
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
        ? noticeScore(m)
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
