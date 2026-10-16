import type { DataObject } from "../../data/types";
import { object } from "../../lib/json";

export interface SlotSummary {
  pokemon: DataObject;
  minimumLevel: number;
  maximumLevel: number;
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
    const low = Number(row.minimum_level ?? row.level);
    const high = Number(row.maximum_level ?? row.level);
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
    summary.minimumLevel = Math.min(summary.minimumLevel, low);
    summary.maximumLevel = Math.max(summary.maximumLevel, high);
    summary.chance =
      summary.chance === null || chance === null
        ? null
        : summary.chance + chance;
  }
  return [...summaries.values()].sort(
    (a, b) => (b.chance ?? 0) - (a.chance ?? 0),
  );
}
