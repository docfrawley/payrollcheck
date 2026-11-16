// The backend's paths to a run, an evaluation and a round, shared by the
// tests' requests and the stand-in for the agent.
export const runPath = (runId: string) => `/api/runs/${runId}`;
export const EVALUATIONS = "/api/evaluations";
export const evaluationPath = (runId: string) => `${EVALUATIONS}/${runId}`;
export const roundPath = (roundId: string) => `/api/rounds/${roundId}`;
export const roundEvaluationsPath = (roundId: string) =>
  `/api/runs/rounds/${roundId}/evaluations`;
