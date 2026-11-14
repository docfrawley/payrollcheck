import { useCallback } from "react";
import { Link, useParams } from "react-router";
import { api, type ScoredCase, type ScoredEvaluation } from "../api";
import { DecisionPayout, RightChip, RunChip } from "../components/Chips";
import { CaseLink } from "../components/CaseLink";
import { Check, GradeChip } from "../components/Judging";
import { StateMessage } from "../components/StateMessage";
import { ModelName } from "../components/ModelName";
import { PageHeader } from "../components/PageHeader";
import {
  agentsAtOnce,
  dateTime,
  duration,
  evaluationSetName,
  modelCost,
  money,
} from "../format";
import { MEASURES } from "../measures";
import { SCOREBOARD } from "../paths";
import { REFRESH_MS, useLoad } from "../useLoad";

export function EvaluationPage() {
  const { runId = "" } = useParams();
  const load = useCallback(() => api.getEvaluation(runId), [runId]);
  const { data: evaluation, error } = useLoad(load, REFRESH_MS);

  if (!evaluation)
    return (
      <>
        <PageHeader
          eyebrow={<Link to={SCOREBOARD}>Scoreboard</Link>}
          title="Evaluation"
        />
        <StateMessage
          error={error}
          notFound="Evaluation not found. Choose one on the Scoreboard."
        />
      </>
    );

  return (
    <>
      <PageHeader
        eyebrow={<Link to={SCOREBOARD}>Scoreboard</Link>}
        title={`Evaluation #${String(evaluation.number)}`}
        status={<RunChip status={evaluation.status} />}
      />
      <div className="column">
        <MeasuresPanel evaluation={evaluation} />
        <ScoredCases cases={evaluation.cases} />
      </div>
    </>
  );
}

function MeasuresPanel({
  evaluation,
}: Readonly<{ evaluation: ScoredEvaluation }>) {
  return (
    <section className="panel" aria-labelledby="measures-title">
      <h2 id="measures-title">Measures</h2>
      <p className="muted small">
        {evaluationSetName(evaluation.evaluation_set, evaluation.size)}, with{" "}
        {agentsAtOnce(evaluation.agents)} on{" "}
        <ModelName
          model={evaluation.model}
          reasoningEffort={evaluation.reasoning_effort}
        />
        , version {evaluation.version}. Started{" "}
        {dateTime(evaluation.started_at)}. Model cost{" "}
        <span className="mono">{modelCost(evaluation.model_cost)}</span> and
        judge cost{" "}
        <span className="mono">{modelCost(evaluation.judge_cost)}</span>.
      </p>
      {evaluation.stopped_because && (
        <p className="stopped">{evaluation.stopped_because}</p>
      )}
      <dl className="facts measures">
        {MEASURES.map(({ label, show }) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd className="mono">{show(evaluation.measures)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function ScoredCases({ cases }: Readonly<{ cases: ScoredCase[] }>) {
  return (
    <section className="panel" aria-labelledby="cases-title">
      <h2 id="cases-title">Cases</h2>
      <p className="muted small">
        A case the agent didn't decide counts as a referral and gets an F from
        the judge.
      </p>
      <div className="table-scroll">
        <table className="table steady scored-cases">
          <colgroup>
            <col className="col-case" />
            <col className="col-id" />
            <col className="col-decision" />
            <col className="col-decision" />
            <col className="col-chip" />
            <col className="col-chip" />
            <col className="col-chip" />
            <col className="col-chip" />
            <col className="col-money" />
            <col className="col-money" />
            <col className="col-time" />
            <col className="col-reason" />
          </colgroup>
          <thead>
            <tr>
              <th>Copy</th>
              <th>Of</th>
              <th>Reviewer</th>
              <th>Agent</th>
              <th>Score</th>
              <th>Grade</th>
              <th>Same grounds</th>
              <th>Same section</th>
              <th className="num">Mistake cost</th>
              <th className="num">Model cost</th>
              <th className="num">Time</th>
              <th>The agent's reason</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((caseRecord) => (
              <tr key={caseRecord.case_id}>
                <td className="nowrap">
                  <CaseLink caseId={caseRecord.case_id} />
                </td>
                <td className="mono nowrap">{caseRecord.copy_of}</td>
                <td className="nowrap">
                  <DecisionPayout
                    decision={caseRecord.reviewer_decision}
                    payout={caseRecord.reviewer_payout}
                  />
                </td>
                <td className="nowrap">
                  {caseRecord.decision && caseRecord.payout !== null ? (
                    <DecisionPayout
                      decision={caseRecord.decision}
                      payout={caseRecord.payout}
                    />
                  ) : (
                    <span className="muted">No decision</span>
                  )}
                </td>
                <td>
                  <RightChip right={caseRecord.right} />
                </td>
                <td>
                  <GradeChip grade={caseRecord.grade} />
                </td>
                <td>
                  {caseRecord.grade && (
                    <Check chance={caseRecord.grade.same_grounds} />
                  )}
                </td>
                <td>
                  {caseRecord.grade && (
                    <Check chance={caseRecord.grade.same_section} />
                  )}
                </td>
                <td className="num mono">{money(caseRecord.mistake_cost)}</td>
                <td className="num mono">{modelCost(caseRecord.model_cost)}</td>
                <td className="num mono">{duration(caseRecord.seconds)}</td>
                <td className="small">
                  <span
                    className="two-lines"
                    title={caseRecord.reason ?? undefined}
                  >
                    {caseRecord.reason}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
