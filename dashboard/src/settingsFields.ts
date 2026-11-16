import { MOST_AGENTS } from "./components/AgentsChoice";
import type { Settings, SettingsValues } from "./settings";
import { money } from "./format";

// How the Settings page shows each setting: its group, its label, its unit and
// its limits. The catch rate, shortfall accuracy and the fractions of cost and
// time are kept from 0 to 1 and typed as percentages; the notice score is kept
// and typed from 0 to 1; false exceptions are a number per 100 payrolls.
export type Unit = "dollars" | "percent" | "score" | "per100" | "agents";

export interface SettingField {
  id: string;
  group: SettingGroup;
  // Its label in its group, and its name on its own, in a list of changes.
  label: string;
  name: string;
  unit: Unit;
  // The most a reviewer may type, in the unit shown, when there's a most.
  max?: number;
  get: (values: SettingsValues) => number;
  set: (values: SettingsValues, value: number) => SettingsValues;
}

// Each unit as a reviewer types it: what goes before or after the number, the
// smallest number allowed and the step, and how it's rounded once typed.
export const UNITS: Record<
  Unit,
  { prefix?: string; suffix?: string; min: number; step: number }
> = {
  dollars: { prefix: "$", min: 0.01, step: 0.01 },
  percent: { suffix: "%", min: 0, step: 0.1 },
  score: { min: 0, step: 0.01 },
  per100: { suffix: "per 100 payrolls", min: 0, step: 0.1 },
  agents: { min: 1, step: 1 },
};

export const settingGroups = [
  "objectives",
  "noise",
  "tolerance",
  "spending",
  "evaluations",
] as const;
export type SettingGroup = (typeof settingGroups)[number];

export const GROUPS: Record<SettingGroup, { title: string; lead: string }> = {
  objectives: {
    title: "Objectives on the held-out set",
    lead: "What a new version of the payroll agent must meet to be kept: the lowest catch rate, shortfall accuracy and notice score, and the most false exceptions.",
  },
  noise: {
    title: "Noise",
    lead: "The smallest improvement that counts. The catch rate and shortfall accuracy are in points, false exceptions per 100 payrolls and the notice score in their own units; cost and time are a share of the old value.",
  },
  tolerance: {
    title: "Tolerance",
    lead: "How much a measure can get worse when another improves.",
  },
  spending: {
    title: "Spending",
    lead: "The most one round of the improver can spend, including its evaluations.",
  },
  evaluations: {
    title: "The improver's evaluations",
    lead: "How many payroll agents work at once in a round's evaluations.",
  },
};

type Measure = keyof SettingsValues["noise"];
type Objective = keyof SettingsValues["objectives"];

// The measures the rule weighs, each with its unit and, for the four with an
// objective, whether a version must score at least or at most it.
const MEASURES: {
  measure: Measure;
  label: string;
  unit: Unit;
  objective?: { name: Objective; direction: "at least" | "at most" };
}[] = [
  {
    measure: "catch_rate",
    label: "Catch rate",
    unit: "percent",
    objective: { name: "catch_rate", direction: "at least" },
  },
  {
    measure: "false_per_100",
    label: "False exceptions",
    unit: "per100",
    objective: { name: "false_per_100", direction: "at most" },
  },
  {
    measure: "shortfall_accuracy",
    label: "Shortfall accuracy",
    unit: "percent",
    objective: { name: "shortfall_accuracy", direction: "at least" },
  },
  {
    measure: "notice_score",
    label: "Notice score",
    unit: "score",
    objective: { name: "notice_score", direction: "at least" },
  },
  { measure: "cost_per_case", label: "Model cost per case", unit: "percent" },
  { measure: "seconds_per_case", label: "Time per case", unit: "percent" },
];

// The most a share or a score can be, as typed.
const MOST: Partial<Record<Unit, number>> = { percent: 100, score: 1 };

function objectiveFields(): SettingField[] {
  return MEASURES.flatMap(({ label, unit, objective }) =>
    objective
      ? [
          {
            id: `objectives.${objective.name}`,
            group: "objectives" as const,
            label: `${label} ${objective.direction}`,
            name: `${label} objective`,
            unit,
            max: MOST[unit],
            get: (values: SettingsValues) => values.objectives[objective.name],
            set: (values: SettingsValues, value: number) => ({
              ...values,
              objectives: { ...values.objectives, [objective.name]: value },
            }),
          },
        ]
      : [],
  );
}

function measureFields(group: "noise" | "tolerance"): SettingField[] {
  return MEASURES.map(({ measure, label, unit }) => ({
    id: `${group}.${measure}`,
    group,
    label,
    name: `${GROUPS[group].title} on ${label.toLowerCase()}`,
    unit,
    get: (values) => values[group][measure],
    set: (values, value) => ({
      ...values,
      [group]: { ...values[group], [measure]: value },
    }),
  }));
}

export const SETTING_FIELDS: SettingField[] = [
  ...objectiveFields(),
  ...measureFields("noise"),
  ...measureFields("tolerance"),
  {
    id: "spending_limit",
    group: "spending",
    label: "Spending limit for each round",
    name: "Spending limit for each round",
    unit: "dollars",
    get: (values) => values.spending_limit,
    set: (values, value) => ({ ...values, spending_limit: value }),
  },
  {
    id: "agents",
    group: "evaluations",
    label: "Payroll agents at once",
    name: "Payroll agents at once in the improver's evaluations",
    unit: "agents",
    max: MOST_AGENTS,
    get: (values) => values.agents,
    set: (values, value) => ({ ...values, agents: value }),
  },
];

// A setting as a reviewer types it: dollars to the cent, shares as percentages
// to a tenth, a score to a hundredth and false exceptions to a tenth.
export function toInput(unit: Unit, value: number): string {
  if (unit === "dollars" || unit === "score") return value.toFixed(2);
  if (unit === "percent") return String(Math.round(value * 1000) / 10);
  if (unit === "per100") return String(Math.round(value * 10) / 10);
  return String(value);
}

// A setting as typed, rounded to what the page shows.
export function fromInput(unit: Unit, input: string): number {
  const value = Number(input);
  if (unit === "dollars" || unit === "score")
    return Math.round(value * 100) / 100;
  if (unit === "percent") return Math.round(value * 10) / 1000;
  if (unit === "per100") return Math.round(value * 10) / 10;
  return Math.round(value);
}

// A setting as the page shows it, with its unit.
function shown(unit: Unit, value: number): string {
  if (unit === "dollars") return money(value);
  if (unit === "percent") return `${toInput(unit, value)}%`;
  if (unit === "per100")
    return `${toInput(unit, value)} ${UNITS.per100.suffix ?? ""}`;
  return toInput(unit, value);
}

export type Inputs = Record<string, string>;

export function inputsOf(values: SettingsValues): Inputs {
  return Object.fromEntries(
    SETTING_FIELDS.map((field) => [
      field.id,
      toInput(field.unit, field.get(values)),
    ]),
  );
}

// The settings alone, without who changed them and when. The business date
// isn't shown and is carried through a save unchanged.
function valuesOnly(settings: Settings): SettingsValues {
  return {
    objectives: settings.objectives,
    noise: settings.noise,
    tolerance: settings.tolerance,
    spending_limit: settings.spending_limit,
    agents: settings.agents,
    business_date: settings.business_date,
  };
}

// The settings as typed: a setting whose input wasn't touched keeps its value
// exactly, so saving never changes what a reviewer didn't.
export function valuesOf(current: Settings, inputs: Inputs): SettingsValues {
  return SETTING_FIELDS.reduce((values, field) => {
    const input = inputs[field.id] ?? "";
    return input === toInput(field.unit, field.get(current))
      ? values
      : field.set(values, fromInput(field.unit, input));
  }, valuesOnly(current));
}

// Each setting that differs between two sets of values, from the old to the
// new, as the page shows them.
export function changesBetween(
  before: SettingsValues,
  after: SettingsValues,
): string[] {
  return SETTING_FIELDS.filter(
    (field) => field.get(before) !== field.get(after),
  ).map(
    (field) =>
      `${field.name}: ${shown(field.unit, field.get(before))} to ${shown(field.unit, field.get(after))}`,
  );
}
