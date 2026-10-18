import type { DataObject } from "../../data/types";
import { title } from "../../lib/utils";
import { fieldLabel } from "./fields";

const SEASONS = ["spring", "summer", "autumn", "winter"];
const TIMES = ["morning", "day", "night"];

export interface WildEncounter {
  area: string;
  route: string | null;
  method: string;
  levels: string;
  chance: number | null;
  // Seasons, times of day, and conditions, in reading order; empty when the
  // encounter always applies.
  when: string[];
  versions: string[];
}

function listed(values: Set<string>, all: string[]): string[] {
  const present = all.filter((value) => values.has(value));
  return present.length === all.length ? [] : present.map(title);
}

// "dual-slot: leaf-green" reads as "Dual slot: LeafGreen".
function condition(value: string): string {
  return value
    .split(": ")
    .map((part, index) => (index ? fieldLabel(part) : title(part)))
    .join(": ");
}

// One row per area, method, level range, chance, and condition, with the
// seasons, times of day, and versions it applies to merged into that row.
export function compactEncounters(
  rows: DataObject[],
  versions: string[],
): WildEncounter[] {
  const groups = new Map<
    string,
    {
      row: DataObject;
      rest: string;
      seasons: Set<string>;
      times: Set<string>;
      versions: Set<string>;
    }
  >();
  for (const row of rows) {
    const parts = String(row.condition ?? "")
      .split("; ")
      .filter(Boolean);
    const time = TIMES.includes(parts[0]) ? parts.shift() : undefined;
    const rest = parts.join("; ");
    const key = JSON.stringify([
      row.encounter_route_key,
      row.area_name,
      row.method,
      row.minimum_level,
      row.maximum_level,
      row.chance,
      rest,
    ]);
    const group = groups.get(key) ?? {
      row,
      rest,
      seasons: new Set<string>(),
      times: new Set<string>(),
      versions: new Set<string>(),
    };
    groups.set(key, group);
    if (typeof row.season === "string") group.seasons.add(row.season);
    if (time) group.times.add(time);
    const rowVersions = Array.isArray(row.versions) ? row.versions : [];
    (rowVersions.length ? rowVersions.map(String) : versions).forEach(
      (version) => group.versions.add(version),
    );
  }
  return [...groups.values()].map(
    ({ row, rest, seasons, times, versions: present }) => {
      const low = Number(row.minimum_level);
      const high = Number(row.maximum_level);
      // Gen 4 areas are keyed by number, Gen 5 routes by map, as their pages are.
      const key = row.encounter_route_key;
      return {
        area: String(row.area_name ?? ""),
        route:
          typeof key === "number"
            ? `area-${String(key).padStart(3, "0")}`
            : typeof key === "string"
              ? key
              : null,
        method: String(row.method ?? ""),
        // Swarms and other overrides store no level of their own.
        levels:
          !low || !high ? "—" : low === high ? String(low) : `${low}–${high}`,
        chance: typeof row.chance === "number" ? row.chance : null,
        when: [
          ...(seasons.size ? listed(seasons, SEASONS) : []),
          ...(times.size ? listed(times, TIMES) : []),
          ...(rest ? [condition(rest)] : []),
        ],
        versions: versions.every((version) => present.has(version))
          ? []
          : versions.filter((version) => present.has(version)),
      };
    },
  );
}
