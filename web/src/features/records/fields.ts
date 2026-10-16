import type { Json } from "../../data/types";
import { title } from "../../lib/utils";

// Fields shown only when the game publishes the matching feature.
export const OPTIONAL_FEATURES: Record<string, string> = {
  egg_moves: "egg-moves",
  tutor_moves: "move-tutors",
  victory_item: "victory-items",
  post_battle_healing: "post-battle-healing",
};

// ROM identifiers, storage details, and provenance. Record pages keep these
// in their collapsed source details instead of the main content.
const TECHNICAL =
  /(?:^id$|_id$|_flags$|^flags$|_offset$|_provenance$|^provenance$|^unknown_|^data_archive|^trailing_|^sprite|^portrait|^cry$|^public$|^slug$|_slug$|^member$|^flip_sprite$|^source$|^source_fields$|^moves_source$|^table_index$|^battle_type$|^has_custom_moves$|^has_held_items$|^party_count$|^internal_name$|^section_name_source$|^bonus_slot_methodology_source$|^encounter_map_index$|^map_index$|^rom_sha256$|^archive$|^trainer_type$|^object_index$|^[xyz]$|^version$|^flavor_text_version$)/;

export function isTechnical(key: string): boolean {
  return TECHNICAL.test(key);
}

function isBlank(value: Json | undefined): boolean {
  return (
    value === undefined ||
    value === null ||
    value === "" ||
    value === 0 ||
    value === false
  );
}

// True when a record section has nothing to show: no entries, or only
// zeros, blanks, and technical fields.
export function isEmpty(value: Json | undefined): boolean {
  if (Array.isArray(value))
    return value.every((entry) => isBlank(entry) || isEmpty(entry));
  if (value && typeof value === "object")
    return Object.entries(value).every(
      ([key, entry]) => isTechnical(key) || isBlank(entry) || isEmpty(entry),
    );
  return isBlank(value);
}

// An object that only names something, such as {id, name, slug}.
export function isNamedReference(value: Json | undefined): boolean {
  return (
    !!value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    typeof value.name === "string" &&
    Object.keys(value).every(
      (key) => key === "name" || key === "kind" || isTechnical(key),
    )
  );
}

// Primary content first; any field not listed follows in its stored order.
const SECTION_ORDER: Record<string, string[]> = {
  pokemon: [
    "abilities",
    "evolutions",
    "level_up_moves",
    "machines",
    "egg_moves",
    "tutor_moves",
    "held_items",
    "egg_groups",
    "ev_yields",
    "battle_forms",
    "static_encounters",
  ],
  moves: ["machines", "tutors", "egg_move_pokemon"],
  items: [
    "shops",
    "locations",
    "gifts",
    "trades",
    "wild_held_by",
    "trainer_held_by",
    "trainer_rewards",
    "evolutions",
  ],
  trainers: ["party", "locations", "ai_battle_items", "base_prize_money"],
  encounters: [
    "walking",
    "walking_variants",
    "grass_cave",
    "doubles_grass",
    "shaking_spots",
    "surf",
    "surfing",
    "surfing_spots",
    "old_rod",
    "good_rod",
    "super_rod",
    "fishing",
    "fishing_spots",
    "rock_smash",
    "special",
    "pools",
    "visible_items",
    "hidden_items",
    "locations",
  ],
  locations: [
    "connections",
    "warps",
    "trainers",
    "items",
    "shops",
    "pokemon_gifts",
    "static_encounters",
    "npc_trades",
  ],
};

export function orderEntries<T>(
  section: string,
  entries: [string, T][],
): [string, T][] {
  const order = SECTION_ORDER[section] ?? [];
  const rank = (key: string) =>
    order.includes(key) ? order.indexOf(key) : order.length;
  return entries
    .map((entry, index) => ({ entry, index }))
    .sort((a, b) => rank(a.entry[0]) - rank(b.entry[0]) || a.index - b.index)
    .map(({ entry }) => entry);
}

const GENDER_RATIOS: Record<number, string> = {
  0: "Male only",
  31: "87.5% male",
  63: "75% male",
  127: "50% male",
  191: "25% male",
  225: "12.5% male",
  254: "Female only",
  255: "Genderless",
};
const BATTLE_MODES = ["Single", "Double", "Triple", "Rotation"];

// Stored scalars shown in the units and words players use.
export function formatScalar(
  field: string,
  value: string | number | boolean,
): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    if (field === "gender_ratio") return GENDER_RATIOS[value] ?? String(value);
    if (field === "height_dm") return `${value / 10} m`;
    if (field === "weight_hg") return `${value / 10} kg`;
    if (field === "battle_mode") return BATTLE_MODES[value] ?? String(value);
    return value.toLocaleString();
  }
  return /^[a-z]+(?:[-_][a-z]+)*$/.test(value) ? title(value) : value;
}

// Names stored as slugs ("stealth-rock") read as proper names.
export function formatName(value: string): string {
  return /^[a-z]+(?:[-_][a-z]+)*$/.test(value)
    ? value
        .split(/[-_]/)
        .map((word) => word[0].toUpperCase() + word.slice(1))
        .join(" ")
    : value;
}
