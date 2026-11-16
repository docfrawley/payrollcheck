import { expect, it } from "vitest";
import {
  cents,
  date,
  duration,
  evaluationSetName,
  initials,
  label,
  modelCost,
  money,
  stoppedBecause,
} from "./format";

it("takes a reviewer's initials from their first and last names", () => {
  expect(initials("Dana Whitfield")).toBe("DW");
  expect(initials("Mary Ann Okafor")).toBe("MO");
});

it("formats money in US dollars", () => {
  expect(money(1150)).toBe("$1,150.00");
  expect(money(0)).toBe("$0.00");
});

it("says why a run stopped in one sentence", () => {
  expect(stoppedBecause("The agent stopped answering")).toBe(
    "Stopped: The agent stopped answering.",
  );
  expect(stoppedBecause("RuntimeError: The connection was lost.")).toBe(
    "Stopped: RuntimeError: The connection was lost.",
  );
});

it("formats dates without shifting the day", () => {
  expect(date("2026-06-24")).toBe("Jun 24, 2026");
});

it("formats amounts kept in cents in US dollars", () => {
  expect(cents(128460)).toBe("$1,284.60");
  expect(cents(5)).toBe("$0.05");
});

it("names an evaluation's set and its size", () => {
  expect(evaluationSetName("tiny", 10)).toBe("Tiny set, 10 payrolls");
  expect(evaluationSetName("held_out", 1)).toBe("Held-out set, 1 payroll");
});

it("turns codes into labels", () => {
  expect(label("check_rates")).toBe("Check rates");
});

it("formats model costs to four places, since they're often under a cent", () => {
  expect(modelCost(0.0125)).toBe("$0.0125");
  expect(modelCost(1.5)).toBe("$1.5000");
});

it("formats lengths of time in minutes and seconds", () => {
  expect(duration(41.4)).toBe("41 s");
  expect(duration(161)).toBe("2 min 41 s");
  expect(duration(0)).toBe("0 s");
  expect(duration(120)).toBe("2 min");
});
