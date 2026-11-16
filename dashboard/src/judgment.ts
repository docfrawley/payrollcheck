import type { Candidate, ExceptionRecord } from "./api";

// How the case page reads the payroll agent's judgment calls from a case's
// record: which exception raises each check's finding, which exceptions the
// agent added with no check behind them, and where each is on the payroll.

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
