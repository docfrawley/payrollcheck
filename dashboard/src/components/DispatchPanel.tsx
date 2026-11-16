import { Play } from "lucide-react";
import { Fragment, useState } from "react";
import { api, type DispatchSummary, type Run, type RunCase } from "../api";
import {
  agentsAtOnce,
  dateTime,
  duration,
  modelCost,
  stoppedBecause,
  time,
} from "../format";
import { REFRESH_MS, useLoad } from "../useLoad";
import { CaseFlags, RunChip, StatusChip } from "./Chips";
import { CaseLink } from "./CaseLink";
import { StateMessage } from "./StateMessage";
import { ActionForm } from "./ActionForm";
import { AgentsChoice, FIRST_CHOICE } from "./AgentsChoice";

export function DispatchPanel() {
  const { data: dispatch, error } = useLoad(api.getLatestDispatch, REFRESH_MS);
  const [agents, setAgents] = useState(FIRST_CHOICE);

  return (
    <section className="panel dispatch" aria-labelledby="dispatch-title">
      <div className="title-row">
        <h2 id="dispatch-title">Dispatch</h2>
        {dispatch && <RunChip status={dispatch.status} />}
      </div>
      <ActionForm
        label="Start a dispatch"
        icon={<Play />}
        action={() => api.startDispatch(agents)}
      >
        <AgentsChoice agents={agents} onChange={setAgents} />
      </ActionForm>
      {dispatch === undefined && <StateMessage error={error} />}
      {dispatch === null && (
        <StateMessage empty="No dispatch yet. Start one to check the Received cases." />
      )}
      {dispatch && <DispatchDetails dispatch={dispatch} />}
    </section>
  );
}

function DispatchDetails({ dispatch }: Readonly<{ dispatch: Run }>) {
  return (
    <>
      <p className="muted small">
        <span className="mono">#{dispatch.number}</span> started at{" "}
        {dateTime(dispatch.started_at)} with {agentsAtOnce(dispatch.agents)}, on
        version {dispatch.version}. Model cost{" "}
        <span className="mono">{modelCost(dispatch.model_cost)}</span>
        {dispatch.seconds !== null && (
          <>
            , took <span className="mono">{duration(dispatch.seconds)}</span>
          </>
        )}
        .
      </p>
      {dispatch.status === "stopped" && (
        <p className="stopped">
          {dispatch.stopped_because
            ? stoppedBecause(dispatch.stopped_because)
            : "It stopped before it finished."}{" "}
          The next dispatch carries on its cases.
        </p>
      )}
      {dispatch.cases.length > 0 && <RunCases cases={dispatch.cases} />}
      {dispatch.cases.length === 0 && dispatch.other_projects === 0 && (
        <StateMessage empty="No cases in this dispatch: the queue had none Received or in progress when it started." />
      )}
      {dispatch.other_projects > 0 && (
        <p className="muted">
          {dispatch.cases.length > 0 ? "And " : ""}
          {casesOnOtherProjects(dispatch.other_projects)}.
        </p>
      )}
      {dispatch.summary && <Summary summary={dispatch.summary} />}
    </>
  );
}

function RunCases({ cases }: Readonly<{ cases: RunCase[] }>) {
  return (
    <div className="table-scroll">
      <table className="table">
        <thead>
          <tr>
            <th>Case</th>
            <th>Subcontractor</th>
            <th>Project</th>
            <th>Status</th>
            <th className="num">Open exceptions</th>
            <th>Flags</th>
            <th>Started</th>
            <th className="num">Time</th>
            <th className="num">Model cost</th>
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
              <td>
                <StatusChip status={caseRecord.status} />
              </td>
              <td className="num mono">
                {caseRecord.open_exceptions > 0 && caseRecord.open_exceptions}
              </td>
              <td className="nowrap">
                <CaseFlags
                  screeningFlag={caseRecord.screening_flag}
                  agentFailed={caseRecord.agent_failed}
                />
              </td>
              <td className="nowrap">
                {caseRecord.started_at && time(caseRecord.started_at)}
              </td>
              <td className="num mono">{duration(caseRecord.seconds)}</td>
              <td className="num mono">{modelCost(caseRecord.model_cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Summary({ summary }: Readonly<{ summary: DispatchSummary }>) {
  const awaiting = summary.with_exceptions.length + summary.clean.length;
  return (
    <div className="dispatch-summary">
      <h3 id="dispatch-summary-title">When it finished</h3>
      <ul aria-labelledby="dispatch-summary-title">
        <li>
          {awaiting} awaiting review: {summary.with_exceptions.length} with
          exceptions and {summary.clean.length} clean.
        </li>
        <CaseLine label="With exceptions" cases={summary.with_exceptions} />
        <CaseLine label="Flagged by the screening" cases={summary.flagged} />
        <CaseLine label="Failed by the agent" cases={summary.agent_failed} />
        <CaseLine
          label="Left for the next dispatch"
          cases={summary.unfinished}
        />
      </ul>
    </div>
  );
}

function CaseLine({
  label,
  cases,
}: Readonly<{ label: string; cases: string[] }>) {
  if (cases.length === 0) return null;
  return (
    <li>
      {label}:{" "}
      {cases.map((caseId, index) => (
        <Fragment key={caseId}>
          {index > 0 && ", "}
          <CaseLink caseId={caseId} />
        </Fragment>
      ))}
    </li>
  );
}

function casesOnOtherProjects(count: number): string {
  return `${String(count)} ${count === 1 ? "case" : "cases"} on other projects`;
}
