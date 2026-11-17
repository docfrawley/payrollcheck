import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { SettingsPage } from "./settings";
import {
  wholeText,
  Refusal,
  priya,
  panel,
  renderAt,
  sent,
  settings,
  stubApi,
} from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

const changedSettings = {
  ...settings.current,
  number: 2,
  spending_limit: 0.75,
  changed_by: "Dana Whitfield",
  changed_at: "2026-10-05T18:05:00+00:00",
};

const changed: SettingsPage = {
  ...settings,
  current: changedSettings,
  changes: [changedSettings, settings.current],
};

const group = (name: string) => within(screen.getByRole("group", { name }));

async function spendingInput() {
  await screen.findByRole("group", { name: "Spending" });
  return group("Spending").getByLabelText("Spending limit for each round");
}

async function save() {
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  fireEvent.click(
    within(await screen.findByRole("dialog")).getByRole("button", {
      name: "Save the settings",
    }),
  );
}

it("shows each setting with its unit and when it last changed", async () => {
  stubApi({ "GET /api/settings": changed });
  renderAt("/settings");
  const spending = await spendingInput();
  expect(spending).toHaveProperty("value", "0.75");
  expect(
    document.getElementById(spending.getAttribute("aria-describedby") ?? "")
      ?.textContent,
  ).toBe("$");
  expect(screen.getByText(/Last changed by Dana Whitfield on/)).toBeDefined();
  const catchRate = group("Objectives on the held-out set").getByLabelText(
    "Catch rate at least",
  );
  expect(catchRate).toHaveProperty("value", "92");
  expect(catchRate.getAttribute("max")).toBe("100");
  const objectives = group("Objectives on the held-out set");
  const falseAtMost = objectives.getByLabelText("False exceptions at most");
  expect(falseAtMost).toHaveProperty("value", "2.5");
  expect(
    document.getElementById(falseAtMost.getAttribute("aria-describedby") ?? "")
      ?.textContent,
  ).toBe("per 100 payrolls");
  expect(
    objectives.getByLabelText("Shortfall accuracy at least"),
  ).toHaveProperty("value", "100");
  const noticeAtLeast = objectives.getByLabelText("Notice score at least");
  expect(noticeAtLeast).toHaveProperty("value", "0.80");
  expect(noticeAtLeast.getAttribute("max")).toBe("1");
  const noise = group("Noise");
  expect(noise.getByLabelText("Catch rate")).toHaveProperty("value", "5");
  expect(noise.getByLabelText("False exceptions")).toHaveProperty("value", "1");
  expect(noise.getByLabelText("Shortfall accuracy")).toHaveProperty(
    "value",
    "0",
  );
  expect(noise.getByLabelText("Notice score")).toHaveProperty("value", "0.10");
  expect(
    group("Tolerance").getByLabelText("Model cost per case"),
  ).toHaveProperty("value", "100");
  expect(screen.queryByText(/Approval limit/)).toBeNull();
  expect(screen.queryByText("2026-11-23")).toBeNull();
  const history = await panel("Changes");
  expect(
    history.getByText("Spending limit for each round: $5.00 to $0.75"),
  ).toBeDefined();
  const models = await panel("Models allowed");
  expect(models.getByText("$0.10 in, $0.50 out").className).toContain("num");
});

it("asks before saving, listing each change, and sends every setting", async () => {
  const fetchMock = stubApi({
    "GET /api/settings": settings,
    "PUT /api/settings": changed,
  });
  renderAt("/settings");
  fireEvent.change(await spendingInput(), { target: { value: "0.75" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  const dialog = within(await screen.findByRole("dialog"));
  expect(
    dialog.getByText("Spending limit for each round: $5.00 to $0.75"),
  ).toBeDefined();

  fireEvent.click(dialog.getByRole("button", { name: "Cancel" }));
  expect(sent(fetchMock, "PUT /api/settings")).toEqual([]);

  await save();
  await waitFor(() => {
    expect(sent(fetchMock, "PUT /api/settings")).toHaveLength(1);
  });
  const { current } = settings;
  expect(sent(fetchMock, "PUT /api/settings")).toEqual([
    {
      objectives: current.objectives,
      noise: current.noise,
      tolerance: current.tolerance,
      spending_limit: 0.75,
      agents: current.agents,
      business_date: "2026-11-23",
    },
  ]);
  expect(
    await screen.findByText(/Last changed by Dana Whitfield/),
  ).toBeDefined();
  expect(screen.getByRole("button", { name: "Save" })).toHaveProperty(
    "disabled",
    true,
  );
});

it("never changes a setting the reviewer didn't touch", async () => {
  const precise = { ...settings.current, spending_limit: 0.755 };
  stubApi({ "GET /api/settings": { ...settings, current: precise } });
  renderAt("/settings");
  expect(await spendingInput()).toHaveProperty("value", "0.76");
  expect(screen.getByRole("button", { name: "Save" })).toHaveProperty(
    "disabled",
    true,
  );
});

it("shows why the backend refused a setting", async () => {
  stubApi({
    "GET /api/settings": settings,
    "PUT /api/settings": new Refusal(422, [
      {
        type: "greater_than",
        loc: ["body", "spending_limit"],
        msg: "Input should be greater than 0",
        input: 0,
      },
    ]),
  });
  renderAt("/settings");
  fireEvent.change(await spendingInput(), { target: { value: "0.6" } });
  await save();
  expect((await screen.findByRole("alert")).textContent).toBe(
    "spending_limit: Input should be greater than 0",
  );
});

it("shows a reviewer only the appearance, with why they can't see the settings", async () => {
  const fetchMock = stubApi({ "GET /api/me": priya });
  renderAt("/settings");
  expect(
    await screen.findByText(
      wholeText(
        "Only the compliance manager can see the settings. Priya Raman can't.",
      ),
    ),
  ).toBeDefined();
  expect(
    screen.getByRole("heading", { name: "Appearance", level: 1 }),
  ).toBeDefined();
  expect(screen.getByRole("group", { name: "Appearance" })).toBeDefined();
  expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  expect(screen.queryByRole("spinbutton")).toBeNull();
  expect(sent(fetchMock, "GET /api/settings")).toHaveLength(0);
});

it("keeps the appearance chosen in this browser", async () => {
  stubApi({ "GET /api/settings": settings });
  renderAt("/settings");
  await screen.findByRole("group", { name: "Appearance" });
  fireEvent.click(group("Appearance").getByLabelText("Dark"));
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem("payrollcheck-appearance")).toBe("dark");
  fireEvent.click(group("Appearance").getByLabelText("Same as this computer"));
  expect(document.documentElement.dataset.theme).toBeUndefined();
});

it("saves an objective on false exceptions and a notice score's noise", async () => {
  const fetchMock = stubApi({
    "GET /api/settings": settings,
    "PUT /api/settings": changed,
  });
  renderAt("/settings");
  await screen.findByRole("group", { name: "Noise" });
  fireEvent.change(
    group("Objectives on the held-out set").getByLabelText(
      "False exceptions at most",
    ),
    { target: { value: "3" } },
  );
  fireEvent.change(group("Noise").getByLabelText("Notice score"), {
    target: { value: "0.2" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  const dialog = within(await screen.findByRole("dialog"));
  expect(
    dialog.getByText(
      "False exceptions objective: 2.5 per 100 payrolls to 3 per 100 payrolls",
    ),
  ).toBeDefined();
  expect(dialog.getByText("Noise on notice score: 0.10 to 0.20")).toBeDefined();
  fireEvent.click(dialog.getByRole("button", { name: "Save the settings" }));
  await waitFor(() => {
    expect(sent(fetchMock, "PUT /api/settings")).toHaveLength(1);
  });
  const [values] = sent(fetchMock, "PUT /api/settings") as [
    { objectives: object; noise: object },
  ];
  expect(values.objectives).toEqual({
    ...settings.current.objectives,
    false_per_100: 3,
  });
  expect(values.noise).toEqual({
    ...settings.current.noise,
    notice_score: 0.2,
  });
});

it("changes the business date through the confirmation, and reads it again for the header", async () => {
  const moved = {
    ...settings.current,
    number: 2,
    business_date: "2026-11-30",
    changed_by: "Dana Whitfield",
    changed_at: "2026-11-23T09:00:00+00:00",
  };
  const fetchMock = stubApi({
    "GET /api/settings": settings,
    "PUT /api/settings": { ...settings, current: moved, changes: [moved] },
  });
  // The business date as the backend gives it once the save has gone through.
  const asked = fetchMock.getMockImplementation();
  fetchMock.mockImplementation((path: string, init?: RequestInit) =>
    path === "/api/business-date" &&
    sent(fetchMock, "PUT /api/settings").length > 0
      ? Promise.resolve(
          Response.json({ business_date: "2026-11-30", real_date: false }),
        )
      : (asked?.(path, init) ?? Promise.reject(new Error("No stub"))),
  );
  renderAt("/settings");
  await screen.findByRole("group", { name: "Business date" });
  const field = group("Business date").getByLabelText("Business date");
  expect(field).toHaveProperty("value", "2026-11-23");
  fireEvent.change(field, { target: { value: "2026-11-30" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(
    within(await screen.findByRole("dialog")).getByText(
      "Business date: Nov 23, 2026 to Nov 30, 2026",
    ),
  ).toBeDefined();
  await save();
  await waitFor(() => {
    expect(sent(fetchMock, "PUT /api/settings")).toHaveLength(1);
  });
  expect(sent(fetchMock, "PUT /api/settings")[0]).toMatchObject({
    business_date: "2026-11-30",
  });
  expect(await screen.findByText("Nov 30, 2026")).toBeDefined();
});

it("saves the real date, null, with Use the real date", async () => {
  const fetchMock = stubApi({
    "GET /api/settings": settings,
    "PUT /api/settings": settings,
  });
  renderAt("/settings");
  await screen.findByRole("group", { name: "Business date" });
  const useReal = await screen.findByRole("button", {
    name: "Use the real date",
  });
  fireEvent.click(useReal);
  expect(useReal).toHaveProperty("disabled", true);
  expect(group("Business date").getByText("The real date")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(
    within(await screen.findByRole("dialog")).getByText(
      "Business date: Nov 23, 2026 to the real date",
    ),
  ).toBeDefined();
  await save();
  await waitFor(() => {
    expect(sent(fetchMock, "PUT /api/settings")).toHaveLength(1);
  });
  expect(sent(fetchMock, "PUT /api/settings")[0]).toMatchObject({
    business_date: null,
  });
});
