import type {
  EvaluationSet,
  RoundStage,
  RoundStatus,
  RoundSummary,
  ExceptionStatus,
  RunStatus,
  Severity,
  Status,
  Verdict,
  VersionStatus,
} from "./api";
import type { Source } from "./sources";

const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

const day = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});

const dayAndClock = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

const clock = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
});

// Model costs are often under a cent.
const modelDollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});

// A context file's source as a reviewer reads it, such as "Compliance manual,
// certified payrolls, owned by Compliance manager, reviewed Sep 1, 2026". An owner that
// is a role, a head of something, is "the" head.
export function sourceOf(source: Source): string {
  const owner = source.owner.startsWith("Head of ")
    ? `the ${source.owner}`
    : source.owner;
  return `${source.system}, owned by ${owner}, reviewed ${date(source.reviewed)}`;
}

export function money(amount: number): string {
  return dollars.format(amount);
}

// An amount the app keeps in cents, in dollars: 128460 is $1,284.60.
export function cents(amount: number): string {
  return dollars.format(amount / 100);
}

// A share, such as 0.8, as a whole percentage: 80%.
export function percent(share: number): string {
  return `${String(Math.round(share * 100))}%`;
}

export function modelCost(amount: number): string {
  return modelDollars.format(amount);
}

// A length of time, such as 41 s or 2 min 41 s.
export function duration(seconds: number): string {
  const whole = Math.round(seconds);
  const minutes = Math.floor(whole / 60);
  const rest = `${String(whole % 60)} s`;
  if (minutes === 0) return rest;
  return whole % 60 === 0
    ? `${String(minutes)} min`
    : `${String(minutes)} min ${rest}`;
}

// A short length of time, to a tenth of a second under ten seconds, such as
// 0.4 s, and as duration gives it from there.
export function briefly(seconds: number): string {
  return seconds < 10 ? `${seconds.toFixed(1)} s` : duration(seconds);
}

export function date(isoDate: string): string {
  return day.format(new Date(`${isoDate}T00:00:00Z`));
}

export function time(isoTime: string): string {
  return clock.format(new Date(isoTime));
}

export function dateTime(isoTime: string): string {
  return dayAndClock.format(new Date(isoTime));
}

export function agentsAtOnce(agents: number): string {
  return `${String(agents)} payroll ${agents === 1 ? "agent" : "agents"} at once`;
}

// A reviewer's initials, from their first and last names, such as DW for Dana
// Whitfield.
export function initials(name: string): string {
  const [first = "", ...rest] = name.split(" ");
  const last = rest.at(-1) ?? "";
  return (first.charAt(0) + last.charAt(0)).toUpperCase();
}

export function label(code: string): string {
  const words = code.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export const statusLabels: Record<Status, string> = {
  received: "Received",
  in_progress: "In progress",
  awaiting_review: "Awaiting review",
  accepted: "Accepted",
  returned_to_sub: "Returned to sub",
};

export const exceptionStatusLabels: Record<ExceptionStatus, string> = {
  open: "Open",
  dismissed: "Dismissed",
  superseded: "Superseded",
};

export const severityLabels: Record<Severity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const runLabels: Record<RunStatus, string> = {
  running: "Running",
  finished: "Finished",
  stopped: "Stopped",
};

export const versionLabels: Record<VersionStatus, string> = {
  current: "Current",
  kept: "Kept",
  rolled_back: "Rolled back",
  under_test: "Under test",
};

// Who approved a version or a recipe that needed no approval.
export const NO_APPROVAL_NEEDED = "Nobody needed to";

export const roundLabels: Record<RoundStatus, string> = {
  open: "Open",
  finished: "Finished",
  stopped: "Stopped",
};

// A verdict keeps or rolls back a version, so it reads as the version's status.
export const verdictLabels: Record<Verdict, string> = {
  kept: versionLabels.kept,
  rolled_back: versionLabels.rolled_back,
};

// Each stage of a round in order, as the page names it in the round's progress.
export const stageLabels: Record<RoundStage, string> = {
  first_evaluations: "First evaluations",
  improving: "The improver is working",
  change_waiting: "A change is waiting for approval",
  evaluating: "Evaluations",
  verdict: "Verdict",
  recipe_waiting: "A new recipe is waiting for approval",
};
export const roundStages = Object.keys(stageLabels) as RoundStage[];

// A verdict's reason in words: the rule names measures such as cost_per_case.
export function inWords(reason: string | null): string {
  return (reason ?? "").replaceAll("_", " ");
}

// Why a run stopped, as a sentence: "Stopped: The agent stopped answering." A
// reason that already ends with a stop, as an error's message may, keeps it.
export function stoppedBecause(reason: string): string {
  return `Stopped: ${reason}${/[.!?]$/.test(reason) ? "" : "."}`;
}

// Where an open round has got to, such as "First evaluations, 2 of 3", or
// "Kept: catch rate improved" once its verdict is in.
export function whereRoundIs(round: RoundSummary): string {
  if (round.stage === null) return "";
  if (round.stage === "verdict" && round.verdict)
    return `${verdictLabels[round.verdict]}: ${inWords(round.verdict_reason)}`;
  const name = stageLabels[round.stage];
  return round.progress ? `${name}, ${round.progress}` : name;
}

export const evaluationSetLabels: Record<EvaluationSet, string> = {
  development: "Development set",
  held_out: "Held-out set",
  tiny: "Tiny set",
};

export function evaluationSetName(set: EvaluationSet, size: number): string {
  return `${evaluationSetLabels[set]}, ${String(size)} ${size === 1 ? "payroll" : "payrolls"}`;
}
