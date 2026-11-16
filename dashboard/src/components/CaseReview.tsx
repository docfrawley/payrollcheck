import { Signature, Undo2 } from "lucide-react";
import { api, type Case } from "../api";
import { cents, date } from "../format";
import { ActionForm } from "./ActionForm";

// Where the case stands, in a sentence.
function progress(caseRecord: Case): string {
  const reviewed = caseRecord.reviewed_on
    ? ` on ${date(caseRecord.reviewed_on)}`
    : "";
  switch (caseRecord.status) {
    case "received":
      return caseRecord.attempts > 0
        ? "Back in the queue after a failed attempt. The next dispatch checks it."
        : "The payroll agent hasn't checked this payroll yet. The next dispatch checks it.";
    case "in_progress":
      return "The payroll agent is checking this payroll.";
    case "awaiting_review":
      if (caseRecord.agent_failed)
        return `The payroll agent couldn't finish this case in ${String(caseRecord.attempts)} attempts, so it's for a reviewer to check by hand.`;
      if (caseRecord.screening_flag)
        return "The screening found an instruction in this payroll, so the payroll agent never read it. It's for a reviewer to check by hand.";
      return "The payroll agent has checked this payroll and it's waiting for a reviewer.";
    case "accepted":
      return `Signed off${reviewed}.`;
    case "returned_to_sub":
      return `Sent back to the subcontractor${reviewed}.`;
  }
}

function openExceptions(count: number): string {
  if (count === 0) return "No open exceptions";
  return `${String(count)} open ${count === 1 ? "exception" : "exceptions"}`;
}

// A case's review: where it stands, what its open exceptions come to, and
// Sign off and Send back while it awaits review, unless it's an evaluation's
// copy, which nobody answers.
export function CaseReview({
  caseRecord,
  onAnswered,
}: Readonly<{ caseRecord: Case; onAnswered: () => void }>) {
  const { case_id: caseId } = caseRecord;
  const awaiting = caseRecord.status === "awaiting_review";
  return (
    <section className="panel" aria-labelledby="review-title">
      <h2 id="review-title">Review</h2>
      <p>{progress(caseRecord)}</p>
      <p className="muted">
        {openExceptions(caseRecord.open_exceptions)}
        {caseRecord.shortfall_cents > 0 && (
          <>
            , <span className="mono">{cents(caseRecord.shortfall_cents)}</span>{" "}
            short
          </>
        )}
        .
      </p>
      {awaiting && caseRecord.evaluation_id && (
        <p className="muted small">
          A copy in an evaluation can't be signed off or sent back.
        </p>
      )}
      {awaiting && !caseRecord.evaluation_id && (
        <div className="review-answers">
          <ActionForm
            label="Sign off"
            icon={<Signature />}
            action={() => api.signOffCase(caseId).then(onAnswered)}
          />
          <ActionForm
            label="Send back"
            icon={<Undo2 />}
            action={() => api.sendBackCase(caseId).then(onAnswered)}
          />
        </div>
      )}
    </section>
  );
}
