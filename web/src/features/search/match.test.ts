import { describe, expect, it } from "vitest";
import { matchSearch, type SearchEntry } from "./match";

const entries: SearchEntry[] = [
  {
    label: "Bulbasaur",
    path: "/platinum/pokemon/bulbasaur",
    section: "pokemon",
  },
  {
    label: "Overgrow",
    path: "/platinum/abilities/overgrow",
    section: "abilities",
  },
  {
    label: "Data sources",
    path: "/platinum/docs/data-sources",
    section: "Documentation",
    search: "# data sources\n\nsynthetic data; no rom inputs.",
  },
];

describe("game search matching", () => {
  it("matches record labels case-insensitively after trimming", () => {
    expect(
      matchSearch(entries, "  BULBA ").map((entry) => entry.label),
    ).toEqual(["Bulbasaur"]);
  });

  it("matches guides by their full text rather than their label", () => {
    expect(
      matchSearch(entries, "rom inputs").map((entry) => entry.label),
    ).toEqual(["Data sources"]);
  });

  it("returns nothing for an unmatched term", () => {
    expect(matchSearch(entries, "zzz")).toEqual([]);
  });
});
