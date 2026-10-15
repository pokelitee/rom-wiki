import { describe, expect, it } from "vitest";
import type { IndexRecord } from "../../data/types";
import { filterRecords, pageNumber } from "./filter";

const records: IndexRecord[] = [
  {
    id: "bulbasaur",
    label: "Bulbasaur",
    search: "bulbasaur grass poison overgrow",
    fields: { name: "Bulbasaur", types: ["grass", "poison"], bst: 318 },
    chunk: "a.json",
  },
  {
    id: "charmander",
    label: "Charmander",
    search: "charmander fire blaze",
    fields: { name: "Charmander", types: ["fire"], bst: 309 },
    chunk: "a.json",
  },
  {
    id: "venusaur",
    label: "Venusaur",
    search: "venusaur grass poison overgrow",
    fields: { name: "Venusaur", types: ["grass", "poison"], bst: 525 },
    chunk: "b.json",
  },
];

describe("catalog navigation state", () => {
  it("combines search, a facet, ranges, and descending sort", () => {
    const params = new URLSearchParams(
      "q=overgrow&f.types=grass&min.bst=300&max.bst=600&sort=bst&dir=desc",
    );
    expect(filterRecords(records, params).map((row) => row.id)).toEqual([
      "venusaur",
      "bulbasaur",
    ]);
    expect(records[0].id).toBe("bulbasaur");
  });
  it("does not match an unrelated facet", () => {
    expect(
      filterRecords(records, new URLSearchParams("q=bulbasaur&f.types=fire")),
    ).toEqual([]);
  });
  it("handles malformed and out-of-range page parameters", () => {
    expect(pageNumber(new URLSearchParams("page=NaN"), 200)).toBe(1);
    expect(pageNumber(new URLSearchParams("page=-4"), 200)).toBe(1);
    expect(pageNumber(new URLSearchParams("page=99"), 51)).toBe(2);
    expect(pageNumber(new URLSearchParams("page=3"), 0)).toBe(1);
  });
});
