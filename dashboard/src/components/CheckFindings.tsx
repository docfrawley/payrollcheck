import { Ban, CircleAlert, ListChecks, Scale } from "lucide-react";
import type { Candidate, Case } from "../api";
import type { ExceptionRecord } from "../exceptions";
import { cents, exceptionStatusLabels } from "../format";
import { exceptionFor, ownJudgment, whereOnPayroll } from "../judgment";

// What the check tools found on the current attempt, check by check in the
// order they ran, beside the payroll agent's judgment of each finding: raised
// as an exception or dismissed with its reason. Then the exceptions the agent
// raised on the latest submission on its own judgment, which no check found.
// A case no check has run on, such as one the screening flagged, shows
// nothing.
export function CheckFindings({ caseRecord }: Readonly<{ caseRecord: Case }>) {
  const { checks_run: checks, candidates, exceptions } = caseRecord;
  const own = exceptions.filter(
    (exception) =>
      ownJudgment(exception) &&
      exception.submission_no === caseRecord.latest_submission_no &&
      exception.status !== "superseded",
  );
  if (checks.length === 0 && own.length === 0) return null;
  return (
    <section className="panel" aria-labelledby="checks-title">
      <h2 id="checks-title">Checks and judgment</h2>
      {checks.length > 0 && (
        <ol className="checks" aria-label="Checks run">
          {checks.map((check) => {
            const found = candidates.filter((c) => c.check === check);
            return (
              <li key={check} className="check" aria-label={check}>
                <p className="check-name">
                  <ListChecks aria-hidden />
                  <span className="mono">{check}</span>
                  {found.length === 0 && (
                    <span className="muted"> Nothing found</span>
                  )}
                </p>
                {found.length > 0 && (
                  <ul className="findings">
                    {found.map((candidate) => (
                      <Finding
                        key={candidate.candidate_id}
                        candidate={candidate}
                        exceptions={exceptions}
                      />
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ol>
      )}
      {own.length > 0 && (
        <>
          <h3>The agent's own judgment</h3>
          <ul className="findings">
            {own.map((exception) => (
              <li key={exception.exception_id} className="finding">
                <p>
                  <Scale aria-hidden />
                  <span className="mono">{exception.rule}</span>{" "}
                  {whereOnPayroll(exception.worker_id, exception.line_no)}
                </p>
                <p className="small muted">
                  Raised with no check behind it: {exception.citation}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function Finding({
  candidate,
  exceptions,
}: Readonly<{ candidate: Candidate; exceptions: ExceptionRecord[] }>) {
  const raised = exceptionFor(candidate, exceptions);
  return (
    <li className="finding">
      <p>
        <span className="mono">{candidate.rule}</span>{" "}
        {whereOnPayroll(candidate.worker_id, candidate.line_no)}
        {candidate.shortfall_cents !== null && (
          <>
            , <span className="mono">{cents(candidate.shortfall_cents)}</span>{" "}
            short
          </>
        )}
      </p>
      {candidate.dismissed_because !== null && (
        <p className="finding-call dismissed">
          <Ban aria-hidden />
          <span>Dismissed: {candidate.dismissed_because}</span>
        </p>
      )}
      {raised && (
        <p className="finding-call raised">
          <CircleAlert aria-hidden />
          <span>
            Raised as an exception
            {raised.status === "open"
              ? ""
              : `, now ${exceptionStatusLabels[raised.status].toLowerCase()}`}
          </span>
        </p>
      )}
      {candidate.dismissed_because === null && !raised && (
        <p className="finding-call muted">Not judged yet</p>
      )}
    </li>
  );
}
