import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { type Appearance, chooseAppearance, savedAppearance } from "../theme";

const APPEARANCES: {
  appearance: Appearance;
  label: string;
  icon: LucideIcon;
}[] = [
  { appearance: "light", label: "Light", icon: Sun },
  { appearance: "dark", label: "Dark", icon: Moon },
  { appearance: "system", label: "Same as this computer", icon: Monitor },
];

// Light, dark or the computer's appearance, kept in this browser.
export function AppearanceChoice() {
  const [appearance, setAppearance] = useState(savedAppearance);
  return (
    <fieldset className="panel">
      <legend>Appearance</legend>
      <p className="muted small">Saved in this browser only.</p>
      <div className="appearances">
        {APPEARANCES.map((choice) => (
          <label key={choice.appearance} className="appearance">
            <input
              type="radio"
              name="appearance"
              checked={appearance === choice.appearance}
              onChange={() => {
                chooseAppearance(choice.appearance);
                setAppearance(choice.appearance);
              }}
            />
            <choice.icon />
            {choice.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
