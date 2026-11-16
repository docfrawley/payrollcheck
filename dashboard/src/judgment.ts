import type { Candidate, Case } from "./api";
import type { ExceptionRecord } from "./exceptions";

// How the case page reads the payroll agent's judgment calls and the
// reviewers' overrides from a case's record: which exception raises each
// check's finding, which exceptions the agent added with no check behind
// them, where each is on the payroll, and when a reviewer may override them.

// An exception the agent raised on its own judgment, which no check found.
export const ownJudgment = (exception: ExceptionRecord) =>
  exception.source === "agent";

// The exception that raises a check's finding, if one does.
export const exceptionFor = (
  candidate: Candidate,
  exceptions: ExceptionRecord[],
) =>
  exceptions.find(
    (exception) => exception.candidate_id === candidate.candidate_id,
  );

// Where a finding is on the payroll: the worker and line, or the whole payroll
// for a rule about the certification.
export function whereOnPayroll(
  workerId: string | null,
  lineNo: number | null,
): string {
  if (workerId === null) return "The whole payroll";
  return lineNo === null ? workerId : `${workerId}, line ${String(lineNo)}`;
}

// Whether a reviewer may work a case: override its exceptions, edit its notice
// and answer it, only while it awaits review, and never on an evaluation's copy.
export const reviewable = (caseRecord: Case) =>
  caseRecord.status === "awaiting_review" && caseRecord.evaluation_id === null;
