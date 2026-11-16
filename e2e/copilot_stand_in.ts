// Stands in for the Copilot's AgentCore app in the end-to-end tests: it answers
// /ping and the health check, and takes each turn the backend posts to
// /invocations, with no key. It then plays a scripted turn through the backend
// with the reviewer's sign-in it was given:
// it checks the sign-in with /api/me, stopping if it's refused, reads the
// turn's message, records its cards and answers, as the Copilot does.
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
const SOURCE = {
  file: "payroll_glossary.yaml",
  system: "Compliance manual, glossary",
  owner: "Compliance manager",
  reviewed: "2026-09-01",
};
// The case the scripted turn links to, and one it asks for that doesn't exist,
// so the app refuses.
const LINKED = "PC-0311";
const MISSING = "PC-9999";
const ANSWER = [
  `I started a dispatch and looked up a term. ${LINKED} is worth a look.`,
  "",
  "| What | Where it stands |",
  "| --- | --- |",
  "| The dispatch | Started with 3 payroll agents |",
  `| ${LINKED} | Returned to sub, with three open exceptions |`,
].join("\n");

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

// A message gets a lookup, an action, a refusal and a formatted answer.
async function takeTurn(payload: Payload) {
  await theTurn(payload);
  await card(
    payload,
    { tool: "lookup_payroll_term", kind: "context", input: "fringe" },
    () => Promise.resolve({ ok: true, answer: { term: "fringe" } }),
    [SOURCE],
  );
  await card(
    payload,
    { tool: "start_dispatch", kind: "action", input: "3" },
    () => asTheReviewer(payload.sign_in, "POST", "/dispatches", { agents: 3 }),
  );
  await card(payload, { tool: "get_case", kind: "cases", input: MISSING }, () =>
    asTheReviewer(payload.sign_in, "GET", `/cases/${MISSING}`),
  );
  await pause();
  await finish(payload, ANSWER);
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
