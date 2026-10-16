import { expect, it } from "vitest";
import { changeSummary } from "./change-summary";

it("summarizes changed fields with simple values inline", () => {
  expect(
    changeSummary({
      changes: [
        { field: "hatch_cycles", label: "Hatch cycles", before: 20, after: 0 },
        {
          field: "abilities",
          label: "Abilities",
          before: [{ name: "Overgrow" }],
          after: [{ name: "Chlorophyll" }],
        },
        {
          field: "type",
          label: "Type",
          before: { id: 0, name: "normal" },
          after: { id: 17, name: "fairy" },
        },
        {
          field: "held_item",
          label: "Held item",
          before: null,
          after: "Leftovers",
        },
      ],
    }),
  ).toBe(
    "Hatch cycles 20 → 0 · Abilities · Type normal → fairy · Held item none → Leftovers",
  );
  expect(changeSummary({})).toBe("");
});
