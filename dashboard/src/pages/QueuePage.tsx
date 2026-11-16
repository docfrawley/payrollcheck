import {
  Bot,
  CircleCheck,
  Inbox,
  type LucideIcon,
  Signature,
  Undo2,
} from "lucide-react";
import { api, type Status, statuses } from "../api";
import { CaseFlags, StatusChip } from "../components/Chips";
import { CaseLink } from "../components/CaseLink";
import { StateMessage } from "../components/StateMessage";
import { DispatchPanel } from "../components/DispatchPanel";
import { PageHeader } from "../components/PageHeader";
import { cents, date, statusLabels } from "../format";
import { REFRESH_MS, useLoad } from "../useLoad";

// Each status's icon on its tile.
const STATUS_ICONS: Record<Status, LucideIcon> = {
  received: Inbox,
  in_progress: Bot,
  awaiting_review: Signature,
  accepted: CircleCheck,
  returned_to_sub: Undo2,
};

export function QueuePage() {
  const { data: cases, error } = useLoad(api.listCases, REFRESH_MS);
  const header = <PageHeader title="Case queue" />;
  if (!cases)
    return (
      <>
        {header}
        <StateMessage error={error} />
      </>
    );

  return (
    <>
      {header}
      <section className="tiles" aria-label="Cases by status">
        {statuses.map((status) => {
          const count = cases.filter((c) => c.status === status).length;
          const Icon = STATUS_ICONS[status];
          return (
            <div
              className={`tile status-${status}`}
              key={status}
              role="group"
              aria-label={`${statusLabels[status]}: ${String(count)}`}
            >
              <p className="tile-label">{statusLabels[status]}</p>
              <p className="tile-figure">
                <span className="tile-count">{count}</span>
                <Icon />
              </p>
            </div>
          );
        })}
      </section>
      <DispatchPanel />
      <section className="panel" aria-labelledby="cases-title">
        <h2 id="cases-title">Cases</h2>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Case</th>
                <th>Subcontractor</th>
                <th>Project</th>
                <th>Week ending</th>
                <th>Status</th>
                <th className="num">Open exceptions</th>
                <th className="num">Shortfall</th>
                <th>Flags</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((caseRecord) => (
                <tr key={caseRecord.case_id}>
                  <td className="nowrap">
                    <CaseLink caseId={caseRecord.case_id} />
                  </td>
                  <td>{caseRecord.subcontractor_name}</td>
                  <td>{caseRecord.project_name}</td>
                  <td className="nowrap">{date(caseRecord.week_ending)}</td>
                  <td>
                    <StatusChip status={caseRecord.status} />
                  </td>
                  <td className="num mono">
                    {caseRecord.open_exceptions > 0 &&
                      caseRecord.open_exceptions}
                  </td>
                  <td className="num mono">
                    {caseRecord.shortfall_cents > 0 &&
                      cents(caseRecord.shortfall_cents)}
                  </td>
                  <td className="nowrap">
                    <CaseFlags
                      screeningFlag={caseRecord.screening_flag}
                      agentFailed={caseRecord.agent_failed}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
