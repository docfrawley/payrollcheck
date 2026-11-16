import type { ExceptionRecord } from "../api";
import { cents, exceptionStatusLabels } from "../format";
import { ownJudgment, whereOnPayroll } from "../judgment";
import { SeverityChip } from "./Chips";

// A case's exceptions, the latest submission's first, each with its rule,
// severity, where it is, what was expected and paid, its shortfall and what
// it cites, marked when the agent raised it on its own judgment.
export function ExceptionList({
  exceptions,
  latestSubmission,
}: Readonly<{ exceptions: ExceptionRecord[]; latestSubmission: number }>) {
  const ordered = [...exceptions].sort(
    (a, b) =>
      Number(b.submission_no === latestSubmission) -
      Number(a.submission_no === latestSubmission),
  );
  return (
    <section className="panel" aria-labelledby="exceptions-title">
      <h2 id="exceptions-title">Exceptions</h2>
      {ordered.length === 0 ? (
        <p className="muted">No exceptions.</p>
      ) : (
        <ul className="exceptions">
          {ordered.map((exception) => (
            <li
              key={exception.exception_id}
              className={`exception exception-${exception.status}`}
            >
              <p className="exception-head">
                <span className="mono">{exception.rule}</span>{" "}
                <SeverityChip severity={exception.severity} />{" "}
                {ownJudgment(exception) && (
                  <>
                    <span className="chip judgment">
                      Agent's own judgment
                    </span>{" "}
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
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
