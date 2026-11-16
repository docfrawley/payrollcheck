// The shapes of the platform's settings and the models allowed, as the backend
// gives and takes them.

// A setting for each measure the rule compares.
export interface MeasureSettings {
  catch_rate: number;
  false_per_100: number;
  shortfall_accuracy: number;
  notice_score: number;
  cost_per_case: number;
  seconds_per_case: number;
}

// What a new version must meet on the held-out set: floors on the catch rate,
// shortfall accuracy and notice score, and a ceiling on false exceptions.
export interface Objectives {
  catch_rate: number;
  false_per_100: number;
  shortfall_accuracy: number;
  notice_score: number;
}

export interface SettingsValues {
  objectives: Objectives;
  noise: MeasureSettings;
  tolerance: MeasureSettings;
  spending_limit: number;
  agents: number;
  // The app's today, or null for the real date.
  business_date: string | null;
}

export interface Settings extends SettingsValues {
  number: number;
  changed_by: string | null;
  changed_at: string;
}

export interface ModelAllowed {
  model: string;
  reasoning_efforts: string[];
  // US dollars per million tokens.
  input_price: number;
  output_price: number;
}

export interface SettingsPage {
  current: Settings;
  changes: Settings[];
  models_allowed: ModelAllowed[];
}
