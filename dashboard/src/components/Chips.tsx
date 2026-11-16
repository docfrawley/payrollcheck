import { Bot, ShieldAlert } from "lucide-react";
import type {
  RoundStatus,
  RunStatus,
  Severity,
  Status,
  Verdict,
  VersionStatus,
} from "../api";
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
