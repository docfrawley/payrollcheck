import { freshAccessToken } from "./auth";
import { post, request, send } from "./connection";
import type { Conversation, ConversationSummary } from "./conversation";
import type { Source } from "./sources";

// Where a case stands, in the order the queue shows them.
export const statuses = [
  "received",
  "in_progress",
  "awaiting_review",
  "accepted",
  "returned_to_sub",
] as const;
export type Status = (typeof statuses)[number];
export type Severity = "high" | "medium" | "low";
export type ExceptionStatus = "open" | "dismissed" | "superseded";
export type StepKind =
  | "screening"
  // A check tool's findings, which the app records itself.
  | "check"
  | "tool_call"
  | "tool_result"
  | "message"
  | "lookup"
  | "refusal"
  | "error";

export interface CaseSummary {
  case_id: string;
  project_id: string;
  project_name: string;
  subcontractor_id: string;
  subcontractor_name: string;
  week_ending: string;
  status: Status;
  screening_flag: boolean;
  agent_failed: boolean;
  open_exceptions: number;
  // Of the open exceptions, in cents.
  shortfall_cents: number;
}

// The MW-562 payroll certification, as the app keeps it.
export interface PayrollCertification {
  contractor_name: string;
  fein: string;
  registration_no: string;
  project_id: string;
  payroll_no: number;
  week_ending: string;
  wage_payment_date: string;
  signed_by: string;
  signed_on: string | null;
  no_work_week: boolean;
  payroll_notes: string;
}

// One worker's week on a payroll: hours from Monday as exact decimals, money
// in cents.
export interface PayrollLine {
  worker_id: string;
  worker_name: string;
  classification: string;
  apprentice_level: number | null;
  hours: string[];
  total_hours: string;
  base_rate: number;
  fringe_rate: number;
  fringe_cash: number;
  overtime_hours: string;
  gross: number;
  deductions: number;
  net: number;
  line_notes: string;
}

// One upload of a payroll into a case, never changed.
export interface Submission {
  submission_no: number;
  uploaded_by: string;
  uploaded_at: string;
  received_on: string;
  file_name: string;
  payroll_no: number;
  wage_payment_date: string;
  certification: PayrollCertification;
  lines: PayrollLine[];
}

export interface Worker {
  worker_id: string;
  name: string;
  // The established craft.
  craft: string;
  classification: string;
}

// One rule breach found in a submission.
export interface ExceptionRecord {
  exception_id: number;
  submission_no: number;
  rule: string;
  severity: Severity;
  worker_id: string | null;
  line_no: number | null;
  expected: string;
  actual: string;
  shortfall_cents: number | null;
  citation: string;
  raised_by: string;
  // The check's finding it raises.
  candidate_id: number | null;
  status: ExceptionStatus;
}

// A check tool's finding on the current attempt.
export interface Candidate {
  candidate_id: number;
  check: string;
  rule: string;
  severity: Severity;
  submission_no: number;
  worker_id: string | null;
  line_no: number | null;
  expected: string;
  actual: string;
  shortfall_cents: number | null;
  citation: string;
  dismissed_because: string | null;
}

export interface Notice {
  submission_no: number;
  draft: string;
  drafted_by: string;
  drafted_at: string;
}

export interface Case extends CaseSummary {
  screening_reason: string | null;
  latest_submission_no: number;
  thread_id: string | null;
  attempts: number;
  // Set on an evaluation's copy of a case.
  evaluation_id: string | null;
  copy_of: string | null;
  reviewed_by: string | null;
  reviewed_on: string | null;
  // Oldest first.
  submissions: Submission[];
  // Each worker on the latest submission.
  workers: Worker[];
  exceptions: ExceptionRecord[];
  // The current attempt's.
  candidates: Candidate[];
  checks_run: string[];
  // The latest submission's draft.
  notice: Notice | null;
}

export interface Project {
  project_id: string;
  name: string;
  county: string;
  location: string;
  public_body: string;
  contract_no: string;
  award_date: string;
}

// A subcontractor on a project, with its engagement window.
export interface Engagement {
  subcontractor_id: string;
  legal_name: string;
  fein: string;
  registration_no: string;
  first_week_ending: string;
  last_week_ending: string;
}

export interface ProjectInFull extends Project {
  subcontractors: Engagement[];
}

export interface Reviewer {
  reviewer_id: string;
  name: string;
  role: string;
  email: string;
  can_approve_over_limit: boolean;
}

export interface Step {
  step_id: number;
  thread_id: string;
  kind: StepKind;
  content: string;
  // The context files a lookup came from, and none for any other step.
  sources: Source[];
  created_at: string;
}

export type RunStatus = "running" | "finished" | "stopped";
export type RunKind = "dispatch" | "evaluation";
export const evaluationSets = ["development", "held_out", "tiny"] as const;
export type EvaluationSet = (typeof evaluationSets)[number];

// The cases a dispatch worked, as they stand: Awaiting review with exceptions
// or clean, flagged by the screening, failed by the agent, or unfinished.
export interface DispatchSummary {
  with_exceptions: string[];
  clean: string[];
  flagged: string[];
  agent_failed: string[];
  // In progress or back in the queue, for the next dispatch.
  unfinished: string[];
}

// A case's line in the queue, with its cost and time in a run.
export interface RunCase extends CaseSummary {
  started_at: string | null;
  seconds: number;
  model_cost: number;
}

export interface RunDetails {
  run_id: string;
  number: number;
  kind: RunKind;
  agents: number;
  version: number;
  round_id: string | null;
  // The round that ran it, if any.
  round_number: number | null;
  model: string;
  reasoning_effort: string;
  status: RunStatus;
  // Why it stopped, for a run that stopped.
  stopped_because: string | null;
  started_at: string;
  finished_at: string | null;
  seconds: number | null;
  model_cost: number;
}

export interface Run extends RunDetails {
  evaluation_set: EvaluationSet | null;
  summary: DispatchSummary | null;
  cases: RunCase[];
}

export interface Measures {
  // Exception labels caught, of all.
  catch_rate: number;
  caught: number;
  labels: number;
  false_exceptions: number;
  // False exceptions per 100 payrolls.
  false_per_100: number;
  // Caught money labels with the right shortfall, or null with none caught.
  shortfall_accuracy: number | null;
  screening_caught: number;
  screening_expected: number;
  model_cost_per_case: number;
  seconds_per_case: number;
  run_seconds: number | null;
}

// A label beside what the agent raised: caught, missed, or caught with the
// wrong shortfall.
export interface LabelMatch {
  rule: string;
  worker_id: string | null;
  line_no: number | null;
  expected_shortfall_cents: number | null;
  result: "caught" | "missed" | "shortfall_wrong";
  // The exception's, once caught.
  shortfall_cents: number | null;
}

export interface ExceptionMatch {
  exception_id: number;
  rule: string;
  worker_id: string | null;
  line_no: number | null;
  shortfall_cents: number | null;
  matched: boolean;
}

// An evaluation's copy of a case beside its labels.
export interface ScoredCase extends RunCase {
  copy_of: string;
  labels: LabelMatch[];
  exceptions: ExceptionMatch[];
  screening_expected: boolean;
  screening_found: boolean;
  misses: number;
  false_exceptions: number;
}

export interface Evaluation extends RunDetails {
  evaluation_set: EvaluationSet;
  size: number;
  measures: Measures;
}

export interface ScoredEvaluation extends Evaluation {
  cases: ScoredCase[];
}

export interface Accepted {
  status: "accepted";
}

export type VersionStatus = "current" | "kept" | "rolled_back" | "under_test";
export type Verdict = "kept" | "rolled_back";
export type DiffLineKind = "context" | "added" | "removed";

export interface DiffLine {
  kind: DiffLineKind;
  text: string;
}

// The lines that differ between two texts, in hunks with their context.
export interface Diff {
  added: number;
  removed: number;
  hunks: DiffLine[][];
}

// A version's scores on each set, from the evaluations rounds ran on it.
export interface VersionScores {
  development: Measures | null;
  held_out: Measures | null;
}

export interface VersionSummary {
  number: number;
  status: VersionStatus;
  model: string;
  reasoning_effort: string;
  // The version this one changes, and its model, or null for version 1.
  based_on: number | null;
  model_before: string | null;
  reasoning_effort_before: string | null;
  lines_added: number;
  lines_removed: number;
  reason: string;
  proposed_by: string;
  round_id: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  verdict: Verdict | null;
  verdict_reason: string | null;
  // The check tools' tunable parameters, such as the rounding tolerance.
  parameters: Record<string, unknown>;
  scores: VersionScores;
}

export interface VersionDetails extends VersionSummary {
  instructions: string;
  diff: Diff | null;
}

export interface Configuration {
  current: number;
  versions: VersionSummary[];
}

// A setting for each measure the rule compares: the catch rate as a
// difference, cost and time per case as fractions of the old value.
export interface MeasureSettings {
  catch_rate: number;
  cost_per_case: number;
  seconds_per_case: number;
}

export interface SettingsValues {
  // The floors a new version must meet on the held-out set.
  objectives: { catch_rate: number };
  noise: MeasureSettings;
  tolerance: MeasureSettings;
  spending_limit: number;
  agents: number;
  // The app's today, or null for the real date.
  business_date: string | null;
}

export interface Settings extends SettingsValues {
  number: number;
  changed_by: string | null;
  changed_at: string;
}

export interface ModelAllowed {
  model: string;
  reasoning_efforts: string[];
  // US dollars per million tokens.
  input_price: number;
  output_price: number;
}

export interface SettingsPage {
  current: Settings;
  changes: Settings[];
  models_allowed: ModelAllowed[];
}

export type RoundStatus = "open" | "finished" | "stopped";
export type RoundStage =
  | "first_evaluations"
  | "improving"
  | "change_waiting"
  | "evaluating"
  | "verdict"
  | "recipe_waiting";
export type ProposalKind = "change" | "recipe";
export type Review = "approved" | "rejected";

// Who approved or rejected one of the improver's proposals, and when.
export interface RoundReview {
  kind: ProposalKind;
  review: Review;
  reviewed_by: string;
  reviewed_at: string;
  rejection_reason: string | null;
}

// The proposal waiting for a reviewer, with what it would change. A recipe has
// no model.
export interface WaitingProposal {
  proposal_id: string;
  kind: ProposalKind;
  reason: string;
  proposed_at: string;
  diff: Diff;
  model_before: string | null;
  reasoning_effort_before: string | null;
  model_after: string | null;
  reasoning_effort_after: string | null;
}

export interface RoundSummary {
  round_id: string;
  number: number;
  status: RoundStatus;
  // Where an open round has got to, and how far, such as "2 of 3".
  stage: RoundStage | null;
  progress: string | null;
  started_by: string;
  started_at: string;
  finished_at: string | null;
  stopped_by: string | null;
  stopped_because: string | null;
  recipe: number;
  settings: number;
  spending_limit: number;
  cost: number;
  // The version the round tried, if any, and its verdict.
  version: number | null;
  model: string | null;
  reasoning_effort: string | null;
  reason: string | null;
  verdict: Verdict | null;
  verdict_reason: string | null;
  held_out_before: Measures | null;
  held_out_after: Measures | null;
  reviews: RoundReview[];
}

export interface RoundView extends RoundSummary {
  waiting: WaitingProposal | null;
  evaluations: Evaluation[];
}

// A version's held-out catch rate, for the chart.
export interface VersionPoint {
  number: number;
  verdict: Verdict | null;
  catch_rate: number | null;
}

export interface RecipeSummary {
  number: number;
  current: boolean;
  reason: string;
  proposed_by: string;
  round_id: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  lines_added: number;
  lines_removed: number;
}

export interface RecipeDetails extends RecipeSummary {
  recipe: string;
  diff: Diff | null;
}

export interface Improvement {
  // The open round, or the newest.
  round: RoundView | null;
  rounds: RoundSummary[];
  first_version: VersionPoint;
  versions_tried: VersionPoint[];
  recipes: RecipeSummary[];
}

// What the Copilot is asked to work on, with a sign-in that won't run out first.
const askTheCopilot = (path: string, body: object) =>
  send<Conversation>("POST", path, body, freshAccessToken);

const CASES = "/api/cases";
const casePath = (caseId: string) => `${CASES}/${encodeURIComponent(caseId)}`;
const PROJECTS = "/api/projects";
const projectPath = (projectId: string) =>
  `${PROJECTS}/${encodeURIComponent(projectId)}`;
const DISPATCHES = "/api/dispatches";
const CONFIGURATION = "/api/configuration";
const SETTINGS = "/api/settings";
const EVALUATIONS = "/api/evaluations";
const IMPROVEMENT = "/api/improvement";
const ROUNDS = `${IMPROVEMENT}/rounds`;
const roundPath = (roundId: string) =>
  `${ROUNDS}/${encodeURIComponent(roundId)}`;
const proposalPath = (roundId: string, proposalId: string) =>
  `${roundPath(roundId)}/proposals/${encodeURIComponent(proposalId)}`;
const CONVERSATIONS = "/api/copilot/conversations";
const conversationPath = (conversationId: string) =>
  `${CONVERSATIONS}/${encodeURIComponent(conversationId)}`;

export const api = {
  listCases: () => request<CaseSummary[]>(CASES),
  getCase: (caseId: string) => request<Case>(casePath(caseId)),
  listSteps: (caseId: string) => request<Step[]>(`${casePath(caseId)}/steps`),
  listProjects: () => request<Project[]>(PROJECTS),
  getProject: (projectId: string) =>
    request<ProjectInFull>(projectPath(projectId)),
  uploadPayroll: (
    projectId: string,
    subcontractorId: string,
    fileName: string,
    content: string,
  ) =>
    post<Case>(`${projectPath(projectId)}/payrolls`, {
      subcontractor_id: subcontractorId,
      file_name: fileName,
      content,
    }),
  getConfiguration: () => request<Configuration>(CONFIGURATION),
  getVersionDetails: (number: string) =>
    request<VersionDetails>(
      `${CONFIGURATION}/versions/${encodeURIComponent(number)}`,
    ),
  getSignedInReviewer: () => request<Reviewer>("/api/me"),
  getSettings: () => request<SettingsPage>(SETTINGS),
  changeSettings: (values: SettingsValues) =>
    send<SettingsPage>("PUT", SETTINGS, values),
  getLatestDispatch: () => request<Run | null>(`${DISPATCHES}/latest`),
  startDispatch: (agents: number) => post<Accepted>(DISPATCHES, { agents }),
  listEvaluations: () => request<Evaluation[]>(EVALUATIONS),
  getEvaluation: (runId: string) =>
    request<ScoredEvaluation>(`${EVALUATIONS}/${encodeURIComponent(runId)}`),
  startEvaluation: (evaluationSet: EvaluationSet, agents: number) =>
    post<Accepted>(EVALUATIONS, { evaluation_set: evaluationSet, agents }),
  signOffCase: (caseId: string) => post<Case>(`${casePath(caseId)}/sign-off`),
  sendBackCase: (caseId: string) => post<Case>(`${casePath(caseId)}/send-back`),
  getImprovement: () => request<Improvement>(IMPROVEMENT),
  getRecipe: (number: string) =>
    request<RecipeDetails>(
      `${IMPROVEMENT}/recipes/${encodeURIComponent(number)}`,
    ),
  startRound: () => post<Accepted>(ROUNDS),
  stopRound: (roundId: string) =>
    post<RoundSummary>(`${roundPath(roundId)}/stop`),
  approveProposal: (roundId: string, proposalId: string) =>
    post<Accepted>(`${proposalPath(roundId, proposalId)}/approval`),
  rejectProposal: (roundId: string, proposalId: string, reason: string) =>
    post<Accepted>(`${proposalPath(roundId, proposalId)}/rejection`, {
      reason,
    }),
  listConversations: () => request<ConversationSummary[]>(CONVERSATIONS),
  getConversation: (conversationId: string) =>
    request<Conversation>(conversationPath(conversationId)),
  startConversation: (message: string) =>
    askTheCopilot(CONVERSATIONS, { message }),
  sendMessage: (conversationId: string, message: string) =>
    askTheCopilot(`${conversationPath(conversationId)}/messages`, { message }),
};
