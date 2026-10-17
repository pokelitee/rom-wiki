import { describe, expect, it } from "vitest";
import { columnRoute, entityRoute } from "./routes";

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
    expect(entityRoute({ item_id: 17, item_slug: "potion" }, "items")).toBe(
      "items/potion",
    );
  });

  it("routes slugs by the field that holds them", () => {
    const slug = { slug: "overgrow" };
    expect(entityRoute(slug, "abilities")).toBe("abilities/overgrow");
    expect(entityRoute(slug, "level_up_moves")).toBe("moves/overgrow");
    expect(entityRoute(slug, "held_items")).toBe("items/overgrow");
    expect(entityRoute(slug, "victory_item")).toBe("items/overgrow");
    expect(entityRoute(slug, "base_species")).toBe("pokemon/overgrow");
    expect(entityRoute(slug, "evolutions")).toBe("pokemon/overgrow");
  });

  it("routes species by their Pokédex number before the field name", () => {
    const charmander = { name: "Charmander", slug: "charmander" };
    expect(
      entityRoute({ ...charmander, national_dex_id: 4 }, "egg_move_pokemon"),
    ).toBe("pokemon/charmander");
    expect(
      entityRoute({ ...charmander, national_dex_id: 4 }, "wild_held_by"),
    ).toBe("pokemon/charmander");
  });

  it("routes evolution endpoints, parameters, and revived fossils", () => {
    const ivysaur = { id: 2, name: "Ivysaur", slug: "ivysaur" };
    expect(entityRoute(ivysaur, "target")).toBe("pokemon/ivysaur");
    expect(entityRoute(ivysaur, "source")).toBe("pokemon/ivysaur");
    expect(entityRoute(ivysaur, "revives_into")).toBe("pokemon/ivysaur");
    expect(entityRoute(ivysaur, "radar")).toBe("pokemon/ivysaur");
    expect(entityRoute(ivysaur, "hoenn_radio")).toBe("pokemon/ivysaur");
    expect(
      entityRoute({ kind: "item", slug: "moon-stone" }, "parameter_data"),
    ).toBe("items/moon-stone");
    expect(
      entityRoute({ kind: "pokemon", slug: "remoraid" }, "parameter_data"),
    ).toBe("pokemon/remoraid");
    expect(
      entityRoute({ kind: "level", slug: "x" }, "parameter_data"),
    ).toBeUndefined();
  });

  it("leaves unlinked values without a route", () => {
    expect(entityRoute({ slug: "grass" }, "types")).toBeUndefined();
    expect(entityRoute({ slug: "dynamic-punch" }, "replaces")).toBeUndefined();
    expect(entityRoute({ name: "Overgrow" }, "abilities")).toBeUndefined();
    expect(entityRoute({ slug: null }, "abilities")).toBeUndefined();
  });

  it("links name columns that carry their own slug or map header", () => {
    const row = {
      held_item_name: "Colbur Berry",
      held_item_slug: "colbur-berry",
      location_id: 115,
      location_name: "Hearthome City",
      class_name: "Psychic",
    };
    expect(columnRoute(row, "held_item_name")).toBe("items/colbur-berry");
    expect(columnRoute(row, "location_name")).toBe("locations/header-115");
    expect(columnRoute(row, "class_name")).toBeUndefined();
    expect(columnRoute(row, "level")).toBeUndefined();
  });
});
