import { describe, expect, it } from "vitest";
import {
  formatName,
  formatScalar,
  isEmpty,
  isNamedReference,
  isTechnical,
  orderEntries,
} from "./fields";

describe("record field rules", () => {
  it("treats identifiers, storage details, and provenance as technical", () => {
    for (const key of [
      "id",
      "move_id",
      "flags",
      "table_index",
      "reward_item_ids",
      "multiplier_provenance",
      "pokemon_slug",
      "internal_name",
      "x",
    ])
      expect(isTechnical(key)).toBe(true);
    for (const key of ["name", "level", "abilities", "gender_ratio"])
      expect(isTechnical(key)).toBe(false);
  });

  it("finds sections with nothing to show", () => {
    expect(isEmpty([])).toBe(true);
    expect(isEmpty([0, 0, 0, 0, 0])).toBe(true);
    expect(isEmpty({ id: 0, is_hidden: false, name: null, slug: null })).toBe(
      true,
    );
    expect(isEmpty({ attack: 0, special_attack: 1 })).toBe(false);
    expect(isEmpty([{ chance: 40, pokemon: { name: "Starly" } }])).toBe(false);
    expect(isEmpty([{ chance: 40, pokemon: null }])).toBe(true);
    expect(isEmpty([{ id: 0, name: null, rarity: "common", slug: null }])).toBe(
      true,
    );
    expect(
      isEmpty([
        { id: 154, name: "Leppa Berry", rarity: "common", slug: "leppa-berry" },
      ]),
    ).toBe(false);
  });

  it("recognizes objects that only name something", () => {
    expect(isNamedReference({ id: 3, name: "green" })).toBe(true);
    expect(isNamedReference({ id: 81, kind: "item", name: "Moon Stone" })).toBe(
      true,
    );
    expect(
      isNamedReference({ id: 65, is_hidden: false, name: "Overgrow" }),
    ).toBe(false);
    expect(isNamedReference({ kind: "level", value: 16 })).toBe(false);
  });

  it("puts a section's primary fields first and keeps the rest in order", () => {
    const entries: [string, number][] = [
      ["body_color", 1],
      ["egg_groups", 2],
      ["abilities", 3],
      ["zz_custom", 4],
      ["evolutions", 5],
    ];
    expect(orderEntries("pokemon", entries).map(([key]) => key)).toEqual([
      "abilities",
      "evolutions",
      "egg_groups",
      "body_color",
      "zz_custom",
    ]);
    expect(orderEntries("unknown", entries)).toEqual(entries);
  });

  it("formats stored values in the units and words players use", () => {
    expect(formatScalar("gender_ratio", 31)).toBe("87.5% male");
    expect(formatScalar("gender_ratio", 255)).toBe("Genderless");
    expect(formatScalar("height_dm", 7)).toBe("0.7 m");
    expect(formatScalar("weight_hg", 69)).toBe("6.9 kg");
    expect(formatScalar("battle_mode", 1)).toBe("Double");
    expect(formatScalar("is_hidden", false)).toBe("No");
    expect(formatScalar("catch_rate", 1200)).toBe("1,200");
    expect(formatScalar("egg_group", "monster")).toBe("Monster");
    expect(formatScalar("category", "damage-ailment")).toBe("Damage ailment");
    expect(formatScalar("internal_name", "R201")).toBe("R201");
    expect(formatScalar("name", "Shed Skin")).toBe("Shed Skin");
    expect(formatName("stealth-rock")).toBe("Stealth Rock");
    expect(formatName("Mr. Mime")).toBe("Mr. Mime");
  });
});
