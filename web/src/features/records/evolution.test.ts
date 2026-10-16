import { describe, expect, it } from "vitest";
import { evolutionCondition } from "./evolution";

describe("evolution conditions", () => {
  it("describes level, item, and party conditions with linked references", () => {
    expect(
      evolutionCondition({
        method: { id: 4, name: "level" },
        parameter: 16,
        parameter_data: { kind: "level", value: 16 },
      }),
    ).toEqual(["Level 16"]);
    expect(
      evolutionCondition({
        method: { name: "use-item" },
        parameter_data: {
          kind: "item",
          name: "Moon Stone",
          slug: "moon-stone",
        },
      }),
    ).toEqual(["Use ", { name: "Moon Stone", route: "items/moon-stone" }]);
    expect(
      evolutionCondition({
        method: { name: "level-with-party-species" },
        parameter_data: { kind: "pokemon", name: "Remoraid", slug: "remoraid" },
      }),
    ).toEqual([
      "Level up with ",
      { name: "Remoraid", route: "pokemon/remoraid" },
      " in the party",
    ]);
  });

  it("names moves by their proper name without inventing a route", () => {
    expect(
      evolutionCondition({
        method: { name: "level-knowing-move" },
        parameter_data: { id: 102, kind: "move", name: "mimic" },
      }),
    ).toEqual(["Level up knowing ", { name: "Mimic" }]);
  });

  it("falls back to the method's name for unknown methods", () => {
    expect(evolutionCondition({ method: { name: "spin-around" } })).toEqual([
      "Spin around",
    ]);
  });
});
