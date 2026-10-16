import { describe, expect, it } from "vitest";
import { entityRoute } from "./routes";

describe("entity routes", () => {
  it("prefers explicit record identities over slugs", () => {
    expect(entityRoute({ encounter_route_key: 7, slug: "x" }, "")).toBe(
      "encounters/area-007",
    );
    expect(entityRoute({ encounter_route_key: "headbutt-003" }, "")).toBe(
      "encounters/headbutt-003",
    );
    expect(entityRoute({ trainer_id: 42 }, "")).toBe("trainers/trainer-0042");
    expect(entityRoute({ header_id: 5 }, "")).toBe("locations/header-005");
    expect(entityRoute({ pokemon_slug: "ivysaur", slug: "x" }, "move")).toBe(
      "pokemon/ivysaur",
    );
  });

  it("routes slugs by the field that holds them", () => {
    const slug = { slug: "overgrow" };
    expect(entityRoute(slug, "abilities")).toBe("abilities/overgrow");
    expect(entityRoute(slug, "level_up_moves")).toBe("moves/overgrow");
    expect(entityRoute(slug, "replaces")).toBe("moves/overgrow");
    expect(entityRoute(slug, "held_items")).toBe("items/overgrow");
    expect(entityRoute(slug, "victory_item")).toBe("items/overgrow");
    expect(entityRoute(slug, "base_species")).toBe("pokemon/overgrow");
    expect(entityRoute(slug, "evolutions")).toBe("pokemon/overgrow");
  });

  it("leaves unlinked values without a route", () => {
    expect(entityRoute({ slug: "grass" }, "types")).toBeUndefined();
    expect(entityRoute({ name: "Overgrow" }, "abilities")).toBeUndefined();
    expect(entityRoute({ slug: null }, "abilities")).toBeUndefined();
  });
});
