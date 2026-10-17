import type { DataObject } from "../../data/types";

export function entityRoute(
  value: DataObject,
  field: string,
): string | undefined {
  if (
    typeof value.encounter_route_key === "string" ||
    typeof value.encounter_route_key === "number"
  )
    return `encounters/${typeof value.encounter_route_key === "number" ? `area-${String(value.encounter_route_key).padStart(3, "0")}` : value.encounter_route_key}`;
  if (typeof value.trainer_id === "number")
    return `trainers/trainer-${String(value.trainer_id).padStart(4, "0")}`;
  if (typeof value.destination_header_id === "number")
    return `locations/header-${String(value.destination_header_id).padStart(3, "0")}`;
  if (typeof value.header_id === "number")
    return `locations/header-${String(value.header_id).padStart(3, "0")}`;
  if (typeof value.pokemon_slug === "string")
    return `pokemon/${value.pokemon_slug}`;
  if (typeof value.item_slug === "string") return `items/${value.item_slug}`;
  if (typeof value.slug !== "string") return undefined;
  // Species carry their Pokédex number, whatever list holds them, such as a
  // move's egg-move Pokémon or an item's wild holders.
  if (typeof value.national_dex_id === "number") return `pokemon/${value.slug}`;
  // An evolution's parameter is an item or a species, and says which.
  if (field === "parameter_data" && value.kind === "item")
    return `items/${value.slug}`;
  if (field === "parameter_data" && value.kind === "pokemon")
    return `pokemon/${value.slug}`;
  if (field.includes("abilit")) return `abilities/${value.slug}`;
  // "replaces" names the standard move a ROM slot stands in for, which has
  // no page of its own.
  if (field === "replaces") return undefined;
  if (field.includes("move")) return `moves/${value.slug}`;
  if (
    field.includes("item") ||
    field.includes("held") ||
    field === "victory_item"
  )
    return `items/${value.slug}`;
  if (
    field.includes("pokemon") ||
    field.includes("species") ||
    field.includes("evolution") ||
    field === "base_species" ||
    // Evolution endpoints, revived fossils, and the Poké Radar and radio
    // encounter lists are always species.
    [
      "source",
      "target",
      "revives_into",
      "radar",
      "hoenn_radio",
      "sinnoh_radio",
    ].includes(field)
  )
    return `pokemon/${value.slug}`;
  return undefined;
}

// A "<thing>_name" column links when its row also carries that thing's slug
// or map header, such as a trainer's held_item_name beside held_item_slug.
export function columnRoute(
  row: DataObject,
  column: string,
): string | undefined {
  const prefix = column.match(/^(.+)_name$/)?.[1];
  if (!prefix) return undefined;
  if (prefix === "location" && typeof row.location_id === "number")
    return `locations/header-${String(row.location_id).padStart(3, "0")}`;
  const slug = row[`${prefix}_slug`];
  if (typeof slug !== "string") return undefined;
  if (prefix.includes("item")) return `items/${slug}`;
  if (prefix.includes("pokemon") || prefix.includes("species"))
    return `pokemon/${slug}`;
  if (prefix.includes("abilit")) return `abilities/${slug}`;
  if (prefix.includes("move")) return `moves/${slug}`;
  return undefined;
}
