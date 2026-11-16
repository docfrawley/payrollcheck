import type { VersionScores } from "../api";
import { percent } from "../format";

const NOT_SCORED = "Not scored yet";

// A version's catch rate on the held-out set, once rounds have scored it.
export function HeldOutCatchRate({
  scores,
}: Readonly<{ scores: VersionScores }>) {
  return scores.held_out ? (
    <span className="mono">{percent(scores.held_out.catch_rate)}</span>
  ) : (
    <span className="muted">{NOT_SCORED}</span>
  );
}
