import type { Source } from "./sources";

// The Copilot's conversations, each turn and its cards.
export type TurnStatus =
  | "working"
  | "done"
  | "failed"
  // A turn still working long after it started, which the app reads as stopped.
  | "stopped";
export type CardKind =
  | "cases"
  | "subcontractors"
  | "projects"
  | "context"
  | "work"
  | "memory"
  | "action";
export type CardStatus = "working" | "done" | "refused" | "failed";

// A card: one tool the Copilot called, what was asked and what came back.
export interface CopilotStep {
  step_id: number;
  tool: string;
  kind: CardKind;
  // The tool's main input, such as PC-1201.
  input: string;
  asked: string;
  status: CardStatus;
  answer: string | null;
  reason: string | null;
  sources: Source[];
  started_at: string;
  finished_at: string | null;
  // So far, while it works.
  seconds: number;
}

export interface CopilotTurn {
  turn_id: string;
  number: number;
  message: string;
  status: TurnStatus;
  started_at: string;
  finished_at: string | null;
  // Once it has finished.
  seconds: number | null;
  answer: string | null;
  model_calls: number | null;
  cost: number | null;
  failure: string | null;
  steps: CopilotStep[];
}

export interface ConversationSummary {
  conversation_id: string;
  // The first message.
  title: string;
  created_at: string;
}

export interface Conversation extends ConversationSummary {
  turns: CopilotTurn[];
}

// The conversation's latest turn, if it has one.
export function latestTurn(
  conversation?: Conversation | null,
): CopilotTurn | undefined {
  return conversation?.turns.at(-1);
}

// Whether the Copilot is working on the conversation's latest turn, which is
// what the sidebar keeps asking about.
export function stillWorking(conversation?: Conversation | null): boolean {
  return latestTurn(conversation)?.status === "working";
}
