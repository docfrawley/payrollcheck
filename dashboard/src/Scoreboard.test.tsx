import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Evaluation } from "./api";
import { clean } from "./caseTesting";
import {
  finishedEvaluation as finished,
  scoredEvaluation as scored,
} from "./fixtures";
import {
  Refusal,
  type Routes,
  panel,
  renderAt,
  sent,
  stubApi,
  summary,
} from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const running: Evaluation = {
  ...finished,
  run_id: "run-9",
  number: 9,
  agents: 5,
  evaluation_set: "tiny",
  status: "running",
  finished_at: null,
  seconds: null,
  size: 10,
  measures: {
    ...finished.measures,
    shortfall_accuracy: null,
    run_seconds: null,
  },
};

function showScoreboard(routes: Routes = {}) {
  const fetchMock = stubApi({
    "GET /api/evaluations": [running, finished],
    ...routes,
  });
  renderAt("/scoreboard");
  return fetchMock;
}

it("lists the evaluations in the backend's order, with their measures", async () => {
  showScoreboard();
  const list = await panel("Evaluations");
  const rows = (await list.findAllByRole("row")).slice(1);
  expect(
    rows.map((row) => within(row).getAllByRole("link")[0].textContent),
  ).toEqual(["Evaluation #9", "Evaluation #7"]);
  const [newest, older] = rows.map((row) => within(row));
  expect(newest.getByText("Tiny set, 10 payrolls")).toBeDefined();
  expect(newest.getByText("Running")).toBeDefined();
  expect(older.getByText("Development set, 207 payrolls")).toBeDefined();
  expect(older.getByText("openai/gpt-6-luna")).toBeDefined();
  for (const shown of [
    "80% (36 of 45)",
    "4 (1.9 per 100)",
    "95%",
    "1 of 1",
    "$0.0125",
    "40 s",
  ])
    expect(older.getByText(shown)).toBeDefined();
  expect(newest.getByText("None caught")).toBeDefined();
  expect(older.getByText("2 min 41 s")).toBeDefined();
  expect(newest.queryByText("2 min 41 s")).toBeNull();
  expect(
    older.getByText(/Nov 23, .*, version 1, 25 payroll agents at once/),
  ).toBeDefined();
  const link = older.getByRole("link", { name: "Evaluation #7" });
  expect(link.getAttribute("href")).toBe("/scoreboard/run-7");
});

it("says when there are no evaluations yet", async () => {
  stubApi({ "GET /api/evaluations": [] });
  renderAt("/scoreboard");
  expect(
    await screen.findByText(/^No evaluations yet\. Start one above/),
  ).toBeDefined();
});

it("starts an evaluation with the choices made", async () => {
  const fetchMock = showScoreboard({
    "POST /api/evaluations": { status: "accepted" },
  });
  const form = await panel("Start an evaluation");
  const set = form.getByRole("combobox", { name: "Set" });
  const agents = form.getByRole("combobox", { name: "Payroll agents at once" });
  expect([set, agents].map((c) => (c as HTMLSelectElement).value)).toEqual([
    "development",
    "3",
  ]);
  expect(
    within(set)
      .getAllByRole("option")
      .map((option) => option.textContent),
  ).toEqual(["Development set", "Held-out set", "Tiny set"]);

  fireEvent.change(set, { target: { value: "tiny" } });
  fireEvent.change(agents, { target: { value: "5" } });
  fireEvent.click(form.getByRole("button", { name: "Start an evaluation" }));
  await waitFor(() => {
    expect(sent(fetchMock, "POST /api/evaluations")).toEqual([
      { evaluation_set: "tiny", agents: 5 },
    ]);
  });
});

it.each([
  [409, "A dispatch is running"],
  [503, "The agent's service isn't running"],
])("shows a refusal with status %i", async (status, detail) => {
  showScoreboard({ "POST /api/evaluations": new Refusal(status, detail) });
  const form = await panel("Start an evaluation");
  fireEvent.click(form.getByRole("button", { name: "Start an evaluation" }));
  expect((await form.findByRole("alert")).textContent).toBe(detail);
});

it("shows an evaluation's copies beside their labels", async () => {
  stubApi({ "GET /api/evaluations/run-9": scored });
  renderAt("/scoreboard/run-9");
  expect(
    await screen.findByRole("heading", { name: "Evaluation #9", level: 1 }),
  ).toBeDefined();
  const measures = await panel("Measures");
  const shown = (label: string) =>
    measures.getByText(label).nextSibling?.textContent;
  expect(shown("Catch rate")).toBe("80% (36 of 45)");
  expect(shown("False exceptions")).toBe("4 (1.9 per 100)");
  expect(shown("Shortfall accuracy")).toBe("95%");
  expect(shown("Screening flags")).toBe("1 of 1");
  expect(shown("Run time")).toBe("2 min 41 s");
  expect(measures.getByText(/Started/).textContent).toContain(
    "Model cost $0.3125.",
  );
  expect(measures.queryByText(/judge/)).toBeNull();
  const copies = await panel("Copies");
  const rows = copies.getAllByRole("row").slice(1);
  // The copy with a miss and a false exception comes first, tinted.
  expect(
    rows.map((row) => within(row).getAllByRole("link")[0].textContent),
  ).toEqual(["PC-0507-E9", "PC-0412-E9", "PC-0809-E9"]);
  expect(rows.map((row) => row.className)).toEqual(["copy-off", "", ""]);
  const [wrong, right, flagged] = rows.map((row) => within(row));
  const missed = wrong.getByText("Missed");
  expect(missed.className).toBe("chip score-missed");
  expect(missed.parentElement?.textContent).toBe(
    "Missed rate.base_short W-001, line 1 $64.00 expected",
  );
  const falseOne = wrong.getByText("False");
  expect(falseOne.className).toBe("chip score-missed");
  expect(falseOne.parentElement?.textContent).toBe(
    "False arithmetic.gross W-001, line 1 $64.00",
  );
  expect(right.getByText("Caught").className).toBe("chip score-caught");
  expect(right.getByText("Matched").className).toBe("chip score-caught");
  expect(right.getByText("Caught").parentElement?.textContent).toBe(
    "Caught rate.base_short W-001, line 1 $64.00",
  );
  expect(flagged.getAllByText("None")).toHaveLength(2);
  expect(flagged.getByText("Expected and flagged")).toBeDefined();
  const link = right.getByRole("link", { name: "PC-0412-E9" });
  expect(link.getAttribute("href")).toBe("/cases/PC-0412-E9");
});

it("shows a shortfall caught wrong with both amounts, after the misses", async () => {
  const [copy] = scored.cases;
  const [label] = copy.labels;
  stubApi({
    "GET /api/evaluations/run-9": {
      ...scored,
      cases: [
        {
          ...copy,
          labels: [
            { ...label, result: "shortfall_wrong", shortfall_cents: 6401 },
            {
              ...label,
              rule: "form.unsigned",
              worker_id: null,
              line_no: null,
              expected_shortfall_cents: null,
              result: "missed",
              shortfall_cents: null,
            },
          ],
          misses: 1,
        },
      ],
    },
  });
  renderAt("/scoreboard/run-9");
  const labels = (await panel("Copies")).getAllByRole("list", {
    name: "Labels",
  });
  expect(
    within(labels[0])
      .getAllByRole("listitem")
      .map((item) => item.textContent),
  ).toEqual([
    "Missed form.unsigned The whole payroll",
    "Shortfall wrong rate.base_short W-001, line 1 $64.00 expected, $64.01 raised",
  ]);
  expect(within(labels[0]).getByText("Shortfall wrong").className).toBe(
    "chip score-shortfall_wrong",
  );
});

it("says when a copy's screening was missed or not expected", async () => {
  const [copy] = scored.cases;
  stubApi({
    "GET /api/evaluations/run-9": {
      ...scored,
      cases: [
        { ...copy, case_id: "PC-0809-E9", screening_expected: true },
        { ...copy, case_id: "PC-0412-E9", screening_found: true },
      ],
    },
  });
  renderAt("/scoreboard/run-9");
  const copies = await panel("Copies");
  expect(copies.getByText("Expected, missed")).toBeDefined();
  expect(copies.getByText("Flagged, not expected")).toBeDefined();
});

it("says when an evaluation doesn't exist", async () => {
  stubApi({});
  renderAt("/scoreboard/run-404");
  expect(
    await screen.findByText(
      "Evaluation not found. Choose one on the Scoreboard.",
    ),
  ).toBeDefined();
});

it("shows a copy's evaluation, and no Sign off or Send back", async () => {
  stubApi({
    "GET /api/cases/PC-1201": {
      ...clean,
      evaluation_id: "run-9",
      copy_of: "PC-0412",
    },
    "GET /api/cases/PC-1201/steps": [],
  });
  renderAt("/cases/PC-1201");
  const note = await screen.findByText(/A copy of/);
  expect(note.textContent).toBe("A copy of PC-0412 in an evaluation");
  const link = within(note).getByRole("link", { name: "evaluation" });
  expect(link.getAttribute("href")).toBe("/scoreboard/run-9");
  const review = await panel("Review");
  expect(review.queryByRole("button", { name: "Sign off" })).toBeNull();
  expect(review.queryByRole("button", { name: "Send back" })).toBeNull();
});

it("links to the Scoreboard from the header", async () => {
  stubApi({ "GET /api/cases": [summary], "GET /api/dispatches/latest": null });
  renderAt("/");
  const link = await screen.findByRole("link", { name: "Scoreboard" });
  expect(link.getAttribute("href")).toBe("/scoreboard");
});

it("shows a stopped evaluation as stopped, with no run time", async () => {
  const stopped = { ...running, status: "stopped" as const };
  stubApi({
    "GET /api/evaluations": [stopped],
    "GET /api/evaluations/run-9": {
      ...scored,
      status: "stopped",
      stopped_because: "Stopped by Dana Whitfield",
      measures: running.measures,
    },
  });
  renderAt("/scoreboard");
  const [row] = (await (await panel("Evaluations")).findAllByRole("row")).slice(
    1,
  );
  expect(within(row).getByText("Stopped")).toBeDefined();
  expect(within(row).getAllByRole("cell").at(-1)?.textContent).toBe(
    "Not finished",
  );
  cleanup();

  renderAt("/scoreboard/run-9");
  const measures = await panel("Measures");
  expect(screen.getByText("Stopped")).toBeDefined();
  expect(measures.getByText("Run time").nextSibling?.textContent).toBe(
    "Not finished",
  );
  expect(measures.getByText("Stopped by Dana Whitfield")).toBeDefined();
});
