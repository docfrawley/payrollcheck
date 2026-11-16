import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { municipal, project } from "./fixtures";
import { Refusal, caseRecord, panel, renderAt, sent, stubApi } from "./testing";

// The projects, a project's page with its subcontractors, and the upload of a
// payroll on it.

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const UPLOAD = "POST /api/projects/PRJ-02/payrolls";
const CSV = "contractor_name,fein\nDelaware Valley Masonry LLC,98-5117616\n";

function showProject(upload?: unknown) {
  const fetchMock = stubApi({
    "GET /api/projects/PRJ-02": project,
    ...(upload === undefined ? {} : { [UPLOAD]: upload }),
  });
  renderAt("/projects/PRJ-02");
  return fetchMock;
}

async function uploadAs(subcontractorId: string) {
  const form = await panel("Upload a payroll");
  const button = form.getByRole("button", { name: "Upload" });
  expect(button.getAttribute("aria-disabled")).toBe("true");
  fireEvent.change(form.getByRole("combobox", { name: "Subcontractor" }), {
    target: { value: subcontractorId },
  });
  fireEvent.change(form.getByLabelText("Payroll file"), {
    target: {
      files: [new File([CSV], "PC-1214-1.csv", { type: "text/csv" })],
    },
  });
  expect(button.getAttribute("aria-disabled")).toBe("false");
  fireEvent.click(button);
  return form;
}

it("lists the projects, each linked to its page", async () => {
  stubApi({ "GET /api/projects": [municipal] });
  renderAt("/projects");
  const link = await screen.findByRole("link", { name: "Municipal building" });
  expect(link.getAttribute("href")).toBe("/projects/PRJ-02");
  const row = within(link.closest("tr") ?? document.body);
  expect(row.getByText("PRJ-02")).toBeDefined();
  expect(row.getByText("City of New Brunswick")).toBeDefined();
  expect(row.getByText("Aug 3, 2026")).toBeDefined();
  const nav = within(screen.getByRole("navigation", { name: "Main" }));
  expect(
    nav.getByRole("link", { name: "Projects" }).getAttribute("aria-current"),
  ).toBe("page");
});

it("shows a project with its subcontractors and their engagement windows", async () => {
  showProject();
  expect(
    await screen.findByRole("heading", {
      name: "Municipal building",
      level: 1,
    }),
  ).toBeDefined();
  expect(screen.getByText("New Brunswick, Middlesex County")).toBeDefined();
  expect((await panel("Project")).getByText("NB-2026-114")).toBeDefined();
  const rows = (await panel("Subcontractors")).getAllByRole("row").slice(1);
  expect(rows.map((row) => row.textContent)).toEqual([
    "Garden State Electric LLCSUB-0162-9917837177511Sep 6, 2026Nov 22, 2026",
    "Delaware Valley Masonry LLCSUB-0698-5117616941034Sep 13, 2026Dec 20, 2026",
  ]);
});

it("uploads a payroll for the subcontractor chosen and links to its case", async () => {
  const created = {
    ...caseRecord,
    case_id: "PC-1214",
    project_id: "PRJ-02",
  };
  const fetchMock = showProject(created);
  const form = await uploadAs("SUB-06");
  const done = await form.findByRole("status");
  expect(done.textContent).toBe("Uploaded as PC-1214, Received.");
  expect(
    within(done).getByRole("link", { name: "PC-1214" }).getAttribute("href"),
  ).toBe("/cases/PC-1214");
  expect(sent(fetchMock, UPLOAD)).toEqual([
    { subcontractor_id: "SUB-06", file_name: "PC-1214-1.csv", content: CSV },
  ]);
});

it("shows why an upload was refused, and creates no link", async () => {
  const reason = "This payroll is for PRJ-01, not PRJ-02.";
  const fetchMock = showProject(new Refusal(422, reason));
  const form = await uploadAs("SUB-01");
  expect((await form.findByRole("alert")).textContent).toBe(reason);
  expect(form.queryByRole("link")).toBeNull();
  await waitFor(() => {
    expect(sent(fetchMock, UPLOAD)).toHaveLength(1);
  });
  expect(sent(fetchMock, UPLOAD)[0]).toMatchObject({
    subcontractor_id: "SUB-01",
  });
});

it("says when a project doesn't exist", async () => {
  stubApi({});
  renderAt("/projects/PRJ-99");
  expect(
    await screen.findByText("Project not found. Choose one from the projects."),
  ).toBeDefined();
});
