import { Ban, RotateCcw } from "lucide-react";
import { useId, useState } from "react";
import { api } from "../api";
import type { ExceptionRecord } from "../exceptions";
import { useAction } from "../useAction";
import { FormError } from "./FormError";
import { ReasonForm } from "./ReasonForm";

// Dismiss an open exception, or restore a dismissed one, with the reviewer's
// reason, which the override log keeps with their name and the time.
export function ExceptionOverride({
  caseId,
  exception,
  onDone,
}: Readonly<{
  caseId: string;
  exception: ExceptionRecord;
  onDone: () => void;
}>) {
  const id = useId();
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const dismissing = exception.status === "open";
  const verb = dismissing ? "Dismiss" : "Restore";
  const icon = dismissing ? <Ban /> : <RotateCcw />;
  const override = useAction(() =>
    (dismissing ? api.dismissException : api.restoreException)(
      caseId,
      exception.exception_id,
      reason,
    ).then(onDone),
  );

  if (!asking)
    return (
      <button
        type="button"
        className="button quiet"
        onClick={() => {
          setAsking(true);
        }}
      >
        {icon}
        {verb}
      </button>
    );
  return (
    <ReasonForm
      id={id}
      label={dismissing ? "Why dismiss it?" : "Why restore it?"}
      hint="The override log keeps your reason with your name and the time."
      submitLabel={
        <>
          {icon}
          {verb}
        </>
      }
      value={reason}
      onChange={setReason}
      sending={override.sending}
      onSubmit={() => void override.run()}
    >
      {override.error && <FormError>{override.error}</FormError>}
    </ReasonForm>
  );
}
