import { Save, Send, Undo2 } from "lucide-react";
import { type ReactNode, useId, useState } from "react";
import { api, type Case } from "../api";
import type { Notice } from "../notices";
import { dateTime } from "../format";
import { resendable, reviewable } from "../judgment";
import { useAction } from "../useAction";
import { FormError } from "./FormError";

// The text a notice would send: the reviewer's edit, or the agent's draft.
const textOf = (notice: Notice | null) =>
  notice?.edited_text ?? notice?.draft ?? "";

// How the editor sends a notice: Send back, which returns a case awaiting
// review to its subcontractor, or Send again, which sends a returned case's
// notice once more and leaves it returned.
interface Sending {
  label: string;
  icon: ReactNode;
  // Sends the text the reviewer sees; the app refuses it if the notice has
  // changed since, as when the Copilot drafted it again.
  send: (caseId: string, text: string) => Promise<Case>;
}

const SEND_BACK: Sending = {
  label: "Send back",
  icon: <Undo2 />,
  send: api.sendBackCase,
};
const SEND_AGAIN: Sending = {
  label: "Send again",
  icon: <Send />,
  send: api.resendNotice,
};

function sendingOf(caseRecord: Case): Sending | undefined {
  if (reviewable(caseRecord)) return SEND_BACK;
  if (resendable(caseRecord)) return SEND_AGAIN;
  return undefined;
}

// The send-back notice to the subcontractor: the agent's or the Copilot's
// draft, which the reviewer edits in place, saves without sending, and sends
// with Send back, or, on a case returned to its subcontractor, Send again.
export function NoticePanel({
  caseRecord,
  onChanged,
}: Readonly<{ caseRecord: Case; onChanged: () => void }>) {
  const { notice } = caseRecord;
  const sending = sendingOf(caseRecord);
  return (
    <section className="panel" aria-labelledby="notice-title">
      <h2 id="notice-title">Send-back notice</h2>
      <NoticeHistory notice={notice} />
      {sending ? (
        <NoticeEditor
          key={`${String(notice?.submission_no)} ${notice?.drafted_at ?? ""}`}
          caseRecord={caseRecord}
          sending={sending}
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
        : "No draft"}
      {notice.edited_by &&
        notice.edited_at &&
        `; edited by ${notice.edited_by}, ${dateTime(notice.edited_at)}`}
      , for submission {notice.submission_no}.
    </p>
  );
}

function NoticeEditor({
  caseRecord,
  sending,
  onChanged,
}: Readonly<{ caseRecord: Case; sending: Sending; onChanged: () => void }>) {
  const id = useId();
  const caseId = caseRecord.case_id;
  const [text, setText] = useState(textOf(caseRecord.notice));
  const written = text.trim() !== "";
  const changed = text !== textOf(caseRecord.notice);
  // Saves the text when it changed, and sends it when asked. A failed send
  // leaves the saved text and reloads the case.
  const act = useAction(async (sendingIt: boolean) => {
    if (changed) await api.saveNotice(caseId, text);
    if (!sendingIt) {
      onChanged();
      return;
    }
    try {
      await sending.send(caseId, text);
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
          {sending.icon}
          {sending.label}
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
