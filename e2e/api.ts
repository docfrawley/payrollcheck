import { type APIRequestContext, expect } from "@playwright/test";
import type {
  Candidate,
  EvaluationSet,
  RoundStatus,
  Run,
  ScoredEvaluation,
  StepKind,
} from "../dashboard/src/api";
import type { Source } from "../dashboard/src/sources";
import { REVIEWERS, signedInAs } from "./reviewers";
import { EVALUATIONS, evaluationPath, roundPath, runPath } from "./paths";
import { AGENT_KEY_HEADERS, AGENT_STAND_IN } from "./servers";

// Stands in for the agent and its payroll agents, with one function for each
// backend operation the tests use, sent through the dashboard's proxy with the
// agent's key.
export type Request = APIRequestContext;

const casePath = (caseId: string) => `/api/cases/${encodeURIComponent(caseId)}`;

// Sends a request as the agent's side does, with its key, and returns the
// backend's answer, which may be a refusal.
const asTheAgent = (
  request: Request,
  method: "POST" | "PUT",
  path: string,
  data: object = {},
) => request.fetch(path, { method, data, headers: AGENT_KEY_HEADERS });

async function send(
  request: Request,
  method: "POST" | "PUT",
  path: string,
  data: object = {},
) {
  const response = await asTheAgent(request, method, path, data);
  await expect(response).toBeOK();
  return response;
}

export const startCase = (request: Request, caseId: string, thread: string) =>
  send(request, "POST", `${casePath(caseId)}/start`, { thread_id: thread });

// Records a step, with the context files a lookup came from, and none for any
// other step.
export const recordStep = (
  request: Request,
  caseId: string,
  kind: StepKind,
  content: string,
  sources: Source[] = [],
) =>
  send(request, "POST", `${casePath(caseId)}/steps`, {
    kind,
    content,
    sources,
  });

// Who raises the exceptions the tests record, as the payroll agent says it.
const MAKER = "PayrollCheck Agent, version 1";

// A check tool's finding, as the payroll agent's checks give it.
export interface Finding {
  rule: string;
  worker_id: string | null;
  line_no: number | null;
  expected: string;
  actual: string;
  shortfall_cents: number | null;
  citation: string;
}

// Records one check's findings, which the backend keeps as the attempt's
// candidates, and returns them with their ids.
export async function recordCheckFindings(
  request: Request,
  caseId: string,
  check: string,
  findings: Finding[] = [],
): Promise<Candidate[]> {
  const response = await send(
    request,
    "POST",
    `${casePath(caseId)}/candidates`,
    {
      check,
      findings,
    },
  );
  return (await response.json()) as Candidate[];
}

// The check tools, in the order they run.
export const CHECKS = [
  "check_form",
  "check_contractor_registration",
  "check_rates",
  "check_overtime",
  "check_arithmetic",
  "check_apprentices",
  "check_timeliness",
  "check_classification",
];

// Records every check the attempt hasn't run as finding nothing, as the check
// node runs them all before the model reports.
async function runTheOtherChecks(request: Request, caseId: string) {
  const response = await request.get(casePath(caseId), {
    headers: AGENT_KEY_HEADERS,
  });
  await expect(response).toBeOK();
  const { checks_run } = (await response.json()) as { checks_run: string[] };
  for (const check of CHECKS)
    if (!checks_run.includes(check))
      await recordCheckFindings(request, caseId, check);
}

export interface ExceptionReport {
  raised: number[];
  dismissed: { candidate_id: number; reason: string }[];
  added: Finding[];
  notice: string;
}

// Records the payroll agent's exception report, with its maker, once every
// check has run, which moves the case to Awaiting review.
export async function recordExceptionReport(
  request: Request,
  caseId: string,
  report: Partial<ExceptionReport> = {},
) {
  await runTheOtherChecks(request, caseId);
  return send(request, "POST", `${casePath(caseId)}/report`, {
    raised: [],
    dismissed: [],
    added: [],
    notice: "",
    ...report,
    raised_by: MAKER,
  });
}

export const recordScreeningFlag = (
  request: Request,
  caseId: string,
  reason: string,
) => send(request, "POST", `${casePath(caseId)}/screening-flag`, { reason });

export const failCase = (request: Request, caseId: string, reason: string) =>
  send(request, "POST", `${casePath(caseId)}/failure`, { reason });

export const recordModelCall = (
  request: Request,
  caseId: string,
  runId: string,
  cost: number,
) =>
  send(request, "POST", `${casePath(caseId)}/model-calls`, {
    run_id: runId,
    input_tokens: 1200,
    output_tokens: 300,
    cost,
  });

export const recordWorkTime = (
  request: Request,
  caseId: string,
  runId: string,
  seconds: number,
) =>
  send(request, "POST", `${casePath(caseId)}/work-times`, {
    run_id: runId,
    seconds,
  });

// The queue's cases, as a reviewer reads them.
export async function listCases(
  request: Request,
  headers: Record<string, string>,
): Promise<unknown[]> {
  const response = await request.get("/api/cases", { headers });
  await expect(response).toBeOK();
  return (await response.json()) as unknown[];
}

// An evaluation with its copies beside their labels, as Dana Whitfield reads
// it on the Scoreboard.
export async function getEvaluation(
  request: Request,
  runId: string,
): Promise<ScoredEvaluation> {
  const response = await request.get(evaluationPath(runId), {
    headers: await signedInAs(request, REVIEWERS.dana),
  });
  await expect(response).toBeOK();
  return (await response.json()) as ScoredEvaluation;
}

// A run as the agent reads it.
export async function getRun(request: Request, runId: string): Promise<Run> {
  const response = await request.get(runPath(runId), {
    headers: AGENT_KEY_HEADERS,
  });
  await expect(response).toBeOK();
  return (await response.json()) as Run;
}

// Starts a run as a reviewer does, and returns it as the agent reads it.
async function startRun(
  request: Request,
  path: string,
  data: object,
): Promise<Run> {
  const before = (await started(request)).length;
  const response = await request.post(path, {
    data,
    headers: await signedInAs(request, REVIEWERS.dana),
  });
  await expect(response).toBeOK();
  const { run_id } = await nextStarted(request, before);
  return getRun(request, String(run_id));
}

export const startDispatch = (request: Request, agents: number) =>
  startRun(request, "/api/dispatches", { agents });

export const startEvaluation = (
  request: Request,
  evaluationSet: EvaluationSet,
  agents: number,
) =>
  startRun(request, EVALUATIONS, {
    evaluation_set: evaluationSet,
    agents,
  });

export const recordRunCases = (
  request: Request,
  runId: string,
  caseIds: string[],
) => send(request, "PUT", `${runPath(runId)}/cases`, { case_ids: caseIds });

export const finishRun = (request: Request, runId: string) =>
  send(request, "POST", `${runPath(runId)}/finish`);

// A round of the improver, started by Dana Whitfield and played out as the
// agent would record it.
export async function startRound(request: Request): Promise<string> {
  const before = (await started(request)).length;
  const response = await request.post("/api/improvement/rounds", {
    headers: await signedInAs(request, REVIEWERS.dana),
  });
  await expect(response).toBeOK();
  return String((await nextStarted(request, before)).round_id);
}

// A round as the agent reads it, as far as the tests need.
export async function getRound(
  request: Request,
  roundId: string,
): Promise<{ round_id: string; number: number; status: RoundStatus }> {
  const response = await request.get(roundPath(roundId), {
    headers: AGENT_KEY_HEADERS,
  });
  await expect(response).toBeOK();
  return (await response.json()) as {
    round_id: string;
    number: number;
    status: RoundStatus;
  };
}

// The first case the round's results hold, as the improver would cite it, or
// none when they hold none.
async function citedIn(request: Request, roundId: string): Promise<string[]> {
  const response = await request.get(`${roundPath(roundId)}/results`, {
    headers: AGENT_KEY_HEADERS,
  });
  await expect(response).toBeOK();
  const view = (await response.json()) as Record<
    "development_mistakes" | "weakest_notices" | "overrides",
    { shown: { case_id: string }[] }
  >;
  return [
    ...view.development_mistakes.shown,
    ...view.weakest_notices.shown,
    ...view.overrides.shown,
  ]
    .map((entry) => entry.case_id)
    .slice(0, 1);
}

// Propose a change as the improver does, citing the first case the round's
// results hold unless the caller gives its own.
export async function recordChangeProposal(
  request: Request,
  roundId: string,
  instructions: string,
  parameters: Record<string, number> = { rounding_tolerance_cents: 0 },
  caseIds?: string[],
): Promise<string> {
  const response = await send(
    request,
    "POST",
    `${roundPath(roundId)}/proposals/change`,
    {
      instructions,
      model: "openai/gpt-6-luna",
      reasoning_effort: "low",
      parameters,
      reason: "Two weekend premiums were missed on the rates check",
      case_ids: caseIds ?? (await citedIn(request, roundId)),
    },
  );
  return ((await response.json()) as { proposal_id: string }).proposal_id;
}

export async function recordRecipeProposal(
  request: Request,
  roundId: string,
): Promise<string> {
  const response = await send(
    request,
    "POST",
    `${roundPath(roundId)}/proposals/recipe`,
    { recipe: "1. Read the results.\n", reason: "A shorter recipe" },
  );
  return ((await response.json()) as { proposal_id: string }).proposal_id;
}

// A proposal with its review, as the agent reads it.
export async function getProposal(
  request: Request,
  roundId: string,
  proposalId: string,
): Promise<{ review: string | null; rejection_reason: string | null }> {
  const response = await request.get(
    `${roundPath(roundId)}/proposals/${proposalId}`,
    { headers: AGENT_KEY_HEADERS },
  );
  await expect(response).toBeOK();
  return (await response.json()) as {
    review: string | null;
    rejection_reason: string | null;
  };
}

export const createVersion = (request: Request, roundId: string) =>
  send(request, "POST", `${roundPath(roundId)}/version`);

// Stops the runs and rounds the tests started that are still going, through
// the stand-in for the agent, so the next test can start its own.
export async function stopTheWork(request: Request) {
  const response = await request.post(`${AGENT_STAND_IN}/api/stop`);
  await expect(response).toBeOK();
}

// A payload the backend sent the agent, naming its operation.
export type Payload = { operation: string } & Record<string, unknown>;

// Every payload the stand-in for the agent took, oldest first.
export async function started(request: Request): Promise<Payload[]> {
  const response = await request.get(`${AGENT_STAND_IN}/api/started`);
  await expect(response).toBeOK();
  return (await response.json()) as Payload[];
}

// Waits for the stand-in for the agent to take exactly one payload more than
// the `before` it had, and returns that payload.
export async function nextStarted(
  request: Request,
  before: number,
): Promise<Payload> {
  let payloads: Payload[] = [];
  await expect
    .poll(async () => {
      payloads = await started(request);
      return payloads.length;
    })
    .toBe(before + 1);
  const next = payloads.at(before);
  if (!next) throw new Error("The stand-in for the agent took nothing");
  return next;
}
