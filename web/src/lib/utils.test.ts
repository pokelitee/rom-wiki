import { expect, it } from "vitest";
import { searchText, title } from "./utils";

it("lowercases search text exactly as the exporter does", () => {
  // tests/sites/test_frontend.py expects the same output from _search_text.
  expect(searchText("Straße ÉCLAIR İstanbul ΟΔΟΣ ﬁre")).toBe(
    "straße éclair i̇stanbul οδος ﬁre",
  );
});

it("labels fields in sentence case without changing proper names", () => {
  expect(title("base_experience")).toBe("Base experience");
  expect(title("egg_move_pokemon")).toBe("Egg move Pokémon");
  expect(title("ai_battle_items")).toBe("AI battle items");
  expect(title("height_dm")).toBe("Height");
  expect(title("level-up")).toBe("Level up");
  expect(title("Shed Skin")).toBe("Shed Skin");
  expect(title("rom")).toBe("ROM");
});
