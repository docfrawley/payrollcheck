import { CircleAlert, Clock } from "lucide-react";
import { STOPPED, smallPrint } from "../copilot";
import type { CopilotStep, CopilotTurn as Turn } from "../conversation";
import { Markdown } from "./Markdown";
import { StepCard } from "./StepCard";

// A small working indicator, while the Copilot works between steps. The
// sidebar tells a screen reader where the turn stands, once.
function Working() {
  return (
    <p className="working">
      <span className="working-dots" aria-hidden>
        <span />
        <span />
        <span />
      </span>
      Working
    </p>
  );
}

function Cards({ steps }: Readonly<{ steps: CopilotStep[] }>) {
  if (steps.length === 0) return null;
  return (
    <ol className="cards" aria-label="Steps">
      {steps.map((step) => (
        <StepCard key={step.step_id} step={step} />
      ))}
    </ol>
  );
}

// One turn of a conversation: the reviewer's message, the Copilot's cards as it
// takes each step, and its answer, or what went wrong.
export function CopilotTurn({ turn }: Readonly<{ turn: Turn }>) {
  const working = turn.status === "working";
  const stepWorking = turn.steps.some((step) => step.status === "working");
  return (
    <li className={working ? "turn turn-working" : "turn"}>
      <p className="from-reviewer">{turn.message}</p>
      <Cards steps={turn.steps} />
      {working && !stepWorking && <Working />}
      {turn.answer && (
        <div className="from-copilot">
          <div className="answer">
            <Markdown text={turn.answer} />
          </div>
          <p className="small-print">{smallPrint(turn)}</p>
        </div>
      )}
      {turn.status === "failed" && (
        <p className="turn-ended failed">
          <CircleAlert aria-hidden />
          <span>
            The Copilot couldn't finish this: {turn.failure ?? "it failed"}
          </span>
        </p>
      )}
      {turn.status === "stopped" && (
        <p className="turn-ended">
          <Clock aria-hidden />
          <span>{STOPPED}</span>
        </p>
      )}
    </li>
  );
}
