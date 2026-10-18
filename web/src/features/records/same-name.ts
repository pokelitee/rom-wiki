import type { IndexRecord } from "../../data/types";
import { title } from "../../lib/utils";

// Gen 4 map codes end in a building code when the map is indoors, such as
// C01PC0101 for Jubilife City's Pokémon Center. Gen 5 publishes no codes.
const MAP_KINDS: [RegExp, string][] = [
  [/PC\d{4}$/, "Pokémon Center"],
  [/FS\d{4}$/, "Poké Mart"],
  [/GYM\d{4}$/, "Gym"],
  [/[A-Z]\d+R\d{4}$/, "Building"],
];

// "Pokémon Center · Map 6": what kind of map a header is, when its code
// says, and its number.
export function mapContext(code: unknown, header: number): string {
  const kind =
    typeof code === "string"
      ? MAP_KINDS.find(([pattern]) => pattern.test(code))?.[1]
      : undefined;
  return [kind, `Map ${header}`].filter(Boolean).join(" · ");
}

function levels(fields: IndexRecord["fields"]): string | undefined {
  const min = fields.min_level;
  const max = fields.max_level;
  if (typeof min !== "number" || typeof max !== "number") return undefined;
  return min === max ? `Lv. ${min}` : `Lv. ${min}–${max}`;
}

function list(value: IndexRecord["fields"][string], limit: number): string {
  const entries = Array.isArray(value) ? value : [];
  return entries.length > limit
    ? `${entries.slice(0, limit).join(", ")} +${entries.length - limit}`
    : entries.join(", ");
}

function number(id: string): string {
  return `#${Number(id.replace(/^\D+/, ""))}`;
}

// A short line telling a record apart from others with the same name,
// leaving out what the catalog's columns already show.
export function recordContext(
  section: string,
  row: IndexRecord,
  columns: string[] = [],
): string {
  const { fields } = row;
  const range = columns.includes("levels") ? undefined : levels(fields);
  const parts =
    section === "trainers"
      ? [range, list(fields.pokemon, 3)]
      : section === "encounters"
        ? columns.includes("methods")
          ? [range, list(fields.pokemon, 3)]
          : [
              range,
              list(
                (Array.isArray(fields.methods) ? fields.methods : []).map(
                  title,
                ),
                3,
              ),
            ]
        : undefined;
  if (parts) return [...parts, number(row.id)].filter(Boolean).join(" · ");
  if (section === "locations")
    return mapContext(fields.section_name, Number(number(row.id).slice(1)));
  return /^\D+-?\d+$/.test(row.id) ? number(row.id) : row.id;
}

// Labels shared by more than one record in a section.
export function sharedLabels(records: IndexRecord[]): Set<string> {
  const counts = new Map<string, number>();
  for (const record of records)
    counts.set(record.label, (counts.get(record.label) ?? 0) + 1);
  return new Set(
    [...counts].filter(([, count]) => count > 1).map(([label]) => label),
  );
}
