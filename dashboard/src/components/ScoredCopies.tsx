import type { ExceptionMatch, LabelMatch, ScoredCase } from "../api";
import { cents, duration, modelCost } from "../format";
import { whereOnPayroll } from "../judgment";
import { CaseLink } from "./CaseLink";
import { LabelResultChip, MatchedChip, StatusChip } from "./Chips";
import { None } from "./None";
import { NoticeGrade } from "./NoticeGrade";

// Whether a copy was expected to be flagged by the screening, and was.
function screening(copy: ScoredCase): string {
  if (copy.screening_expected)
    return copy.screening_found ? "Expected and flagged" : "Expected, missed";
  return copy.screening_found ? "Flagged, not expected" : "";
}

// A copy the agent got something wrong on: a label missed, an exception that
// matches no label, or a screening it got wrong, flagging where no flag was
// expected or not flagging where one was.
const wentWrong = (copy: ScoredCase) =>
  copy.misses > 0 ||
  copy.false_exceptions > 0 ||
  copy.screening_expected !== copy.screening_found;

// Misses before shortfalls wrong before catches, and false exceptions before
// matched ones, keeping the backend's order otherwise.
const LABEL_ORDER: Record<LabelMatch["result"], number> = {
  missed: 0,
  shortfall_wrong: 1,
  caught: 2,
};

// What a label's money comes to: the shortfall expected, and what the agent
// raised when it differs, or nothing for a label with no money owed.
function labelMoney(label: LabelMatch): string | null {
  if (label.expected_shortfall_cents === null) return null;
  const expected = cents(label.expected_shortfall_cents);
  if (label.result === "shortfall_wrong" && label.shortfall_cents !== null)
    return `${expected} expected, ${cents(label.shortfall_cents)} raised`;
  return label.result === "missed" ? `${expected} expected` : expected;
}

function LabelMoney({ label }: Readonly<{ label: LabelMatch }>) {
  const money = labelMoney(label);
  if (money === null) return null;
  return (
    <>
      {" "}
      <span className="mono">{money}</span>
    </>
  );
}

function Labels({ labels }: Readonly<{ labels: LabelMatch[] }>) {
  if (labels.length === 0) return <None />;
  const ordered = [...labels].sort(
    (a, b) => LABEL_ORDER[a.result] - LABEL_ORDER[b.result],
  );
  return (
    <ul className="matches" aria-label="Labels">
      {ordered.map((label, index) => (
        <li key={`${label.rule} ${String(label.worker_id)} ${String(index)}`}>
          <LabelResultChip result={label.result} />{" "}
          <span className="mono">{label.rule}</span>{" "}
          {whereOnPayroll(label.worker_id, label.line_no)}
          <LabelMoney label={label} />
        </li>
      ))}
    </ul>
  );
}

function Exceptions({
  exceptions,
}: Readonly<{ exceptions: ExceptionMatch[] }>) {
  if (exceptions.length === 0) return <None />;
  const ordered = [...exceptions].sort(
    (a, b) => Number(a.matched) - Number(b.matched),
  );
  return (
    <ul className="matches" aria-label="Exceptions">
      {ordered.map((exception) => (
        <li key={exception.exception_id}>
          <MatchedChip matched={exception.matched} />{" "}
          <span className="mono">{exception.rule}</span>{" "}
          {whereOnPayroll(exception.worker_id, exception.line_no)}
          {exception.shortfall_cents !== null && (
            <>
              {" "}
              <span className="mono">{cents(exception.shortfall_cents)}</span>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}

// Each copy of a labeled payroll beside its labels, those the agent got wrong
// first and tinted.
export function ScoredCopies({ cases }: Readonly<{ cases: ScoredCase[] }>) {
  const ordered = [...cases].sort(
    (a, b) => Number(wentWrong(b)) - Number(wentWrong(a)),
  );
  return (
    <section className="panel" aria-labelledby="copies-title">
      <h2 id="copies-title">Copies</h2>
      <p className="muted small">
        Each copy of a labeled payroll beside its labels: each label caught,
        missed or caught with the wrong shortfall, and each exception the agent
        raised, matched to a label or false, and the judge's score of its draft
        notice on the rubric's four points. Copies with a miss, a false
        exception or a screening the agent got wrong come first, tinted.
      </p>
      <div className="table-scroll">
        <table className="table steady">
          <colgroup>
            <col className="col-case" />
            <col className="col-id" />
            <col className="col-status" />
            <col />
            <col />
            <col className="col-status" />
            <col />
            <col className="col-money" />
            <col className="col-time" />
          </colgroup>
          <thead>
            <tr>
              <th>Copy</th>
              <th>Of</th>
              <th>Status</th>
              <th>Labels</th>
              <th>Exceptions</th>
              <th>Screening</th>
              <th>Notice</th>
              <th className="num">Model cost</th>
              <th className="num">Time</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((copy) => (
              <tr
                key={copy.case_id}
                className={wentWrong(copy) ? "copy-off" : undefined}
              >
                <td className="nowrap">
                  <CaseLink caseId={copy.case_id} />
                </td>
                <td className="mono nowrap">{copy.copy_of}</td>
                <td>
                  <StatusChip status={copy.status} />
                </td>
                <td>
                  <Labels labels={copy.labels} />
                </td>
                <td>
                  <Exceptions exceptions={copy.exceptions} />
                </td>
                <td>{screening(copy)}</td>
                <td>
                  <NoticeGrade notice={copy.notice} />
                </td>
                <td className="num mono">{modelCost(copy.model_cost)}</td>
                <td className="num mono">{duration(copy.seconds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
