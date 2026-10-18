import { describe, expect, it } from "vitest";
import { isSlotList, slotGroups, summarizeSlots } from "./encounter";

const starly = { name: "Starly", slug: "starly" };
const bidoof = { name: "Bidoof", slug: "bidoof" };

describe("encounter slots", () => {
  it("recognizes slot-shaped rows", () => {
    expect(isSlotList([{ chance: 20, level: 2, pokemon: starly }])).toBe(true);
    expect(isSlotList([{ name: "Overgrow", is_hidden: false }])).toBe(false);
    expect(isSlotList([])).toBe(false);
  });

  it("combines repeated species and drops unused slots", () => {
    expect(
      summarizeSlots([
        { chance: 20, level: 2, pokemon: starly },
        { chance: 20, level: 2, pokemon: bidoof },
        { chance: 10, level: 3, pokemon: starly },
        { chance: 40, maximum_level: 0, minimum_level: 0, pokemon: null },
      ]),
    ).toEqual([
      { pokemon: starly, minimumLevel: 2, maximumLevel: 3, chance: 30 },
      { pokemon: bidoof, minimumLevel: 2, maximumLevel: 2, chance: 20 },
    ]);
  });

  it("keeps level ranges from minimum and maximum levels", () => {
    expect(
      summarizeSlots([
        { chance: 60, minimum_level: 20, maximum_level: 30, pokemon: starly },
      ]),
    ).toEqual([
      { pokemon: starly, minimumLevel: 20, maximumLevel: 30, chance: 60 },
    ]);
  });

  it("groups conditional tables and merges conditions with the same Pokémon", () => {
    const pair = [
      { chance: 4, level: 4, pokemon: starly },
      { chance: 4, level: 4, pokemon: bidoof },
    ];
    expect(
      slotGroups({
        day: [{ chance: 10, level: 3, pokemon: starly }],
        dual_slot: { emerald: pair, "fire-red": pair, ruby: [] },
        radar: [starly, starly],
        unown_forms: [],
      }),
    ).toEqual([
      {
        labels: ["Day"],
        slots: [
          { pokemon: starly, minimumLevel: 3, maximumLevel: 3, chance: 10 },
        ],
      },
      {
        labels: ["Dual slot", "Emerald, FireRed"],
        slots: [
          { pokemon: starly, minimumLevel: 4, maximumLevel: 4, chance: 4 },
          { pokemon: bidoof, minimumLevel: 4, maximumLevel: 4, chance: 4 },
        ],
      },
      {
        labels: ["Poké Radar"],
        slots: [
          {
            pokemon: starly,
            minimumLevel: null,
            maximumLevel: null,
            chance: null,
          },
        ],
      },
    ]);
  });

  it("leaves values that are not encounter tables alone", () => {
    expect(
      slotGroups({ note: "Only after the National Dex", day: [] }),
    ).toBeNull();
    expect(
      slotGroups({
        rate: 30,
        slots: [{ chance: 20, level: 2, pokemon: starly }],
      }),
    ).toHaveLength(1);
  });
});
