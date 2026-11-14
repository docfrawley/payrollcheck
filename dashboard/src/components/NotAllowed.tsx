import { api } from "../api";
import { money } from "../format";
import { useReviewer } from "../reviewer";
import { useLoad } from "../useLoad";

// Says what the signed-in reviewer can't do and why, in place of the button
// that would do it.
export function NotAllowed({ action }: Readonly<{ action: string }>) {
  const reviewer = useReviewer();
  const { data: settings } = useLoad(api.getSettings);
  return (
    <p className="not-allowed">
      {settings && (
        <>
          Only a reviewer who can sign off payouts over{" "}
          <span className="mono">{money(settings.current.approval_limit)}</span>{" "}
          can {action}. {reviewer.name} can't.
        </>
      )}
    </p>
  );
}
