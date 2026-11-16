import { useCallback } from "react";
import { Link, useParams } from "react-router";
import { api, type ScoredEvaluation } from "../api";
import { RunChip } from "../components/Chips";
import { ScoredCopies } from "../components/ScoredCopies";
import { StateMessage } from "../components/StateMessage";
import { SuccessCriteria } from "../components/SuccessCriteria";
import { ModelName } from "../components/ModelName";
import { PageHeader } from "../components/PageHeader";
import {
  agentsAtOnce,
  dateTime,
  evaluationSetName,
  modelCost,
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
        {evaluation.success_criteria && (
          <SuccessCriteria criteria={evaluation.success_criteria} />
        )}
        <ScoredCopies cases={evaluation.cases} />
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
        <span className="mono">{modelCost(evaluation.model_cost)}</span>, judge
        cost <span className="mono">{modelCost(evaluation.judge_cost)}</span>.
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
