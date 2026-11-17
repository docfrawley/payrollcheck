import type { Criterion } from "../api";
import { MetChip } from "./Chips";

// The success criteria the business agreed, each with its figure on this
// development-set evaluation and whether it's met.
export function SuccessCriteria({
  criteria,
}: Readonly<{ criteria: Criterion[] }>) {
  return (
    <section className="panel" aria-labelledby="criteria-title">
      <h2 id="criteria-title">Success criteria</h2>
      <ol className="criteria">
        {criteria.map((criterion) => (
          <li key={criterion.title}>
            <MetChip met={criterion.met} /> {criterion.title}
            <p className="mono small">{criterion.figure}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
