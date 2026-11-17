import type { ParameterValue } from "../changes";
import { inUnit } from "../format";

// A version's tunable parameters, each a fact of its own.
export function ParameterValues({
  parameters,
}: Readonly<{ parameters: ParameterValue[] }>) {
  return (
    <>
      {parameters.map((parameter) => (
        <div key={parameter.name}>
          <dt>{parameter.label}</dt>
          <dd className="mono">{inUnit(parameter.unit, parameter.value)}</dd>
        </div>
      ))}
    </>
  );
}
