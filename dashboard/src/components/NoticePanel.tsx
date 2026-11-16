import type { Notice } from "../api";
import { dateTime } from "../format";

// The draft send-back notice to the subcontractor, as the agent wrote it.
export function NoticePanel({ notice }: Readonly<{ notice: Notice | null }>) {
  return (
    <section className="panel" aria-labelledby="notice-title">
      <h2 id="notice-title">Send-back notice</h2>
      {notice === null || notice.draft === "" ? (
        <p className="muted">No notice drafted.</p>
      ) : (
        <>
          <p className="muted small">
            Drafted by {notice.drafted_by}, {dateTime(notice.drafted_at)}, for
            submission {notice.submission_no}.
          </p>
          <p className="notice">{notice.draft}</p>
        </>
      )}
    </section>
  );
}
