// The shapes of a case's exceptions and a reviewer's overrides of them, as the
// backend gives and takes them.

export type Severity = "high" | "medium" | "low";
export type ExceptionStatus = "open" | "dismissed" | "superseded";
// What raised an exception: a check tool's finding, the payroll agent's own
// judgment with no check behind it, or a reviewer.
export type ExceptionSource = "check" | "agent" | "reviewer";

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
  source: ExceptionSource;
  // The check's finding it raises.
  candidate_id: number | null;
  status: ExceptionStatus;
}

export type OverrideKind = "dismissed" | "added" | "restored";

// A reviewer's override of an exception, never edited or deleted.
export interface Override {
  override_id: number;
  exception_id: number;
  submission_no: number;
  kind: OverrideKind;
  reviewer_id: string;
  reviewer_name: string;
  reason: string;
  created_at: string;
}

// An exception a reviewer adds.
export interface NewException {
  rule: string;
  worker_id: string | null;
  line_no: number | null;
  expected: string;
  actual: string;
  shortfall_cents: number | null;
  reason: string;
}

// A rule of the catalogue, for the form that adds an exception.
export interface RuleEntry {
  rule: string;
  check: string;
  severity: Severity;
  money: boolean;
  // Found on a worker's line, not on the payroll as a whole.
  worker: boolean;
}
