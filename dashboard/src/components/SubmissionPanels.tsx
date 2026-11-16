import type { PayrollLine, Submission } from "../api";
import { cents, date } from "../format";

// Each submission of a case's payroll, the latest first: its certification and
// its lines.
export function SubmissionPanels({
  submissions,
}: Readonly<{ submissions: Submission[] }>) {
  return (
    <>
      {[...submissions].reverse().map((submission) => (
        <SubmissionPanel
          key={submission.submission_no}
          submission={submission}
        />
      ))}
    </>
  );
}

function SubmissionPanel({ submission }: Readonly<{ submission: Submission }>) {
  const { certification } = submission;
  const titleId = `submission-${String(submission.submission_no)}-title`;
  return (
    <section className="panel" aria-labelledby={titleId}>
      <h2 id={titleId}>Submission {submission.submission_no}</h2>
      <dl className="facts">
        <div>
          <dt>Contractor</dt>
          <dd>{certification.contractor_name}</dd>
        </div>
        <div>
          <dt>Payroll number</dt>
          <dd className="mono">{submission.payroll_no}</dd>
        </div>
        <div>
          <dt>Received</dt>
          <dd>{date(submission.received_on)}</dd>
        </div>
        <div>
          <dt>Wages paid</dt>
          <dd>{date(submission.wage_payment_date)}</dd>
        </div>
        <div>
          <dt>Signed</dt>
          <dd>
            {certification.signed_by || "Not signed"}
            {certification.signed_on && `, ${date(certification.signed_on)}`}
          </dd>
        </div>
        <div>
          <dt>File</dt>
          <dd className="mono">{submission.file_name}</dd>
        </div>
        {certification.payroll_notes && (
          <div className="fact-wide">
            <dt>Notes</dt>
            <dd>{certification.payroll_notes}</dd>
          </div>
        )}
      </dl>
      {certification.no_work_week ? (
        <p className="muted">A No Work Week filing, with no lines.</p>
      ) : (
        <Lines lines={submission.lines} />
      )}
    </section>
  );
}

function Lines({ lines }: Readonly<{ lines: PayrollLine[] }>) {
  return (
    <div className="table-scroll">
      <table className="table">
        <thead>
          <tr>
            <th>Line</th>
            <th>Worker</th>
            <th>Classification</th>
            <th className="num">Hours</th>
            <th className="num">Overtime</th>
            <th className="num">Base rate</th>
            <th className="num">Fringe</th>
            <th className="num">Gross</th>
            <th className="num">Net</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line, index) => (
            <tr key={line.worker_id}>
              <td className="num mono">{index + 1}</td>
              <td>
                <span className="mono">{line.worker_id}</span>{" "}
                {line.worker_name}
              </td>
              <td>
                {line.classification}
                {line.apprentice_level !== null &&
                  `, apprentice level ${String(line.apprentice_level)}`}
              </td>
              <td className="num mono">{line.total_hours}</td>
              <td className="num mono">{line.overtime_hours}</td>
              <td className="num mono">{cents(line.base_rate)}</td>
              <td className="num mono">
                {cents(line.fringe_rate + line.fringe_cash)}
              </td>
              <td className="num mono">{cents(line.gross)}</td>
              <td className="num mono">{cents(line.net)}</td>
              <td className="small">{line.line_notes}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
