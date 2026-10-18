import type { DataObject, Json } from "../../data/types";
import { object } from "../../lib/json";
import { fieldLabel, isNamedReference, isTechnical } from "./fields";

export interface SlotSummary {
  pokemon: DataObject;
  minimumLevel: number | null;
  maximumLevel: number | null;
  chance: number | null;
}

// Rows shaped like encounter slots: a Pokémon with a chance or a level.
export function isSlotList(rows: DataObject[]): boolean {
  return (
    rows.length > 0 &&
    rows.every(
      (row) =>
        "pokemon" in row &&
        ("chance" in row || "level" in row || "minimum_level" in row),
    )
  );
}

// One row per Pokémon, as wikis list them: summed chance and level range.
// Slots without a Pokémon are unused and left out.
export function summarizeSlots(rows: DataObject[]): SlotSummary[] {
  const summaries = new Map<string, SlotSummary>();
  for (const row of rows) {
    const pokemon = object(row.pokemon);
    if (typeof pokemon.name !== "string") continue;
    const key = String(pokemon.slug ?? pokemon.name);
    // Some tables, like the Poké Radar's, list Pokémon without levels.
    const level = (value: Json | undefined) =>
      typeof value === "number" ? value : null;
    const low = level(row.minimum_level ?? row.level);
    const high = level(row.maximum_level ?? row.level);
    const chance = typeof row.chance === "number" ? row.chance : null;
    const summary = summaries.get(key);
    if (!summary) {
      summaries.set(key, {
        pokemon,
        minimumLevel: low,
        maximumLevel: high,
        chance,
      });
      continue;
    }
    summary.minimumLevel =
      summary.minimumLevel === null || low === null
        ? (summary.minimumLevel ?? low)
        : Math.min(summary.minimumLevel, low);
    summary.maximumLevel =
      summary.maximumLevel === null || high === null
        ? (summary.maximumLevel ?? high)
        : Math.max(summary.maximumLevel, high);
    summary.chance =
      summary.chance === null || chance === null
        ? null
        : summary.chance + chance;
  }
  return [...summaries.values()].sort(
    (a, b) => (b.chance ?? 0) - (a.chance ?? 0),
  );
}

export interface SlotGroup {
  // When the group applies, such as ["Dual slot", "Ruby, Sapphire"].
  labels: string[];
  slots: SlotSummary[];
}

function rowsOf(value: Json[]): DataObject[] | null {
  const entries = value.filter((entry) => entry !== null);
  const rows = entries.map(object);
  if (!rows.length || isSlotList(rows)) return rows;
  // A list of Pokémon alone, such as the Poké Radar's.
  if (entries.every(isNamedReference))
    return rows.map((pokemon) => ({ pokemon }));
  return null;
}

// Encounter tables nested under conditions, such as the time of day or the
// game in the dual slot, flattened into labelled groups for one table.
// Conditions with the same Pokémon share a group. Returns null when the
// value holds anything other than encounter tables.
export function slotGroups(
  value: Json,
  labels: string[] = [],
): SlotGroup[] | null {
  if (value === null) return [];
  if (Array.isArray(value)) {
    const rows = rowsOf(value);
    if (!rows) return null;
    const slots = summarizeSlots(rows);
    return slots.length ? [{ labels, slots }] : [];
  }
  if (typeof value !== "object") return null;
  if (isNamedReference(value)) return slotGroups([value], labels);
  if (Array.isArray(value.slots)) return slotGroups(value.slots, labels);
  const groups: SlotGroup[] = [];
  for (const [key, child] of Object.entries(value)) {
    if (isTechnical(key)) continue;
    const nested = slotGroups(child, [...labels, fieldLabel(key)]);
    if (!nested) return null;
    for (const group of nested) {
      const same = groups.find(
        (other) =>
          other.labels.length === labels.length + 1 &&
          group.labels.length === labels.length + 1 &&
          JSON.stringify(other.slots) === JSON.stringify(group.slots),
      );
      if (same)
        same.labels[labels.length] += `, ${group.labels[labels.length]}`;
      else groups.push({ ...group, labels: [...group.labels] });
    }
  }
  return groups;
}

function hasSlotList(value: Json): boolean {
  if (Array.isArray(value))
    return (
      isSlotList(value.filter((entry) => entry !== null).map(object)) ||
      value.some(hasSlotList)
    );
  return (
    value !== null &&
    typeof value === "object" &&
    Object.values(value).some(hasSlotList)
  );
}

// Slot groups for a value that holds at least one real encounter table, so
// other lists of Pokémon are not mistaken for encounters.
export function encounterGroups(value: Json): SlotGroup[] | null {
  return hasSlotList(value) ? slotGroups(value) : null;
}
