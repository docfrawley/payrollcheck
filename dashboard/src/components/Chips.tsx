import { Bot, ShieldAlert } from "lucide-react";
import type {
  LabelMatch,
  RoundStatus,
  RunStatus,
  Status,
  Verdict,
  VersionStatus,
} from "../api";
import type { Severity } from "../exceptions";
import {
  roundLabels,
  runLabels,
  severityLabels,
  statusLabels,
  verdictLabels,
  versionLabels,
} from "../format";

export function StatusChip({ status }: Readonly<{ status: Status }>) {
  return (
    <span className={`chip status-${status}`}>{statusLabels[status]}</span>
  );
}

export function SeverityChip({ severity }: Readonly<{ severity: Severity }>) {
  return (
    <span className={`chip severity-${severity}`}>
      {severityLabels[severity]}
    </span>
  );
}

// The flags that leave a case for a reviewer to work by hand: an instruction
// the screening found, or two attempts the agent failed.
export function CaseFlags({
  screeningFlag,
  agentFailed,
}: Readonly<{ screeningFlag: boolean; agentFailed: boolean }>) {
  return (
    <>
      {screeningFlag && (
        <span className="chip flag">
          <ShieldAlert aria-hidden />
          Screening flag
        </span>
      )}
      {screeningFlag && agentFailed && " "}
      {agentFailed && (
        <span className="chip flag">
          <Bot aria-hidden />
          Agent failed
        </span>
      )}
    </>
  );
}

export function RunChip({ status }: Readonly<{ status: RunStatus }>) {
  return <span className={`chip run-${status}`}>{runLabels[status]}</span>;
}

export function VersionChip({ status }: Readonly<{ status: VersionStatus }>) {
  return (
    <span className={`chip version-${status}`}>{versionLabels[status]}</span>
  );
}

export function RoundChip({ status }: Readonly<{ status: RoundStatus }>) {
  return <span className={`chip round-${status}`}>{roundLabels[status]}</span>;
}

export function VerdictChip({ verdict }: Readonly<{ verdict: Verdict }>) {
  return (
    <span className={`chip verdict-${verdict}`}>{verdictLabels[verdict]}</span>
  );
}

const LABEL_RESULTS: Record<LabelMatch["result"], string> = {
  caught: "Caught",
  missed: "Missed",
  shortfall_wrong: "Shortfall wrong",
};

// Whether the agent caught a label, and with the right shortfall.
export function LabelResultChip({
  result,
}: Readonly<{ result: LabelMatch["result"] }>) {
  return (
    <span className={`chip score-${result}`}>{LABEL_RESULTS[result]}</span>
  );
}

// Whether a success criterion is met.
export function MetChip({ met }: Readonly<{ met: boolean }>) {
  return met ? (
    <span className="chip score-caught">Met</span>
  ) : (
    <span className="chip score-missed">Not met</span>
  );
}

// Whether an exception the agent raised matched a label.
export function MatchedChip({ matched }: Readonly<{ matched: boolean }>) {
  return matched ? (
    <span className="chip score-caught">Matched</span>
  ) : (
    <span className="chip score-missed">False</span>
  );
}
