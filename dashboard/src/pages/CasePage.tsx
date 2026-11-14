import { useCallback } from "react";
import { Link, useParams } from "react-router";
import { api, type Case } from "../api";
import { StatusChip } from "../components/Chips";
import { ContextUsed } from "../components/ContextUsed";
import { DecisionPanel } from "../components/DecisionPanel";
import { StateMessage } from "../components/StateMessage";
import { PageHeader } from "../components/PageHeader";
import { HistoryPanel, PolicyPanel } from "../components/PolicyPanels";
import { SentBackDecisions } from "../components/SentBackDecisions";
import { StepList } from "../components/StepList";
import { date, label, money } from "../format";
import { evaluationPage, QUEUE } from "../paths";
import { REFRESH_MS, useLoad } from "../useLoad";

export function CasePage() {
  const { caseId = "" } = useParams();
  const load = useCallback(() => api.getCase(caseId), [caseId]);
  const { data: caseRecord, error, reload } = useLoad(load, REFRESH_MS);
  const loadSteps = useCallback(() => api.listSteps(caseId), [caseId]);
  const steps = useLoad(loadSteps, REFRESH_MS);

  if (!caseRecord)
    return (
      <>
        <PageHeader eyebrow={<Link to={QUEUE}>Queue</Link>} title={caseId} />
        <StateMessage
          error={error}
          notFound="Case not found. Choose one from the queue."
        />
      </>
    );

  return (
    <>
      <PageHeader
        eyebrow={
          <>
            {caseRecord.evaluation_id ? (
              <Link to={evaluationPage(caseRecord.evaluation_id)}>
                Evaluation
              </Link>
            ) : (
              <Link to={QUEUE}>Queue</Link>
            )}{" "}
            <span className="mono">/ {caseRecord.case_id}</span>
          </>
        }
        title={caseRecord.summary}
        status={<StatusChip status={caseRecord.status} />}
        lead={
          caseRecord.evaluation_id ? (
            <>
              A copy of <span className="mono">{caseRecord.copy_of}</span> in an{" "}
              <Link to={evaluationPage(caseRecord.evaluation_id)}>
                evaluation
              </Link>
            </>
          ) : (
            `${caseRecord.customer_name}'s ${label(caseRecord.case_type).toLowerCase()} case`
          )
        }
      />
      {/* The agent's steps grow at the end of the right column, and the context
          it used at the end of the left, so neither moves anything as the
          page refreshes. */}
      <div className="case-layout">
        <div className="column">
          <CaseDetails caseRecord={caseRecord} />
          <ItemsPanel caseRecord={caseRecord} />
          <DocumentsPanel caseRecord={caseRecord} />
          <PolicyPanel policyId={caseRecord.policy_id} />
          <HistoryPanel customerId={caseRecord.customer_id} />
          <ContextUsed steps={steps.data} />
        </div>
        <div className="column">
          <DecisionPanel caseRecord={caseRecord} onAnswered={reload} />
          <SentBackDecisions decisions={caseRecord.sent_back_decisions} />
          <StepList steps={steps.data} error={steps.error} />
        </div>
      </div>
    </>
  );
}

function CaseDetails({ caseRecord }: Readonly<{ caseRecord: Case }>) {
  return (
    <section className="panel" aria-labelledby="case-title">
      <h2 id="case-title">Case</h2>
      <dl className="facts">
        <div>
          <dt>Customer</dt>
          <dd>{caseRecord.customer_name}</dd>
        </div>
        <div>
          <dt>Type</dt>
          <dd>{label(caseRecord.case_type)}</dd>
        </div>
        <div>
          <dt>Incident</dt>
          <dd>
            {date(caseRecord.incident_date)}, {caseRecord.incident_location}
          </dd>
        </div>
        <div>
          <dt>Submitted</dt>
          <dd>{date(caseRecord.submitted_on)}</dd>
        </div>
        <div>
          <dt>Amount claimed</dt>
          <dd className="mono">{money(caseRecord.amount_claimed)}</dd>
        </div>
      </dl>
      <h3>The customer's story</h3>
      <p className="story">{caseRecord.story}</p>
    </section>
  );
}

function ItemsPanel({ caseRecord }: Readonly<{ caseRecord: Case }>) {
  const total = caseRecord.items.reduce((sum, item) => sum + item.amount, 0);
  return (
    <section className="panel" aria-labelledby="items-title">
      <h2 id="items-title">Items claimed</h2>
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Category</th>
              <th className="num">Amount</th>
            </tr>
          </thead>
          <tbody>
            {caseRecord.items.map((item) => (
              <tr key={item.description}>
                <td>{item.description}</td>
                <td>{label(item.category)}</td>
                <td className="num mono">{money(item.amount)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colSpan={2}>
                Total
              </th>
              <td className="num mono">{money(total)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

function DocumentsPanel({ caseRecord }: Readonly<{ caseRecord: Case }>) {
  return (
    <section className="panel" aria-labelledby="documents-title">
      <h2 id="documents-title">Documents</h2>
      {caseRecord.documents.map((document) => (
        <article className="document" key={document.name}>
          <h3>{document.name}</h3>
          <p className="muted small">{label(document.type)}</p>
          <p>{document.content}</p>
        </article>
      ))}
    </section>
  );
}
