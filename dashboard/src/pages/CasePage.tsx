import { ShieldAlert } from "lucide-react";
import { useCallback } from "react";
import { Link, useParams } from "react-router";
import { api, type Case } from "../api";
import { CaseFlags, StatusChip } from "../components/Chips";
import { CaseReview } from "../components/CaseReview";
import { ContextUsed } from "../components/ContextUsed";
import { ExceptionList } from "../components/ExceptionList";
import { NoticePanel } from "../components/NoticePanel";
import { StateMessage } from "../components/StateMessage";
import { PageHeader } from "../components/PageHeader";
import { StepList } from "../components/StepList";
import { SubmissionPanels } from "../components/SubmissionPanels";
import { date } from "../format";
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
        title={caseRecord.subcontractor_name}
        status={
          <>
            <StatusChip status={caseRecord.status} />
            <CaseFlags
              screeningFlag={caseRecord.screening_flag}
              agentFailed={caseRecord.agent_failed}
            />
          </>
        }
        lead={
          caseRecord.evaluation_id ? (
            <>
              A copy of <span className="mono">{caseRecord.copy_of}</span> in an{" "}
              <Link to={evaluationPage(caseRecord.evaluation_id)}>
                evaluation
              </Link>
            </>
          ) : (
            `${caseRecord.project_name}, week ending ${date(caseRecord.week_ending)}`
          )
        }
      />
      {/* The agent's steps grow at the end of the right column, and the context
          it used at the end of the left, so neither moves anything as the
          page refreshes. */}
      <div className="case-layout">
        <div className="column">
          <CaseDetails caseRecord={caseRecord} />
          <Screening caseRecord={caseRecord} />
          <SubmissionPanels submissions={caseRecord.submissions} />
          <ContextUsed steps={steps.data} />
        </div>
        <div className="column">
          <CaseReview caseRecord={caseRecord} onAnswered={reload} />
          <ExceptionList
            exceptions={caseRecord.exceptions}
            latestSubmission={caseRecord.latest_submission_no}
          />
          <NoticePanel notice={caseRecord.notice} />
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
          <dt>Subcontractor</dt>
          <dd>
            {caseRecord.subcontractor_name}{" "}
            <span className="mono muted">{caseRecord.subcontractor_id}</span>
          </dd>
        </div>
        <div>
          <dt>Project</dt>
          <dd>
            {caseRecord.project_name}{" "}
            <span className="mono muted">{caseRecord.project_id}</span>
          </dd>
        </div>
        <div>
          <dt>Week ending</dt>
          <dd>{date(caseRecord.week_ending)}</dd>
        </div>
        <div>
          <dt>Submissions</dt>
          <dd className="mono">{caseRecord.submissions.length}</dd>
        </div>
        {caseRecord.reviewed_by && (
          <div>
            <dt>Reviewed by</dt>
            <dd className="mono">{caseRecord.reviewed_by}</dd>
          </div>
        )}
      </dl>
    </section>
  );
}

// What the screening for hidden instructions found, once it flagged the case.
function Screening({ caseRecord }: Readonly<{ caseRecord: Case }>) {
  if (!caseRecord.screening_flag) return null;
  return (
    <section className="panel" aria-labelledby="screening-title">
      <h2 id="screening-title">Screening</h2>
      <p className="screening">
        <ShieldAlert aria-hidden />
        <span>
          {caseRecord.screening_reason ??
            "The screening found an instruction in this payroll."}
        </span>
      </p>
    </section>
  );
}
