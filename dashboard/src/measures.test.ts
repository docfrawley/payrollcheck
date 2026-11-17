import { expect, test } from "vitest";
import type { Measures } from "./api";
import { measures } from "./improvementTesting";
import { MEASURES, ROUND_MEASURES } from "./measures";

const shownBy = (
  list: typeof ROUND_MEASURES,
  changed: Partial<Measures>,
): Record<string, string> =>
  Object.fromEntries(
    list.map(({ label, show }) => [
      label,
      show({ ...measures(1), ...changed }),
    ]),
  );

test("a score just short of its objective never shows as meeting it", () => {
  const justShort = {
    catch_rate: 0.9195,
    shortfall_accuracy: 0.996,
    notice_score: 0.79961,
    false_per_100: 2.5049,
    notices_graded: 30,
  };
  const round = shownBy(ROUND_MEASURES, justShort);
  expect(round["Catch rate"]).toBe("91.9%");
  expect(round["Shortfall accuracy"]).toBe("99.6%");
  expect(round["Notice score"]).toBe("0.799");
  expect(round["False per 100"]).toBe("2.51");
  const scoreboard = shownBy(MEASURES, justShort);
  expect(scoreboard["Catch rate"]).toMatch(/^91\.9% /);
  expect(scoreboard["Shortfall accuracy"]).toBe("99.6%");
  expect(scoreboard["Notice score"]).toBe("0.799 (30 graded)");
  expect(scoreboard["False exceptions"]).toBe("2 (2.51 per 100)");
});

test("a score exactly at its objective shows as it is", () => {
  const round = shownBy(ROUND_MEASURES, {
    catch_rate: 0.92,
    shortfall_accuracy: 1,
    notice_score: 0.8,
    false_per_100: 2.5,
  });
  expect(round["Catch rate"]).toBe("92.0%");
  expect(round["Shortfall accuracy"]).toBe("100.0%");
  expect(round["Notice score"]).toBe("0.800");
  expect(round["False per 100"]).toBe("2.50");
});
