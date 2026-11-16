import {
  act,
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Run } from "./api";
import {
  runningDispatch as running,
  waitingInRun as waiting,
} from "./fixtures";
import {
  Refusal,
  type Routes,
  summary as caseSummary,
  panel,
  renderAt,
  sent,
  stubApi,
} from "./testing";
import { REFRESH_MS } from "./useLoad";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const finished: Run = {
  ...running,
  status: "finished",
  finished_at: "2026-11-23T17:04:54+00:00",
  seconds: 161,
  cases: running.cases.map((caseRecord) => ({
    ...caseRecord,
    status: "awaiting_review",
  })),
  summary: {
    with_exceptions: ["PC-1201", "PC-1205"],
    clean: ["PC-1202", "PC-1203", "PC-1204"],
    flagged: ["PC-1208"],
    agent_failed: ["PC-1216"],
    unfinished: ["PC-1212"],
  },
};

function showQueue(dispatch: Run | null) {
  const routes: Routes = {
    "GET /api/cases": [caseSummary],
    "GET /api/dispatches/latest": dispatch,
  };
  stubApi(routes);
  renderAt("/");
  return routes;
}

const dispatchPanel = () => panel("Dispatch");
const NO_DISPATCH = /^No dispatch yet\. Start one to check the Received cases/;

const started = (fetchMock: ReturnType<typeof stubApi>) =>
  sent(fetchMock, "POST /api/dispatches");

it("says when there's no dispatch yet", async () => {
  showQueue(null);
  const panel = await dispatchPanel();
  expect(await panel.findByText(NO_DISPATCH)).toBeDefined();
});

it("shows a running dispatch with its cases", async () => {
  showQueue(running);
  const panel = await dispatchPanel();
  expect(await panel.findByText("Running")).toBeDefined();
  expect(
    panel.getByText(/with 3 payroll agents at once, on version 1\./),
  ).toBeDefined();
  expect(panel.getByText("$0.0125", { selector: "p > span" })).toBeDefined();
  expect(panel.queryByText(/took/)).toBeNull();
  const rows = panel.getAllByRole("row").slice(1);
  expect(
    rows.map((row) => within(row).getAllByRole("cell")[0].textContent),
  ).toEqual(["PC-1201", "PC-1202", "PC-1203"]);
  const first = within(rows[0]);
  expect(first.getByText("Awaiting review")).toBeDefined();
  expect(first.getByText("Lincoln School renovation")).toBeDefined();
  expect(first.getByText("2")).toBeDefined();
  expect(first.getByText("41 s")).toBeDefined();
  expect(within(rows[1]).getByText("In progress")).toBeDefined();
  expect(within(rows[2]).getByText("Received")).toBeDefined();
  const link = first.getByRole("link", { name: "PC-1201" });
  expect(link.getAttribute("href")).toBe("/cases/PC-1201");
  expect(panel.queryByText("When it finished")).toBeNull();
});

it("shows a finished dispatch with its summary", async () => {
  showQueue(finished);
  const panel = await dispatchPanel();
  expect(await panel.findByText("Finished")).toBeDefined();
  expect(panel.getByText("2 min 41 s")).toBeDefined();
  const lines = within(panel.getByRole("list", { name: "When it finished" }))
    .getAllByRole("listitem")
    .map((line) => line.textContent);
  expect(lines).toEqual([
    "5 awaiting review: 2 with exceptions and 3 clean.",
    "With exceptions: PC-1201, PC-1205",
    "Flagged by the screening: PC-1208",
    "Failed by the agent: PC-1216",
    "Left for the next dispatch: PC-1212",
  ]);
  const flagged = panel.getByRole("link", { name: "PC-1208" });
  expect(flagged.getAttribute("href")).toBe("/cases/PC-1208");
});

it("shows a stopped dispatch", async () => {
  showQueue({ ...running, status: "stopped" });
  const panel = await dispatchPanel();
  const chip = await panel.findByText("Stopped");
  expect(chip.className).toBe("chip run-stopped");
  expect(
    panel.getByText(
      "It stopped before it finished. The next dispatch carries on its cases.",
    ),
  ).toBeDefined();
});

it("says why a dispatch stopped", async () => {
  showQueue({
    ...running,
    status: "stopped",
    stopped_because: "The agent stopped answering",
  });
  const panel = await dispatchPanel();
  expect(
    await panel.findByText(
      "Stopped: The agent stopped answering. The next dispatch carries on its cases.",
    ),
  ).toBeDefined();
});

it("follows a dispatch as it works", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const routes = showQueue(null);
  const panel = await dispatchPanel();
  expect(await panel.findByText(NO_DISPATCH)).toBeDefined();

  routes["GET /api/dispatches/latest"] = { ...running, cases: [waiting] };
  await act(() => vi.advanceTimersByTimeAsync(REFRESH_MS));
  expect(panel.getByText("Received")).toBeDefined();

  routes["GET /api/dispatches/latest"] = finished;
  await act(() => vi.advanceTimersByTimeAsync(REFRESH_MS));
  expect(panel.getByText("Finished")).toBeDefined();
  expect(panel.queryByText("Received")).toBeNull();
});

function startWith(agents: string) {
  const choice = screen.getByRole("combobox", {
    name: "Payroll agents at once",
  });
  fireEvent.change(choice, { target: { value: agents } });
  fireEvent.click(screen.getByRole("button", { name: "Start a dispatch" }));
}

it("offers 1 to 25 payroll agents at once, with 3 chosen", async () => {
  showQueue(null);
  const choice = await screen.findByRole("combobox", {
    name: "Payroll agents at once",
  });
  const options = within(choice).getAllByRole("option");
  expect(options.map((option) => option.textContent)).toEqual(
    Array.from({ length: 25 }, (_, index) => String(index + 1)),
  );
  expect((choice as HTMLSelectElement).value).toBe("3");
});

it("starts a dispatch with the payroll agents chosen", async () => {
  const routes: Routes = {
    "GET /api/cases": [caseSummary],
    "GET /api/dispatches/latest": null,
    "POST /api/dispatches": { status: "accepted" },
  };
  const fetchMock = stubApi(routes);
  renderAt("/");
  await screen.findByText(NO_DISPATCH);
  startWith("7");
  await waitFor(() => {
    expect(started(fetchMock)).toEqual([{ agents: 7 }]);
  });
  expect(screen.queryByRole("alert")).toBeNull();
});

it.each([
  [409, "An evaluation is running"],
  [503, "The agent's service isn't running"],
])("shows a refusal with status %i", async (status, detail) => {
  const routes: Routes = {
    "GET /api/cases": [caseSummary],
    "GET /api/dispatches/latest": null,
    "POST /api/dispatches": new Refusal(status, detail),
  };
  const fetchMock = stubApi(routes);
  renderAt("/");
  await screen.findByText(NO_DISPATCH);
  startWith("3");
  expect((await screen.findByRole("alert")).textContent).toBe(detail);
  const button = screen.getByRole("button", { name: "Start a dispatch" });
  await waitFor(() => {
    expect(button.getAttribute("aria-disabled")).toBe("false");
  });
  fireEvent.click(button);
  await waitFor(() => {
    expect(started(fetchMock)).toHaveLength(2);
  });
});
