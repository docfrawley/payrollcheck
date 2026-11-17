import type { ParameterChange } from "../changes";
import { inUnit } from "../format";

// Each tunable parameter a version or a proposal changes, before and after.
export function ParameterChanges({
  changes,
}: Readonly<{ changes: ParameterChange[] }>) {
  return (
    <>
      {changes.map((change, index) => (
        <span key={change.name}>
          {index > 0 && ", "}
          {change.label.toLowerCase()}{" "}
          <span className="mono">{inUnit(change.unit, change.before)}</span> to{" "}
          <span className="mono">{inUnit(change.unit, change.after)}</span>
        </span>
      ))}
    </>
  );
}
