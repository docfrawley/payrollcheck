import { useCallback } from "react";
import { api } from "../api";
import { addOnName, date, label, money } from "../format";
import { useLoad } from "../useLoad";
import { StateMessage } from "./StateMessage";

export function PolicyPanel({ policyId }: Readonly<{ policyId: string }>) {
  const load = useCallback(() => api.getPolicy(policyId), [policyId]);
  const { data: policy, error } = useLoad(load);

  return (
    <section className="panel" aria-labelledby="policy-title">
      <h2 id="policy-title">Policy</h2>
      {policy ? (
        <dl className="facts">
          <div>
            <dt>Policy</dt>
            <dd className="mono">{policy.policy_id}</dd>
          </div>
          <div>
            <dt>Plan</dt>
            <dd>{label(policy.plan)}</dd>
          </div>
          <div>
            <dt>Add-ons</dt>
            <dd>
              {policy.add_ons.length > 0
                ? policy.add_ons.map(addOnName).join(", ")
                : "None"}
            </dd>
          </div>
          <div>
            <dt>Purchased</dt>
            <dd>{date(policy.purchased_on)}</dd>
          </div>
          <div>
            <dt>Sold through</dt>
            <dd>{policy.sold_through}</dd>
          </div>
          <div>
            <dt>Trip</dt>
            <dd>
              {policy.trip.destination}, {date(policy.trip.departs_on)} to{" "}
              {date(policy.trip.returns_on)}
            </dd>
          </div>
          <div>
            <dt>Trip cost</dt>
            <dd className="mono">{money(policy.trip.trip_cost)}</dd>
          </div>
          <div>
            <dt>Travelers</dt>
            <dd>{policy.travelers.join(", ")}</dd>
          </div>
        </dl>
      ) : (
        <StateMessage error={error} />
      )}
    </section>
  );
}

export function HistoryPanel({
  subcontractorId,
}: Readonly<{ subcontractorId: string }>) {
  const load = useCallback(
    () => api.getCaseHistory(subcontractorId),
    [subcontractorId],
  );
  const { data: history, error } = useLoad(load);

  return (
    <section className="panel" aria-labelledby="history-title">
      <h2 id="history-title">Earlier cases</h2>
      {!history && <StateMessage error={error} />}
      {history?.length === 0 && (
        <StateMessage empty="No earlier cases: this is the subcontractor's first case with us." />
      )}
      {history && history.length > 0 && (
        <ul className="history">
          {history.map((caseRecord) => (
            <li key={caseRecord.case_id}>
              <p className="small muted">
                <span className="mono">{caseRecord.case_id}</span>,{" "}
                {label(caseRecord.case_type)}, filed {date(caseRecord.filed_on)}
              </p>
              <p>{caseRecord.summary}</p>
              <p className="small">
                {label(caseRecord.outcome)}, paid{" "}
                <span className="mono">{money(caseRecord.amount_paid)}</span>
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
