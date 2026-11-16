import { useReviewer } from "../reviewer";

// Says what the signed-in reviewer can't do and why, in place of the button
// that would do it.
export function NotAllowed({ action }: Readonly<{ action: string }>) {
  const reviewer = useReviewer();
  return (
    <p className="not-allowed">
      Only the compliance manager can {action}. {reviewer.name} can't.
    </p>
  );
}
