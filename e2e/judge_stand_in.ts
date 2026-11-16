// Stands in for OpenRouter's Decisions endpoint in the end-to-end tests: it grades
// every notice the same on the rubric's four points, covering every exception
// at 0.9, its amounts matching at 0.8, plain language at 0.7 and no legal
// interpretation at 1.0, a score of 0.85, for $0.00002.
import { createServer } from "node:http";
import { reply } from "./stand_in.ts";

const point = (noul: number) => ({ type: "noul", noul });

const ANSWER = {
  model: "typesafe/jev-1.13",
  answers: {
    covers_every_exception: point(0.9),
    amounts_match: point(0.8),
    plain_language: point(0.7),
    no_legal_interpretation: point(1.0),
  },
  usage: { input_tokens: 400, output_tokens: 4, cost: 0.00002 },
};

createServer((request, response) => {
  request.resume();
  if (request.method === "POST" && request.url === "/api/alpha/decisions")
    reply(response, 200, ANSWER);
  else if (request.url === "/health") reply(response, 200, { status: "ok" });
  else reply(response, 404, { detail: "Not found" });
}).listen(Number(process.env.PORT), "127.0.0.1");
