import type { Case } from "../api";
import { dateTime } from "../format";

// The notices sent to the subcontractor, newest first, each as the email it
// would be: to, subject, sender, time and body, with the agent's draft beside
// a notice the reviewer edited.
export function SentNotices({ caseRecord }: Readonly<{ caseRecord: Case }>) {
  if (caseRecord.sent_notices.length === 0) return null;
  return (
    <section className="panel" aria-labelledby="sent-title">
      <h2 id="sent-title">Sent to the subcontractor</h2>
      {caseRecord.sent_notices.map((sent) => (
        <article
          key={sent.outbox_id}
          className="email"
          aria-label={`Notice for submission ${String(sent.submission_no)}`}
        >
          <dl className="email-head">
            <div>
              <dt>To</dt>
              <dd className="mono">{sent.to_address}</dd>
            </div>
            <div>
              <dt>From</dt>
              <dd>{sent.sent_by}</dd>
            </div>
            <div>
              <dt>Sent</dt>
              <dd>{dateTime(sent.sent_at)}</dd>
            </div>
            <div>
              <dt>Subject</dt>
              <dd>{sent.subject}</dd>
            </div>
          </dl>
          <p className="notice">{sent.body}</p>
          {sent.draft && sent.draft !== sent.body && (
            <details>
              <summary>The agent's draft</summary>
              <p className="notice">{sent.draft}</p>
            </details>
          )}
        </article>
      ))}
    </section>
  );
}
