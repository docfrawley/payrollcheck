import type { NoticeGradeRecord, RubricPoint } from "../api";
import { NOT_GRADED } from "../measures";

// The rubric's four points, in the judge's order.
const POINTS: { point: RubricPoint; label: string }[] = [
  { point: "covers_every_exception", label: "Covers every exception" },
  { point: "amounts_match", label: "Amounts match the records" },
  { point: "plain_language", label: "Plain language" },
  { point: "no_legal_interpretation", label: "No legal interpretation" },
];

// A copy's notice as the judge graded it: its score and each point of the
// rubric, or why it has no score.
export function NoticeGrade({
  notice,
}: Readonly<{ notice: NoticeGradeRecord | null }>) {
  if (notice === null) return <span className="muted">No notice needed</span>;
  if (notice.result === "not_graded") return <>{NOT_GRADED}</>;
  if (notice.result === "no_notice")
    return (
      <>
        No notice, <span className="mono">{notice.score.toFixed(2)}</span>
      </>
    );
  return (
    <>
      Score <span className="mono">{notice.score.toFixed(2)}</span>
      <dl className="scores" aria-label="The judge's points">
        {POINTS.map(({ point, label }) => (
          <div key={point}>
            <dt>{label}</dt>
            <dd className="mono">{notice[point].toFixed(2)}</dd>
          </div>
        ))}
      </dl>
    </>
  );
}
