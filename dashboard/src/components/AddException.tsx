import { Plus } from "lucide-react";
import { useId, useState } from "react";
import { api, type Case } from "../api";
import type { RuleEntry } from "../exceptions";
import { severityLabels, shortfallInCents } from "../format";
import { useLoad } from "../useLoad";
import { ActionForm } from "./ActionForm";
import { StateMessage } from "./StateMessage";

// Adds an exception the agent missed to the latest submission: a rule from the
// catalogue, the worker's line for a rule found on one, what was expected and
// paid, a shortfall for a rule that carries money, and the reviewer's reason.
export function AddException({
  caseRecord,
  onAdded,
}: Readonly<{ caseRecord: Case; onAdded: () => void }>) {
  const rules = useLoad(api.listRules);
  return (
    <section className="panel" aria-labelledby="add-exception-title">
      <h2 id="add-exception-title">Add an exception</h2>
      {rules.data ? (
        <AddForm caseRecord={caseRecord} rules={rules.data} onAdded={onAdded} />
      ) : (
        <StateMessage error={rules.error} />
      )}
    </section>
  );
}

function AddForm({
  caseRecord,
  rules,
  onAdded,
}: Readonly<{ caseRecord: Case; rules: RuleEntry[]; onAdded: () => void }>) {
  const id = useId();
  const [code, setCode] = useState(rules[0]?.rule ?? "");
  const [line, setLine] = useState(1);
  const [expected, setExpected] = useState("");
  const [actual, setActual] = useState("");
  const [shortfall, setShortfall] = useState("");
  const [reason, setReason] = useState("");
  const rule = rules.find((entry) => entry.rule === code);
  const latest = caseRecord.submissions.at(-1);
  const lines = latest?.lines ?? [];
  const cents = shortfallInCents(shortfall);
  const written = [expected, actual, reason].every((text) => text.trim());
  const ready =
    rule !== undefined &&
    written &&
    (!rule.worker || lines.length > 0) &&
    (!rule.money || cents !== undefined);

  async function add() {
    if (!rule) return;
    await api.addException(caseRecord.case_id, {
      rule: rule.rule,
      worker_id: rule.worker ? (lines[line - 1]?.worker_id ?? null) : null,
      line_no: rule.worker ? line : null,
      expected,
      actual,
      shortfall_cents: rule.money ? (cents ?? null) : null,
      reason,
    });
    setExpected("");
    setActual("");
    setShortfall("");
    setReason("");
    onAdded();
  }

  return (
    <ActionForm
      label="Add the exception"
      icon={<Plus />}
      ready={ready}
      action={add}
    >
      <div className="add-exception">
        <label htmlFor={`${id}-rule`}>Rule</label>
        <select
          id={`${id}-rule`}
          value={code}
          onChange={(event) => {
            setCode(event.target.value);
          }}
        >
          {rules.map((entry) => (
            <option key={entry.rule} value={entry.rule}>
              {entry.rule} ({severityLabels[entry.severity]})
            </option>
          ))}
        </select>
        {rule?.worker && (
          <>
            <label htmlFor={`${id}-line`}>Worker and line</label>
            <select
              id={`${id}-line`}
              value={line}
              onChange={(event) => {
                setLine(Number(event.target.value));
              }}
            >
              {lines.map((payrollLine, index) => (
                <option
                  key={`${payrollLine.worker_id}-${String(index)}`}
                  value={index + 1}
                >
                  Line {index + 1}: {payrollLine.worker_name} (
                  {payrollLine.worker_id})
                </option>
              ))}
            </select>
          </>
        )}
        <label htmlFor={`${id}-expected`}>Expected</label>
        <input
          id={`${id}-expected`}
          value={expected}
          onChange={(event) => {
            setExpected(event.target.value);
          }}
        />
        <label htmlFor={`${id}-actual`}>Actual</label>
        <input
          id={`${id}-actual`}
          value={actual}
          onChange={(event) => {
            setActual(event.target.value);
          }}
        />
        {rule?.money && (
          <>
            <label htmlFor={`${id}-shortfall`}>Shortfall, in dollars</label>
            <input
              id={`${id}-shortfall`}
              inputMode="decimal"
              value={shortfall}
              onChange={(event) => {
                setShortfall(event.target.value);
              }}
            />
          </>
        )}
        <label htmlFor={`${id}-reason`}>Why the agent missed it</label>
        <textarea
          id={`${id}-reason`}
          rows={2}
          value={reason}
          onChange={(event) => {
            setReason(event.target.value);
          }}
        />
      </div>
    </ActionForm>
  );
}
