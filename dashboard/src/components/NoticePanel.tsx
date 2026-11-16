import { Save, Undo2 } from "lucide-react";
import { useId, useState } from "react";
import { api, type Case } from "../api";
import type { Notice } from "../notices";
import { dateTime } from "../format";
import { reviewable } from "../judgment";
import { useAction } from "../useAction";
import { FormError } from "./FormError";

// The text a notice would send: the reviewer's edit, or the agent's draft.
const textOf = (notice: Notice | null) =>
  notice?.edited_text ?? notice?.draft ?? "";

// The send-back notice to the subcontractor: the agent's draft, which the
// reviewer edits in place, saves without sending, and sends with Send back,
// which returns the case to its subcontractor.
export function NoticePanel({
  caseRecord,
  onChanged,
}: Readonly<{ caseRecord: Case; onChanged: () => void }>) {
  const { notice } = caseRecord;
  return (
    <section className="panel" aria-labelledby="notice-title">
      <h2 id="notice-title">Send-back notice</h2>
      <NoticeHistory notice={notice} />
      {reviewable(caseRecord) ? (
        <NoticeEditor
          key={notice?.submission_no}
          caseRecord={caseRecord}
          onChanged={onChanged}
        />
      ) : (
        <NoticeText text={textOf(notice)} />
      )}
    </section>
  );
}

function NoticeHistory({ notice }: Readonly<{ notice: Notice | null }>) {
  if (!notice) return null;
  return (
    <p className="muted small">
      {notice.drafted_by && notice.drafted_at
        ? `Drafted by ${notice.drafted_by}, ${dateTime(notice.drafted_at)}`
        : "No draft from the agent"}
      {notice.edited_by &&
        notice.edited_at &&
        `; edited by ${notice.edited_by}, ${dateTime(notice.edited_at)}`}
      , for submission {notice.submission_no}.
    </p>
  );
}

function NoticeEditor({
  caseRecord,
  onChanged,
}: Readonly<{ caseRecord: Case; onChanged: () => void }>) {
  const id = useId();
  const caseId = caseRecord.case_id;
  const [text, setText] = useState(textOf(caseRecord.notice));
  const written = text.trim() !== "";
  const changed = text !== textOf(caseRecord.notice);
  // Saves the text when it changed, and sends the case back with it when asked.
  // A failed send leaves the saved text and reloads the case.
  const act = useAction(async (sendingBack: boolean) => {
    if (changed) await api.saveNotice(caseId, text);
    if (!sendingBack) {
      onChanged();
      return;
    }
    try {
      await api.sendBackCase(caseId);
    } finally {
      onChanged();
    }
  });
  const ready = written && !act.sending;
  return (
    <form
      className="notice-editor"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready) void act.run(true);
      }}
    >
      <label htmlFor={id}>The notice to the subcontractor</label>
      <textarea
        id={id}
        rows={8}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
        }}
      />
      <div className="review-answers">
        <button
          type="button"
          className="button quiet"
          aria-disabled={!ready || !changed}
          onClick={() => {
            if (ready && changed) void act.run(false);
          }}
        >
          <Save />
          Save
        </button>
        <button type="submit" className="button" aria-disabled={!ready}>
          <Undo2 />
          Send back
        </button>
      </div>
      {act.error && <FormError>{act.error}</FormError>}
    </form>
  );
}

function NoticeText({ text }: Readonly<{ text: string }>) {
  if (!text) return <p className="muted">No notice drafted.</p>;
  return <p className="notice">{text}</p>;
}
