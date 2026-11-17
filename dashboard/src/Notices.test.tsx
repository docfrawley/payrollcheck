import { cleanup, fireEvent } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Case } from "./api";
import { awaiting, reviewPanel, showCase } from "./caseTesting";
import { Refusal, marcus, panel, sent } from "./testing";

// A notice with nothing in it, for building one in a test.
const noNotice = {
  submission_no: 1,
  draft: null,
  drafted_by: null,
  drafted_at: null,
  edited_text: null,
  edited_by: null,
  edited_at: null,
  sent_by: null,
  sent_at: null,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const EDITED = "Please pay Kim Dimitrov the journeyman base rate and sign.";

it("lets any reviewer edit the notice and send the case back with it", async () => {
  const { routes, fetchMock } = showCase(awaiting);
  routes["GET /api/me"] = marcus;
  const notice = await panel("Send-back notice");
  fireEvent.change(notice.getByLabelText("The notice to the subcontractor"), {
    target: { value: EDITED },
  });
  const returned: Case = {
    ...awaiting,
    status: "returned_to_sub",
    reviewed_by: "HND-02",
    reviewed_on: "2026-11-23",
    sent_notices: [
      {
        outbox_id: 1,
        submission_no: 1,
        to_address: "payroll@gardenstateelectric.example",
        subject:
          "Certified payroll PC-1201, Lincoln School renovation, week ending Nov 22, 2026: corrections needed",
        body: EDITED,
        sent_by: "Marcus Oyelaran <marcus.oyelaran@payrollcheck.example>",
        sent_at: "2026-11-23T15:00:00+00:00",
        draft: awaiting.notice?.draft ?? null,
        drafted_by: awaiting.notice?.drafted_by ?? null,
      },
    ],
  };
  routes["PUT /api/cases/PC-1201/notice"] = awaiting;
  routes["POST /api/cases/PC-1201/send-back"] = returned;
  routes["GET /api/cases/PC-1201"] = returned;
  fireEvent.click(notice.getByRole("button", { name: "Send back" }));

  const review = await reviewPanel();
  expect(
    await review.findByText("Sent back to the subcontractor on Nov 23, 2026."),
  ).toBeDefined();
  expect(sent(fetchMock, "PUT /api/cases/PC-1201/notice")).toEqual([
    { text: EDITED },
  ]);
  expect(sent(fetchMock, "POST /api/cases/PC-1201/send-back")).toEqual([
    { text: EDITED },
  ]);
  const email = await panel("Sent to the subcontractor");
  expect(email.getByText("payroll@gardenstateelectric.example")).toBeDefined();
  expect(
    email.getByText(/week ending Nov 22, 2026: corrections needed/),
  ).toBeDefined();
  expect(email.getByText(EDITED)).toBeDefined();
  expect(email.getByText(/^Drafted by /)).toBeDefined();
});

it("saves an edit of the notice without sending it", async () => {
  const { routes, fetchMock } = showCase(awaiting);
  const notice = await panel("Send-back notice");
  fireEvent.change(notice.getByLabelText("The notice to the subcontractor"), {
    target: { value: EDITED },
  });
  routes["PUT /api/cases/PC-1201/notice"] = new Refusal(
    409,
    "Case PC-1201 is not awaiting review",
  );
  fireEvent.click(notice.getByRole("button", { name: "Save" }));
  expect((await notice.findByRole("alert")).textContent).toBe(
    "Case PC-1201 is not awaiting review",
  );
  expect(sent(fetchMock, "PUT /api/cases/PC-1201/notice")).toEqual([
    { text: EDITED },
  ]);
  expect(sent(fetchMock, "POST /api/cases/PC-1201/send-back")).toHaveLength(0);
});

it("saves an edit, and says who edited it beside the draft", async () => {
  const { routes, fetchMock } = showCase(awaiting);
  const notice = await panel("Send-back notice");
  const save = notice.getByRole("button", { name: "Save" });
  expect(save.getAttribute("aria-disabled")).toBe("true");
  fireEvent.change(notice.getByLabelText("The notice to the subcontractor"), {
    target: { value: EDITED },
  });
  const edited: Case = {
    ...awaiting,
    notice: {
      ...(awaiting.notice ?? noNotice),
      edited_text: EDITED,
      edited_by: "Dana Whitfield",
      edited_at: "2026-11-23T15:00:00+00:00",
    },
  };
  routes["PUT /api/cases/PC-1201/notice"] = edited;
  routes["GET /api/cases/PC-1201"] = edited;
  fireEvent.click(save);
  expect(await notice.findByText(/; edited by Dana Whitfield, /)).toBeDefined();
  expect(sent(fetchMock, "PUT /api/cases/PC-1201/notice")).toEqual([
    { text: EDITED },
  ]);
});

it("says when the agent drafted no notice and the reviewer wrote one", async () => {
  showCase({
    ...awaiting,
    notice: {
      ...noNotice,
      edited_text: EDITED,
      edited_by: "Dana Whitfield",
      edited_at: "2026-11-23T15:00:00+00:00",
    },
  });
  const notice = await panel("Send-back notice");
  expect(notice.getByText(/^No draft; edited by Dana Whitfield/)).toBeDefined();
});

it("keeps a saved edit and reloads the case when the send back fails", async () => {
  const { routes, fetchMock } = showCase(awaiting);
  const notice = await panel("Send-back notice");
  fireEvent.change(notice.getByLabelText("The notice to the subcontractor"), {
    target: { value: EDITED },
  });
  routes["PUT /api/cases/PC-1201/notice"] = awaiting;
  routes["POST /api/cases/PC-1201/send-back"] = new Refusal(
    409,
    "Case PC-1201 is not awaiting review",
  );
  const reads = sent(fetchMock, "GET /api/cases/PC-1201").length;
  fireEvent.click(notice.getByRole("button", { name: "Send back" }));
  expect((await notice.findByRole("alert")).textContent).toBe(
    "Case PC-1201 is not awaiting review",
  );
  expect(sent(fetchMock, "PUT /api/cases/PC-1201/notice")).toHaveLength(1);
  await vi.waitFor(() => {
    expect(sent(fetchMock, "GET /api/cases/PC-1201").length).toBeGreaterThan(
      reads,
    );
  });
});

it("sends an unchanged draft back without saving it as an edit", async () => {
  const { routes, fetchMock } = showCase(awaiting);
  const notice = await panel("Send-back notice");
  routes["POST /api/cases/PC-1201/send-back"] = awaiting;
  fireEvent.click(notice.getByRole("button", { name: "Send back" }));
  await vi.waitFor(() => {
    expect(sent(fetchMock, "POST /api/cases/PC-1201/send-back")).toHaveLength(
      1,
    );
  });
  expect(sent(fetchMock, "PUT /api/cases/PC-1201/notice")).toHaveLength(0);
});

it("on a case returned to its subcontractor, edits the notice and sends it again, with the earlier sends", async () => {
  const first = {
    outbox_id: 1,
    submission_no: 1,
    to_address: "payroll@gardenstateelectric.example",
    subject: "Certified payroll PC-1201: corrections needed",
    body: "Please correct line 1.",
    sent_by: "Marcus Oyelaran <marcus.oyelaran@payrollcheck.example>",
    sent_at: "2026-11-23T15:00:00+00:00",
    draft: null,
    drafted_by: null,
  };
  const returned: Case = {
    ...awaiting,
    status: "returned_to_sub",
    reviewed_by: "HND-02",
    reviewed_on: "2026-11-23",
    notice: {
      ...noNotice,
      draft: "Please correct line 1.",
      drafted_by: "PayrollCheck Copilot for Marcus Oyelaran",
      drafted_at: "2026-11-23T14:00:00+00:00",
      sent_by: "Marcus Oyelaran",
      sent_at: "2026-11-23T15:00:00+00:00",
    },
    sent_notices: [first],
  };
  const { routes, fetchMock } = showCase(returned);
  const notice = await panel("Send-back notice");
  expect(
    notice.getByText(/^Drafted by PayrollCheck Copilot for Marcus Oyelaran/),
  ).toBeDefined();
  expect(notice.queryByRole("button", { name: "Send back" })).toBeNull();
  fireEvent.change(notice.getByLabelText("The notice to the subcontractor"), {
    target: { value: EDITED },
  });
  const again = {
    ...returned,
    sent_notices: [{ ...first, outbox_id: 2, body: EDITED }, first],
  };
  routes["PUT /api/cases/PC-1201/notice"] = returned;
  routes["POST /api/cases/PC-1201/notice/resend"] = again;
  routes["GET /api/cases/PC-1201"] = again;
  fireEvent.click(notice.getByRole("button", { name: "Send again" }));
  const emails = await panel("Sent to the subcontractor");
  expect(await emails.findByText(EDITED)).toBeDefined();
  expect(emails.getByText("Please correct line 1.")).toBeDefined();
  expect(sent(fetchMock, "PUT /api/cases/PC-1201/notice")).toEqual([
    { text: EDITED },
  ]);
  expect(sent(fetchMock, "POST /api/cases/PC-1201/notice/resend")).toEqual([
    { text: EDITED },
  ]);
});
