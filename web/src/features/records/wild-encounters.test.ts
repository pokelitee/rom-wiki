import { describe, expect, it } from "vitest";
import { compactEncounters } from "./wild-encounters";

const route6 = {
  area_name: "Route 6",
  encounter_route_key: "map-107",
  method: "Grass / cave",
  minimum_level: 23,
  maximum_level: 25,
  chance: 30,
  condition: null,
};

describe("wild encounter rows", () => {
  it("merges seasons and versions of the same encounter", () => {
    const rows = ["spring", "summer", "autumn", "winter"].flatMap((season) =>
      ["black-2", "white-2"].map((version) => ({
        ...route6,
        season,
        versions: [version],
      })),
    );
    expect(compactEncounters(rows, ["black-2", "white-2"])).toEqual([
      {
        area: "Route 6",
        route: "map-107",
        method: "Grass / cave",
        levels: "23–25",
        chance: 30,
        when: [],
        versions: [],
      },
    ]);
  });

  it("names the seasons, times, conditions, and versions that differ", () => {
    const [row] = compactEncounters(
      [
        { ...route6, season: "spring", versions: ["black-2"] },
        { ...route6, season: "summer", versions: ["black-2"] },
      ],
      ["black-2", "white-2"],
    );
    expect(row.when).toEqual(["Spring", "Summer"]);
    expect(row.versions).toEqual(["black-2"]);
    const [timed] = compactEncounters(
      [
        {
          ...route6,
          condition: "morning; dual-slot: leaf-green",
          versions: [],
        },
        { ...route6, condition: "day; dual-slot: leaf-green", versions: [] },
      ],
      ["platinum"],
    );
    expect(timed.when).toEqual(["Morning", "Day", "Dual slot: LeafGreen"]);
    expect(timed.versions).toEqual([]);
  });

  it("links numbered areas and leaves unknown levels blank", () => {
    const [row] = compactEncounters(
      [
        {
          ...route6,
          encounter_route_key: 115,
          minimum_level: null,
          maximum_level: null,
        },
      ],
      ["heart-gold", "soul-silver"],
    );
    expect(row.route).toBe("area-115");
    expect(row.levels).toBe("—");
  });
});
