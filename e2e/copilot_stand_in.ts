// Stands in for the Copilot's AgentCore app in the end-to-end tests: it answers
// /ping and the health check, and takes each turn the backend posts to
// /invocations, with no key. It then plays a scripted turn through the backend
// with the reviewer's sign-in it was given, picked by the message's words: a
// lookup, a draft notice, a refusal to sign off, or a formatted answer. It
// checks the sign-in with /api/me, stopping if it's refused, reads the turn's
// message, records its cards and answers, as the Copilot does.
import { createServer } from "node:http";
import { json } from "node:stream/consumers";
import { reply } from "./stand_in.ts";

interface Payload {
  operation: string;
  conversation_id: string;
  turn_id: string;
  sign_in: string;
}

interface Turn {
  turn_id: string;
  message: string;
}

const app = process.env.PAYROLLCHECK_API ?? "";
// A pause between steps, so the sidebar shows each card working.
const STEP_MS = 250;
// The case the scripted turns draft a notice for, and the project they look up.
const NOTICE_CASE = "PC-0311";
const LINCOLN = "PRJ-01";
// What a search of the queue filters on: null for any.
const ANY_CASE = {
  project_id: null,
  subcontractor_id: null,
  status: null,
  period: null,
  has_open_exceptions: null,
  flag: null,
};

const pause = () => new Promise((resolve) => setTimeout(resolve, STEP_MS));

// Sends one request to the backend as the reviewer, with their sign-in.
async function asTheReviewer(
  signIn: string,
  method: string,
  path: string,
  body?: object,
) {
  const response = await fetch(`${app}/api${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${signIn}`,
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const answer = (await response.json()) as Record<string, unknown>;
  return { ok: response.ok, answer };
}

// Records a card for one step, as it starts and again as it ends.
async function card(
  payload: Payload,
  started: { tool: string; kind: string; input: string },
  step: () => Promise<{ ok: boolean; answer: Record<string, unknown> }>,
  sources: object[] = [],
) {
  const turn = `/copilot/turns/${payload.turn_id}`;
  const asked = JSON.stringify({ input: started.input });
  const { answer: made } = await asTheReviewer(
    payload.sign_in,
    "POST",
    `${turn}/steps`,
    { ...started, asked },
  );
  await pause();
  const { ok, answer } = await step();
  const result = ok
    ? { status: "done", answer: JSON.stringify(answer), reason: null, sources }
    : {
        status: "refused",
        answer: null,
        reason: String(answer.detail),
        sources: [],
      };
  await asTheReviewer(
    payload.sign_in,
    "POST",
    `${turn}/steps/${String(made.step_id)}/finish`,
    result,
  );
  return ok;
}

async function finish(payload: Payload, answer: string) {
  await asTheReviewer(
    payload.sign_in,
    "POST",
    `/copilot/turns/${payload.turn_id}/finish`,
    { answer, model_calls: 3, cost: 0.0021 },
  );
}

// The turn the app asked about, read with the reviewer's sign-in once the app
// says the sign-in is a reviewer's, as the Copilot checks it.
async function theTurn(payload: Payload): Promise<Turn> {
  const me = await asTheReviewer(payload.sign_in, "GET", "/me");
  if (!me.ok)
    throw new Error(`The sign-in was refused: ${String(me.answer.detail)}`);
  const { answer } = await asTheReviewer(
    payload.sign_in,
    "GET",
    `/copilot/conversations/${payload.conversation_id}`,
  );
  const turn = (answer.turns as Turn[]).find(
    (each) => each.turn_id === payload.turn_id,
  );
  if (!turn) throw new Error(`No turn ${payload.turn_id}`);
  return turn;
}

interface Found {
  by_subcontractor: { name: string; case_ids: string[] }[];
}

interface Exposed {
  flagged: string;
  outstanding: string;
  case_ids: string[];
}

// A lookup: the subs on the Lincoln School renovation with open exceptions.
async function lookUp(payload: Payload) {
  let found: Found = { by_subcontractor: [] };
  await card(
    payload,
    { tool: "list_cases", kind: "cases", input: LINCOLN },
    async () => {
      const read = await asTheReviewer(
        payload.sign_in,
        "POST",
        "/copilot/cases",
        {
          ...ANY_CASE,
          project_id: LINCOLN,
          has_open_exceptions: true,
        },
      );
      found = read.answer as unknown as Found;
      return read;
    },
  );
  const lines = found.by_subcontractor.map(
    (sub) => `- ${sub.name}: ${sub.case_ids.join(", ")}`,
  );
  return ["These subs have open exceptions:", "", ...lines].join("\n");
}

// A draft notice, which the reviewer then sends from the case page.
async function draft(payload: Payload) {
  await card(
    payload,
    { tool: "draft_notice", kind: "action", input: NOTICE_CASE },
    () =>
      asTheReviewer(
        payload.sign_in,
        "POST",
        `/copilot/cases/${NOTICE_CASE}/notice-draft`,
      ),
  );
  return `I drafted the notice for ${NOTICE_CASE}. Edit and send it on the case page.`;
}

// A formatted answer: this month's exposure, as a table with its total.
async function exposure(payload: Payload) {
  let exposed: Exposed = { flagged: "", outstanding: "", case_ids: [] };
  await card(
    payload,
    { tool: "exposure_summary", kind: "work", input: "this_month" },
    async () => {
      const read = await asTheReviewer(
        payload.sign_in,
        "POST",
        "/copilot/exposure",
        {
          project_id: null,
          subcontractor_id: null,
          period: { kind: "this_month" },
        },
      );
      exposed = read.answer as unknown as Exposed;
      return read;
    },
  );
  return [
    "This month's underpayment:",
    "",
    "| Flagged | Outstanding |",
    "| --- | --- |",
    `| ${exposed.flagged} | ${exposed.outstanding} |`,
    "",
    `From ${exposed.case_ids.join(", ")}.`,
  ].join("\n");
}

// A refusal: the Copilot never signs off, and calls no tool to.
function refusal() {
  return Promise.resolve(
    `I can't sign off ${NOTICE_CASE}: a reviewer signs off on its case page.`,
  );
}

// Each message gets the scripted turn its words ask for.
function scriptFor(message: string): (payload: Payload) => Promise<string> {
  const asked = message.toLowerCase();
  if (asked.includes("sign off")) return refusal;
  if (asked.includes("draft")) return draft;
  if (asked.includes("open exceptions")) return lookUp;
  return exposure;
}

async function takeTurn(payload: Payload) {
  const turn = await theTurn(payload);
  const answer = await scriptFor(turn.message)(payload);
  await pause();
  await finish(payload, answer);
}

createServer((request, response) => {
  const url = request.url ?? "";
  if (request.method === "POST" && url === "/invocations") {
    json(request).then(
      (body) => {
        const payload = body as Payload;
        if (payload.operation === "health") {
          reply(response, 200, { healthy: true });
          return;
        }
        reply(response, 200, { accepted: true });
        takeTurn(payload).catch((error: unknown) => {
          console.error(error);
        });
      },
      () => {
        reply(response, 400, { error: "Invalid JSON" });
      },
    );
  } else if (url === "/ping") {
    reply(response, 200, { status: "Healthy" });
  } else {
    reply(response, 404, { error: "Not found" });
  }
}).listen(Number(process.env.PORT), "127.0.0.1");
