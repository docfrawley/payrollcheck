import type { Case, Decision, Payment } from "../api";
import { money, time } from "../format";
import { useReviewer } from "../reviewer";
import { DecisionDetails } from "./DecisionDetails";
import { NotAllowed } from "./NotAllowed";
import { SendBackForm } from "./SendBackForm";
import { SignOffForm } from "./SignOffForm";

type SignOff = Pick<Payment, "signed_off_by" | "signed_off_at">;

function whoAndWhen({ signed_off_by, signed_off_at }: SignOff): string | null {
  return signed_off_by && signed_off_at
    ? `${signed_off_by} at ${time(signed_off_at)}`
    : null;
}

function progress(caseRecord: Case): string {
  if (caseRecord.status === "in_progress")
    return "The agent is working on this case.";
  if (caseRecord.status === "sent_back")
    return "Sent back to the agent, which hasn't taken it up yet. The next dispatch works on it.";
  if (caseRecord.status === "left_for_reviewer")
    return `The agent couldn't finish this case in ${String(caseRecord.attempts)} attempts, so it's left for a reviewer.`;
  if (caseRecord.attempts > 0)
    return "Back in the queue after a failed attempt.";
  return "The agent hasn't started on this case.";
}

export function DecisionPanel({
  caseRecord,
  onAnswered,
}: Readonly<{ caseRecord: Case; onAnswered: () => void }>) {
  const { decision, payment } = caseRecord;
  const paidSignedOff = payment && whoAndWhen(payment);

  return (
    <section className="panel" aria-labelledby="decision-title">
      <h2 id="decision-title">Decision</h2>
      {!decision && <p className="muted">{progress(caseRecord)}</p>}
      {decision && <DecisionDetails decision={decision} />}
      {payment && (
        <p className="payment">
          Paid <span className="mono">{money(payment.amount)}</span>
          {paidSignedOff && `, signed off by ${paidSignedOff}`}
        </p>
      )}
      {decision?.decision === "approve" &&
        !payment &&
        caseRecord.status === "in_progress" && (
          <p className="payment">Waiting for the agent to pay it.</p>
        )}
      {decision && caseRecord.status === "waiting_for_sign_off" && (
        <HeldPayment
          caseRecord={caseRecord}
          decision={decision}
          onAnswered={onAnswered}
        />
      )}
    </section>
  );
}

// Why a payment waits for a reviewer's sign-off: it's over the approval limit,
// or the Gateway refused it.
function WhyHeld({ decision }: Readonly<{ decision: Decision }>) {
  const amount = <span className="mono">{money(decision.payout)}</span>;
  if (decision.gateway_refusal)
    return (
      <>
        <p>
          The Gateway refused the payment of {amount}, so it waits for a
          reviewer's sign-off.
        </p>
        <p className="small muted">{decision.gateway_refusal}</p>
      </>
    );
  return (
    <p>
      The payment of {amount} is over the approval limit and waits for a
      reviewer's sign-off.
    </p>
  );
}

// A payment over the limit or refused by the Gateway, which waits for a
// reviewer to sign it off or send it back, unless the case is an evaluation's
// copy, which nobody can answer.
function HeldPayment({
  caseRecord,
  decision,
  onAnswered,
}: Readonly<{ caseRecord: Case; decision: Decision; onAnswered: () => void }>) {
  const reviewer = useReviewer();
  if (caseRecord.evaluation_id)
    return (
      <p className="payment">
        Held for sign-off. In an evaluation this counts as finished, and a copy
        can't be signed off.
      </p>
    );
  return (
    <div className="sign-off">
      <WhyHeld decision={decision} />
      {reviewer.can_approve_over_limit ? (
        <div className="held-answers">
          <SignOffForm caseId={caseRecord.case_id} onSignedOff={onAnswered} />
          <SendBackForm caseId={caseRecord.case_id} onSentBack={onAnswered} />
        </div>
      ) : (
        <NotAllowed action="sign this off or send it back" />
      )}
    </div>
  );
}
