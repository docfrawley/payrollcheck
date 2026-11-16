import type { Case } from "../api";
import type { ExceptionRecord, Override } from "../exceptions";
import {
  cents,
  dateTime,
  exceptionStatusLabels,
  overrideLabels,
} from "../format";
import { reviewable, ownJudgment, whereOnPayroll } from "../judgment";
import { SeverityChip } from "./Chips";
import { ExceptionOverride } from "./ExceptionOverride";

// A case's exceptions, the latest submission's first, each with its rule,
// severity, where it is, what was expected and paid, its shortfall and what
// it cites, marked when the agent raised it on its own judgment, with its
// overrides, and Dismiss or Restore while the reviewer may override it.
export function ExceptionList({
  caseRecord,
  onChanged,
}: Readonly<{ caseRecord: Case; onChanged: () => void }>) {
  const { exceptions, latest_submission_no: latestSubmission } = caseRecord;
  const mayOverride = reviewable(caseRecord);
  // Each submission's exceptions under it, the latest first, and the latest
  // even with none, once an earlier one has some.
  const submissionNos =
    exceptions.length === 0
      ? []
      : [
          ...new Set([
            latestSubmission,
            ...exceptions.map((exception) => exception.submission_no),
          ]),
        ].sort((a, b) => b - a);
  return (
    <section className="panel" aria-labelledby="exceptions-title">
      <h2 id="exceptions-title">Exceptions</h2>
      {exceptions.length === 0 && <p className="muted">No exceptions.</p>}
      {submissionNos.map((submissionNo) => {
        const theirs = exceptions.filter(
          (exception) => exception.submission_no === submissionNo,
        );
        return (
          <section
            key={submissionNo}
            className="exception-group"
            aria-label={`Submission ${String(submissionNo)}`}
          >
            {submissionNos.length > 1 && (
              <h3>
                Submission {submissionNo}
                {submissionNo === latestSubmission
                  ? ", the latest"
                  : ", before a correction"}
              </h3>
            )}
            {theirs.length === 0 ? (
              <p className="muted">No exceptions.</p>
            ) : (
              <ul className="exceptions">
                {theirs.map((exception) => (
                  <ExceptionItem
                    key={exception.exception_id}
                    caseRecord={caseRecord}
                    exception={exception}
                    mayOverride={
                      mayOverride && submissionNo === latestSubmission
                    }
                    onChanged={onChanged}
                  />
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </section>
  );
}

// One exception, with its overrides, and Dismiss or Restore while the reviewer
// may override it.
function ExceptionItem({
  caseRecord,
  exception,
  mayOverride,
  onChanged,
}: Readonly<{
  caseRecord: Case;
  exception: ExceptionRecord;
  mayOverride: boolean;
  onChanged: () => void;
}>) {
  return (
    <li className={`exception exception-${exception.status}`}>
      <p className="exception-head">
        <span className="mono">{exception.rule}</span>{" "}
        <SeverityChip severity={exception.severity} />{" "}
        {ownJudgment(exception) && (
          <>
            <span className="chip judgment">Agent's own judgment</span>{" "}
          </>
        )}
        <span className="muted small">
          {exceptionStatusLabels[exception.status]}, submission{" "}
          {exception.submission_no}
        </span>
      </p>
      <dl className="facts">
        <div>
          <dt>Where</dt>
          <dd className="mono">
            {whereOnPayroll(exception.worker_id, exception.line_no)}
          </dd>
        </div>
        {exception.expected && (
          <div>
            <dt>Expected</dt>
            <dd>{exception.expected}</dd>
          </div>
        )}
        {exception.actual && (
          <div>
            <dt>Actual</dt>
            <dd>{exception.actual}</dd>
          </div>
        )}
        {exception.shortfall_cents !== null && (
          <div>
            <dt>Shortfall</dt>
            <dd className="mono">{cents(exception.shortfall_cents)}</dd>
          </div>
        )}
        <div className="fact-wide">
          <dt>Citation</dt>
          <dd>{exception.citation}</dd>
        </div>
        <div>
          <dt>Raised by</dt>
          <dd>{exception.raised_by}</dd>
        </div>
      </dl>
      <OverrideLog
        overrides={caseRecord.overrides.filter(
          (override) => override.exception_id === exception.exception_id,
        )}
      />
      {mayOverride && exception.status !== "superseded" && (
        <ExceptionOverride
          // A new form once it's dismissed or restored.
          key={exception.status}
          caseId={caseRecord.case_id}
          exception={exception}
          onDone={onChanged}
        />
      )}
    </li>
  );
}

// Who overrode an exception, when and why, oldest first.
function OverrideLog({ overrides }: Readonly<{ overrides: Override[] }>) {
  if (overrides.length === 0) return null;
  return (
    <ul className="override-log" aria-label="Overrides">
      {overrides.map((override) => (
        <li key={override.override_id}>
          <span className="small">
            {overrideLabels[override.kind]} by {override.reviewer_name},{" "}
            {dateTime(override.created_at)}:
          </span>{" "}
          {override.reason}
        </li>
      ))}
    </ul>
  );
}
