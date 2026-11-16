import {
  BookOpen,
  Bot,
  Brain,
  FileText,
  type LucideIcon,
  Users,
  Zap,
} from "lucide-react";
import {
  type CardKind,
  type Conversation,
  type CopilotTurn,
  type TurnStatus,
  latestTurn,
} from "./conversation";
import { modelCost } from "./format";

// What the sidebar shows of each kind of card: its icon and what it's about.
export const CARD_KINDS: Record<CardKind, { icon: LucideIcon; label: string }> =
  {
    cases: { icon: FileText, label: "Cases" },
    subcontractors: { icon: Users, label: "Subcontractors and projects" },
    context: { icon: BookOpen, label: "The context layer" },
    work: { icon: Bot, label: "The agent's work" },
    memory: { icon: Brain, label: "Memory" },
    action: { icon: Zap, label: "Action" },
  };

// What this browser remembers of the sidebar for each reviewer: whether it is
// open, and the conversation open in it.
const OPEN = "payrollcheck-copilot-open";
const CONVERSATION = "payrollcheck-copilot-conversation";

const keyFor = (name: string, reviewerId: string) => `${name}:${reviewerId}`;

function read(name: string, reviewerId: string): string | null {
  return localStorage.getItem(keyFor(name, reviewerId));
}

function write(name: string, reviewerId: string, value: string | undefined) {
  const key = keyFor(name, reviewerId);
  if (value === undefined) localStorage.removeItem(key);
  else localStorage.setItem(key, value);
}

export function savedOpen(reviewerId: string): boolean {
  return read(OPEN, reviewerId) !== "false";
}

export function saveOpen(reviewerId: string, open: boolean) {
  write(OPEN, reviewerId, String(open));
}

export function savedConversation(reviewerId: string): string | undefined {
  return read(CONVERSATION, reviewerId) ?? undefined;
}

export function saveConversation(reviewerId: string, id: string | undefined) {
  write(CONVERSATION, reviewerId, id);
}

// How often the sidebar reads a conversation while the Copilot works on it.
export const ASK_EVERY_MS = 1000;
// The longest message the app takes.
export const MESSAGE_LENGTH = 4000;
// Below this width the sidebar opens over the page, and Escape closes it.
export const OVERLAY = "(width < 1100px)";
export const ASK = "Ask the Copilot";
export const STILL_WORKING = "The Copilot is working on your message";
export const OPENING = "Opening the conversation";
export const STOPPED =
  "This turn stopped before it finished. Send a new message to carry on.";
export const NO_CONVERSATIONS =
  "No conversations yet. Ask the Copilot something to start one.";
export const SUGGESTED_QUESTIONS = [
  "What needs me today?",
  "How did the latest dispatch go?",
  "Which cases have a screening flag?",
  "What do the filing rules say about late payrolls?",
];

// Why the message box can't take a message yet, if it can't.
export function waitingFor(conversation?: Conversation): string | undefined {
  const status = latestTurn(conversation)?.status;
  return status === "working" ? STILL_WORKING : undefined;
}

// Where the latest turn stands, as a screen reader is told it.
export const TURN_STATES: Record<TurnStatus, string> = {
  working: "The Copilot is working",
  done: "The Copilot answered",
  failed: "The Copilot couldn't finish",
  stopped: "The Copilot stopped",
};

// The small print under an answer: its model calls, their cost and its time.
export function smallPrint(turn: CopilotTurn): string {
  const calls = turn.model_calls ?? 0;
  const seconds = Math.round(turn.seconds ?? 0);
  return [
    `${String(calls)} model ${calls === 1 ? "call" : "calls"}`,
    modelCost(turn.cost ?? 0),
    `${String(seconds)} ${seconds === 1 ? "second" : "seconds"}`,
  ].join(", ");
}
