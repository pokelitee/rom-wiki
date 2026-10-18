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
  /(?:^id$|_id$|_ids$|_flags$|^flags$|_offset$|_provenance$|^provenance$|^unknown_|^data_archive|^trailing_|^sprite|^portrait|^cry$|^public$|^slug$|_slug$|^member$|^flip_sprite$|^source$|^source_fields$|^moves_source$|^table_index$|^battle_type$|^has_custom_moves$|^has_held_items$|^party_count$|internal_name$|^section_name$|^command$|_mask$|^hold_effect_parameter$|^section_name_source$|^bonus_slot_methodology_source$|^encounter_map_index$|^map_index$|^rom_sha256$|^archive$|^trainer_type$|^object_index$|^[xyz]$|^version$|^flavor_text_version$|^pokemon_form$|^linked$|^party_position$|^event_index$|^hidden_flag$|^format$|^active$)/;

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
  // A slot with nothing in it: an encounter slot without a Pokémon, or an
  // unnamed reference such as a Pokémon's "common" held item when it holds
  // none.
  if (
    value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    (value.pokemon === null || (value.name === null && value.slug === null))
  )
    return true;
  if (Array.isArray(value))
    return value.every((entry) => isBlank(entry) || isEmpty(entry));
  if (value && typeof value === "object")
    return Object.entries(value).every(
      ([key, entry]) => isTechnical(key) || isBlank(entry) || isEmpty(entry),
    );
  return isBlank(value);
}

// An encounter method whose rate is zero or whose slots hold no Pokémon,
// such as the fishing tables every map header carries.
export function hasNoEncounters(value: Json | undefined): boolean {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const slots = value.slots;
  if (!Array.isArray(slots)) return false;
  return (
    value.rate === 0 ||
    slots.every(
      (slot) =>
        slot === null ||
        typeof slot !== "object" ||
        Array.isArray(slot) ||
        !slot.pokemon,
    )
  );
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

// Field and version names whose words title-case wrongly, such as games in
// dual-slot encounter tables or HeartGold's version identifier.
const FIELD_LABELS: Record<string, string> = {
  fire_red: "FireRed",
  leaf_green: "LeafGreen",
  heart_gold: "HeartGold",
  soul_silver: "SoulSilver",
  radar: "Poké Radar",
};

export function fieldLabel(key: string): string {
  return FIELD_LABELS[key.replaceAll("-", "_")] ?? title(key);
}

const LONG_TABLE_ROWS = 15;

// Tables longer than this scroll inside their card.
export function tableScroll(rows: number): string {
  return rows > LONG_TABLE_ROWS ? "table-scroll is-long" : "table-scroll";
}

// Repeated references, such as a trainer's two Potions, collapse into one
// entry with a count, in order of first appearance.
export function countRepeats(
  entries: Json[],
): { value: Json; count: number }[] {
  const counted = new Map<string, { value: Json; count: number }>();
  for (const entry of entries) {
    const key = JSON.stringify(entry);
    const existing = counted.get(key);
    if (existing) existing.count += 1;
    else counted.set(key, { value: entry, count: 1 });
  }
  return [...counted.values()];
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
  if (field === "versions" && typeof value === "string")
    return fieldLabel(value);
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

// A record available in every version of its game; saying so adds nothing.
export function coversAllVersions(
  value: Json | undefined,
  versions: string[],
): boolean {
  return (
    Array.isArray(value) &&
    versions.length > 0 &&
    versions.every((version) => value.includes(version))
  );
}

// Acquisition details that are script commands, such as PokePartyAddEx,
// name how the game runs an event rather than anything a player sees. Only
// the detail field is checked: Gen 4 item names like BlackGlasses look alike.
export function isScriptCommand(
  field: string,
  value: Json | undefined,
): boolean {
  return (
    field === "detail" &&
    typeof value === "string" &&
    /^[A-Z][a-z]+(?:[A-Z][a-z]*)+$/.test(value)
  );
}
