import { cleanup, fireEvent, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { CARD_KINDS } from "./copilot";
import type { CardKind } from "./conversation";
import {
  openSidebar,
  showConversation,
  sidebar,
  step,
  turn,
} from "./copilotTesting";

// The Copilot's cards in the sidebar: each step's card and the answer,
// formatted.

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const SOURCE = {
  file: "payroll_glossary.yaml",
  system: "Compliance manual, glossary",
  owner: "Compliance manager",
  reviewed: "2026-09-01",
};

it("shows each card with its kind, call and state", async () => {
  showConversation(
    turn({
      status: "working",
      answer: null,
      steps: [
        step({ step_id: 1 }),
        step({
          step_id: 2,
          tool: "lookup_payroll_term",
          kind: "context",
          input: "fringe",
          answer: '{"term": "fringe"}',
          sources: [SOURCE],
        }),
        step({
          step_id: 3,
          tool: "start_dispatch",
          kind: "action",
          input: "10",
          status: "refused",
          answer: null,
          reason: "A dispatch is running",
        }),
        step({
          step_id: 4,
          tool: "list_steps",
          status: "failed",
          reason: "It broke",
        }),
        step({
          step_id: 5,
          tool: "list_cases",
          input: "",
          status: "working",
          seconds: 2.5,
        }),
      ],
    }),
  );
  const copilot = await openSidebar();
  const list = within(await copilot.findByRole("list", { name: "Steps" }));
  const [lookup, read, action, failed, working] = list.getAllByRole("listitem");
  expect(lookup.textContent).toContain("get_case PC-1201");
  expect(within(lookup).getByLabelText("Done")).toBeDefined();
  expect(lookup.textContent).toContain("0.4 s");
  expect(action.className).toContain("card-action");
  expect(within(action).getByText("Refused")).toBeDefined();
  expect(action.textContent).toContain("A dispatch is running");
  expect(within(failed).getByText("Failed")).toBeDefined();
  expect(failed.textContent).toContain("It broke");
  expect(within(working).getByLabelText("Working")).toBeDefined();
  expect(working.textContent).toContain("2.5 s");
  const open = within(read).getByRole("button");
  expect(open.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(open);
  expect(open.getAttribute("aria-expanded")).toBe("true");
  expect(within(read).getByText("Asked")).toBeDefined();
  expect(within(read).getByText("Came back")).toBeDefined();
  expect(read.textContent).toContain("payroll_glossary.yaml");
  expect(read.textContent).toContain(
    "Compliance manual, glossary, owned by Compliance manager",
  );
});

it.each(Object.entries(CARD_KINDS))(
  "marks a %s card with its icon",
  async (kind, { label }) => {
    showConversation(turn({ steps: [step({ kind: kind as CardKind })] }));
    const card = within(
      await (await openSidebar()).findByRole("list", { name: "Steps" }),
    );
    expect(card.getByLabelText(label).tagName).toBe("svg");
  },
);

it("shows the working indicator while the turn works and no card does", async () => {
  showConversation(turn({ status: "working", answer: null, steps: [step()] }));
  const copilot = await openSidebar();
  expect(await copilot.findByText("Working")).toBeDefined();
  cleanup();
  showConversation(
    turn({
      status: "working",
      answer: null,
      steps: [step({ status: "working" })],
    }),
  );
  await (await openSidebar()).findByLabelText("Working");
  expect(sidebar().queryByText("Working")).toBeNull();
});

const ANSWER = [
  "PC-1203 needs you:",
  "",
  "- It is awaiting review.",
  "",
  "| Case | Shortfall |",
  "| --- | --- |",
  "| PC-1203 | $64.00 |",
].join("\n");

it("formats the answer with case links and its small print", async () => {
  showConversation(turn({ answer: ANSWER }));
  const copilot = await openSidebar();
  const [link] = await copilot.findAllByRole("link", { name: "PC-1203" });
  expect(link.getAttribute("href")).toBe("/cases/PC-1203");
  expect(copilot.getByRole("table")).toBeDefined();
  expect(copilot.getByText("It is awaiting review.")).toBeDefined();
  expect(copilot.getByText("4 model calls, $0.0021, 12 seconds")).toBeDefined();
});

it("links a case id once, even in a link, and opens another site in a tab of its own", async () => {
  showConversation(
    turn({
      answer:
        "See [PC-1203](/cases/PC-1203), https://example.com/PC-1204 and [the guide](//example.com/cases).",
    }),
  );
  const copilot = await openSidebar();
  const links = await copilot.findAllByRole("link");
  expect(links.map((link) => link.getAttribute("href"))).toEqual([
    "/cases/PC-1203",
    "https://example.com/PC-1204",
    "//example.com/cases",
  ]);
  expect(document.querySelector(".answer a a")).toBeNull();
  expect(links[2].getAttribute("target")).toBe("_blank");
});
