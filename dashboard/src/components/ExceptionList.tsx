import type { ExceptionRecord, ExceptionStatus } from "../api";
import { cents } from "../format";
import { SeverityChip } from "./Chips";

const STATUS_LABELS: Record<ExceptionStatus, string> = {
  open: "Open",
  dismissed: "Dismissed",
  superseded: "Superseded",
};

// Where an exception is on the payroll: the worker and line, or the whole
// payroll for a rule about the certification.
function where(exception: ExceptionRecord): string {
  if (exception.worker_id === null) return "The whole payroll";
  const line =
    exception.line_no === null ? "" : `, line ${String(exception.line_no)}`;
  return `${exception.worker_id}${line}`;
}

// A case's exceptions, the latest submission's first, each with its rule,
// severity, where it is, what was expected and paid, its shortfall and what
// it cites.
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
                <span className="muted small">
                  {STATUS_LABELS[exception.status]}, submission{" "}
                  {exception.submission_no}
                </span>
              </p>
              <dl className="facts">
                <div>
                  <dt>Where</dt>
                  <dd className="mono">{where(exception)}</dd>
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
