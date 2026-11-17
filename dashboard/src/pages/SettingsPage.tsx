import { Save } from "lucide-react";
import { useId, useState } from "react";
import { api } from "../api";
import type {
  ModelAllowed,
  Settings,
  SettingsPage as SettingsData,
} from "../settings";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { FormError } from "../components/FormError";
import { AppearanceChoice } from "../components/AppearanceChoice";
import { PageHeader } from "../components/PageHeader";
import { StateMessage } from "../components/StateMessage";
import { dateTime, label, money } from "../format";
import {
  GROUPS,
  SETTING_FIELDS,
  type SettingField,
  UNITS,
  changesBetween,
  inputsOf,
  settingGroups,
  valuesOf,
} from "../settingsFields";
import { useAction } from "../useAction";
import { useLoad } from "../useLoad";

function lastChange(settings: Settings): string {
  return settings.changed_by
    ? `Last changed by ${settings.changed_by} on ${dateTime(settings.changed_at)}`
    : "Not changed since the platform was set up";
}

export function SettingsPage() {
  // Loaded once, so a refresh never overwrites what a reviewer is typing. A
  // save returns the settings as they now stand.
  const { data, error } = useLoad(api.getSettings);
  const [saved, setSaved] = useState<SettingsData>();
  const page = saved ?? data;
  return (
    <>
      <PageHeader
        title="Settings"
        lead="The rules for improving the payroll agent."
      />
      {page ? (
        <SettingsPanels page={page} onSaved={setSaved} />
      ) : (
        <StateMessage error={error} />
      )}
    </>
  );
}

function SettingsPanels({
  page,
  onSaved,
}: Readonly<{ page: SettingsData; onSaved: (page: SettingsData) => void }>) {
  return (
    <div className="column">
      <SettingsForm current={page.current} onSaved={onSaved} />
      <Changes changes={page.changes} />
      <ModelsAllowed models={page.models_allowed} />
      <AppearanceChoice />
    </div>
  );
}

function SettingsForm({
  current,
  onSaved,
}: Readonly<{ current: Settings; onSaved: (page: SettingsData) => void }>) {
  const [inputs, setInputs] = useState(() => inputsOf(current));
  const [confirming, setConfirming] = useState(false);
  const proposed = valuesOf(current, inputs);
  const changes = changesBetween(current, proposed);
  const save = useAction(() => api.changeSettings(proposed).then(onSaved));

  return (
    <form
      className="settings"
      onSubmit={(event) => {
        event.preventDefault();
        setConfirming(true);
      }}
    >
      <div className="settings-bar">
        <p className="muted small">{lastChange(current)}</p>
        <button
          type="submit"
          className="button"
          disabled={changes.length === 0 || save.sending}
        >
          <Save />
          Save
        </button>
      </div>
      {save.error && <FormError>{save.error}</FormError>}
      {settingGroups.map((group) => (
        <fieldset className="panel" key={group}>
          <legend>{GROUPS[group].title}</legend>
          <p className="muted small">{GROUPS[group].lead}</p>
          <div className="setting-fields">
            {SETTING_FIELDS.filter((field) => field.group === group).map(
              (field) => (
                <SettingInput
                  key={field.id}
                  field={field}
                  value={inputs[field.id] ?? ""}
                  onChange={(value) => {
                    setInputs({ ...inputs, [field.id]: value });
                  }}
                />
              ),
            )}
          </div>
        </fieldset>
      ))}
      <ConfirmDialog
        open={confirming}
        title="Save the settings?"
        confirmLabel="Save the settings"
        onConfirm={() => {
          setConfirming(false);
          void save.run();
        }}
        onCancel={() => {
          setConfirming(false);
        }}
      >
        <ul className="change-list">
          {changes.map((change) => (
            <li key={change}>{change}</li>
          ))}
        </ul>
      </ConfirmDialog>
    </form>
  );
}

function SettingInput({
  field,
  value,
  onChange,
}: Readonly<{
  field: SettingField;
  value: string;
  onChange: (value: string) => void;
}>) {
  const id = useId();
  const unit = UNITS[field.unit];
  return (
    <div className="setting">
      <label htmlFor={id}>{field.label}</label>
      <span className="setting-input">
        {unit.prefix && <span id={`${id}-unit`}>{unit.prefix}</span>}
        <input
          id={id}
          type="number"
          inputMode="decimal"
          required
          min={unit.min}
          max={field.max}
          step={unit.step}
          aria-describedby={
            unit.prefix || unit.suffix ? `${id}-unit` : undefined
          }
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
          }}
        />
        {unit.suffix && (
          <span id={`${id}-unit`} className="muted">
            {unit.suffix}
          </span>
        )}
      </span>
    </div>
  );
}

function Changes({ changes }: Readonly<{ changes: Settings[] }>) {
  return (
    <section className="panel" aria-labelledby="changes-title">
      <h2 id="changes-title">Changes</h2>
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>When</th>
              <th>Who</th>
              <th>What changed</th>
            </tr>
          </thead>
          <tbody>
            {changes.map((change, index) => {
              const before = changes.at(index + 1);
              return (
                <tr key={change.number}>
                  <td className="nowrap">{dateTime(change.changed_at)}</td>
                  <td>{change.changed_by ?? "The platform's set-up"}</td>
                  <td>
                    {before
                      ? changesBetween(before, change).join("; ")
                      : "The starting settings"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ModelsAllowed({ models }: Readonly<{ models: ModelAllowed[] }>) {
  return (
    <section className="panel" aria-labelledby="models-title">
      <h2 id="models-title">Models allowed</h2>
      <p className="muted small">
        The models the payroll agent can use, set in data/models.json.
      </p>
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Reasoning efforts</th>
              <th className="num">Price per million tokens</th>
            </tr>
          </thead>
          <tbody>
            {models.map((model) => (
              <tr key={model.model}>
                <td className="mono">{model.model}</td>
                <td>{model.reasoning_efforts.map(label).join(", ")}</td>
                <td className="num mono">
                  {money(model.input_price)} in, {money(model.output_price)} out
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
