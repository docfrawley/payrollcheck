import {
  Bot,
  CircleCheck,
  Flag,
  Inbox,
  type LucideIcon,
  Signature,
  Undo2,
} from "lucide-react";
import { api, type Status, statuses } from "../api";
import { DecisionChip, StatusChip } from "../components/Chips";
import { CaseLink } from "../components/CaseLink";
import { StateMessage } from "../components/StateMessage";
import { DispatchPanel } from "../components/DispatchPanel";
import { PageHeader } from "../components/PageHeader";
import { date, label, money, statusLabels } from "../format";
import { REFRESH_MS, useLoad } from "../useLoad";

// Each state's icon on its tile.
const STATUS_ICONS: Record<Status, LucideIcon> = {
  waiting: Inbox,
  in_progress: Bot,
  waiting_for_sign_off: Signature,
  sent_back: Undo2,
  decided: CircleCheck,
  left_for_reviewer: Flag,
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
      <section className="tiles" aria-label="Cases by state">
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
                <th>Type</th>
                <th>Summary</th>
                <th className="num">Claimed</th>
                <th>Submitted</th>
                <th>State</th>
                <th>Decision</th>
                <th className="num">Payout</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((caseRecord) => (
                <tr key={caseRecord.case_id}>
                  <td className="nowrap">
                    <CaseLink caseId={caseRecord.case_id} />
                  </td>
                  <td className="nowrap">{caseRecord.subcontractor_name}</td>
                  <td className="nowrap">{label(caseRecord.case_type)}</td>
                  <td>{caseRecord.summary}</td>
                  <td className="num mono">
                    {money(caseRecord.amount_claimed)}
                  </td>
                  <td className="nowrap">{date(caseRecord.submitted_on)}</td>
                  <td>
                    <StatusChip status={caseRecord.status} />
                  </td>
                  <td>
                    {caseRecord.decision && (
                      <DecisionChip decision={caseRecord.decision} />
                    )}
                  </td>
                  <td className="num mono">
                    {caseRecord.payout !== null && money(caseRecord.payout)}
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
