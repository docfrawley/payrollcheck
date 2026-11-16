import { CaseLink } from "./CaseLink";

// The cases behind a change, each linking to its page.
export function MotivatingCases({ caseIds }: Readonly<{ caseIds: string[] }>) {
  if (caseIds.length === 0) return <span className="muted">None</span>;
  return (
    <ul className="inline-list">
      {caseIds.map((caseId) => (
        <li key={caseId}>
          <CaseLink caseId={caseId} />
        </li>
      ))}
    </ul>
  );
}
