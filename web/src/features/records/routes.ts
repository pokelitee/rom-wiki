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
  if (typeof value.header_id === "number")
    return `locations/header-${String(value.header_id).padStart(3, "0")}`;
  if (typeof value.pokemon_slug === "string")
    return `pokemon/${value.pokemon_slug}`;
  if (typeof value.slug !== "string") return undefined;
  // An evolution's parameter is an item or a species, and says which.
  if (field === "parameter_data" && value.kind === "item")
    return `items/${value.slug}`;
  if (field === "parameter_data" && value.kind === "pokemon")
    return `pokemon/${value.slug}`;
  if (field.includes("abilit")) return `abilities/${value.slug}`;
  if (field.includes("move") || field === "replaces")
    return `moves/${value.slug}`;
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
    // Evolution endpoints and revived fossils are always species.
    ["source", "target", "revives_into"].includes(field)
  )
    return `pokemon/${value.slug}`;
  return undefined;
}
