import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TRY_AGAIN } from "./components/StateMessage";
import {
  Refusal,
  caseRecord,
  renderAt,
  sent,
  stubApi,
  summary,
} from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the queue with a tile for each status, in order", async () => {
  stubApi({
    "GET /api/cases": [
      summary,
      {
        ...summary,
        case_id: "PC-1102",
        status: "accepted",
      },
      {
        ...summary,
        case_id: "PC-1103",
        status: "awaiting_review",
        open_exceptions: 3,
        shortfall_cents: 128460,
      },
      {
        ...summary,
        case_id: "PC-1104",
        status: "awaiting_review",
        screening_flag: true,
        agent_failed: true,
      },
      { ...summary, case_id: "PC-0311", status: "returned_to_sub" },
    ],
    "GET /api/dispatches/latest": null,
  });
  renderAt("/");
  const link = await screen.findByRole("link", { name: "PC-1201" });
  expect(link.getAttribute("href")).toBe("/cases/PC-1201");
  const tiles = within(screen.getByRole("region", { name: "Cases by status" }))
    .getAllByRole("group")
    .map((tile) => tile.getAttribute("aria-label"));
  expect(tiles).toEqual([
    "Received: 1",
    "In progress: 0",
    "Awaiting review: 2",
    "Accepted: 1",
    "Returned to sub: 1",
  ]);
  const returned = screen.getByLabelText("Returned to sub: 1");
  expect(returned.className).toBe("tile status-returned_to_sub");
  expect(returned.querySelector("svg.lucide-undo-2")).not.toBeNull();
  const short = screen.getByRole("row", { name: /PC-1103/ });
  const chip = within(short).getByText("Awaiting review");
  expect(chip.className).toBe("chip status-awaiting_review");
  expect(within(short).getByText("3")).toBeDefined();
  expect(within(short).getByText("$1,284.60")).toBeDefined();
  const flagged = within(screen.getByRole("row", { name: /PC-1104/ }));
  expect(flagged.getByText("Screening flag")).toBeDefined();
  expect(flagged.getByText("Agent failed")).toBeDefined();
  expect(screen.getAllByText("Garden State Electric LLC")).toHaveLength(5);
  expect(screen.getAllByText("Lincoln School renovation")).toHaveLength(5);
  expect(screen.getAllByText("Nov 22, 2026")).toHaveLength(5);
});

it("shows an error when the queue can't load", async () => {
  stubApi({ "GET /api/cases": new Refusal(500, "The backend is down") });
  renderAt("/");
  expect((await screen.findByRole("alert")).textContent).toBe(
    `The backend is down ${TRY_AGAIN}`,
  );
});

it("shows a case in full", async () => {
  stubApi({ "GET /api/cases/PC-1201": caseRecord });
  renderAt("/cases/PC-1201");
  expect(
    await screen.findByRole("heading", {
      name: "Garden State Electric LLC",
      level: 1,
    }),
  ).toBeDefined();
  expect(screen.getByText("Kim Dimitrov")).toBeDefined();
  expect(screen.getByText("PC-1201-1.csv")).toBeDefined();
  expect(screen.getAllByText("Received").length).toBeGreaterThan(0);
});

it("says when a case doesn't exist, and stops asking for it", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetchMock = stubApi({});
  renderAt("/cases/PC-9999");
  expect(
    await screen.findByText("Case not found. Choose one from the queue."),
  ).toBeDefined();
  await vi.advanceTimersByTimeAsync(5000);
  expect(sent(fetchMock, "GET /api/cases/PC-9999")).toHaveLength(1);
  vi.useRealTimers();
});

it("shows other errors loading a case", async () => {
  stubApi({ "GET /api/cases/PC-1201": new Refusal(500, "Server error") });
  renderAt("/cases/PC-1201");
  expect((await screen.findByRole("alert")).textContent).toBe(
    `Server error ${TRY_AGAIN}`,
  );
});

it("says when a page doesn't exist", async () => {
  stubApi({});
  renderAt("/nowhere");
  expect(
    await screen.findByText("Page not found. Choose a page from the header."),
  ).toBeDefined();
});
