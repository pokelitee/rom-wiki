import { expect, it } from "vitest";
import { searchText } from "./utils";

it("lowercases search text exactly as the exporter does", () => {
  // tests/sites/test_frontend.py expects the same output from _search_text.
  expect(searchText("Straße ÉCLAIR İstanbul ΟΔΟΣ ﬁre")).toBe(
    "straße éclair i̇stanbul οδος ﬁre",
  );
});
