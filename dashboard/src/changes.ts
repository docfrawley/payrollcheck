// The shapes of what a version of the payroll agent's configuration, or a
// proposal for one, changes: the lines of a text, and the check tools' tunable
// parameters.

export type DiffLineKind = "context" | "added" | "removed";

export interface DiffLine {
  kind: DiffLineKind;
  text: string;
}

// The lines that differ between two texts, in hunks with their context.
export interface Diff {
  added: number;
  removed: number;
  hunks: DiffLine[][];
}

export type ParameterUnit = "cents";

// One of the check tools' tunable parameters, as a page names it.
export interface ParameterLabel {
  name: string;
  label: string;
  unit: ParameterUnit;
}

// A version's value of a parameter.
export interface ParameterValue extends ParameterLabel {
  value: number;
}

// A parameter a version changed from the one it was based on.
export interface ParameterChange extends ParameterLabel {
  before: number;
  after: number;
}
