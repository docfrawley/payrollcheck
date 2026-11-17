import { Sparkles } from "lucide-react";
import { SUGGESTED_QUESTIONS } from "../copilot";

// What an empty conversation shows: a greeting by the reviewer's first name, and
// a few questions to start from, each sent with a click.
export function CopilotGreeting({
  name,
  onAsk,
  disabled,
}: Readonly<{
  name: string;
  onAsk: (question: string) => void;
  disabled: boolean;
}>) {
  const [first] = name.split(" ");
  return (
    <div className="greeting">
      <p className="greeting-hello">Hello, {first}.</p>
      <p className="greeting-lead">
        Ask me about your projects, subcontractors and weeks, a case or our rate
        table, or have me draft a notice or start the work. I work as you, so I
        see only what you can, and you decide every case.
      </p>
      <ul className="suggestions" aria-label="Questions to ask">
        {SUGGESTED_QUESTIONS.map((question) => (
          <li key={question}>
            <button
              type="button"
              className="suggestion"
              disabled={disabled}
              onClick={() => {
                onAsk(question);
              }}
            >
              <Sparkles aria-hidden />
              <span>{question}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
