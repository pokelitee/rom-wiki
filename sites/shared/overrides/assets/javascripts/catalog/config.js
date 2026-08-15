import { title } from "../formatting.js";
import {
  accessMethods,
  classBadge,
  numberOrDash,
  pokemonAvailability,
  pokemonName,
  referenceList,
  referencePreviewList,
  recordLink,
  routeId,
  text,
  trainerPartySummary,
  typeBadge,
  typeList,
} from "./renderers.js";

export const CATALOGS = {
  items: {
    searchPlaceholder: "Search items, locations, or uses",
    filters: [{ key: "pocket", label: "Pocket" }, { key: "category", label: "Category" }, { key: "features", label: "Usage", multi: true }, { key: "locations", label: "Location", control: "combobox" }],
    ranges: [{ key: "price", label: "Base price" }],
    sorts: [["label", "Name"], ["pocket", "Pocket"], ["price", "Base price"]],
    columns: [["Item", recordLink], ["Pocket", (record) => text(title(record.pocket))], ["Base price", (record) => text(record.price ? `₽${record.price.toLocaleString()}` : "Not sold", "rw-catalog__number")], ["Locations", (record) => referencePreviewList(record.location_refs)]],
  },
  abilities: {
    searchPlaceholder: "Search abilities or Pokémon",
    filters: [{ key: "pokemon", label: "Pokémon", control: "combobox" }, { key: "status", label: "Assignment" }],
    sorts: [["label", "Name"]],
    columns: [["Ability", recordLink], ["Pokémon", (record) => referencePreviewList(record.pokemon_refs)]],
  },
  pokemon: {
    searchPlaceholder: "Search Pokémon, types, or abilities",
    filters: [{ key: "types", label: "Type", multi: true }, { key: "abilities", label: "Ability", control: "combobox" }, { key: "egg_groups", label: "Egg group", multi: true }, { key: "availability_methods", label: "Availability", multi: true }],
    ranges: [{ key: "bst", label: "BST" }],
    sorts: [["dex", "Pokédex number"], ["label", "Name"], ["bst", "Base stat total"]],
    columns: [["Pokémon", pokemonName], ["Type", typeList], ["Abilities", (record) => referenceList(record.ability_refs)], ["Availability", pokemonAvailability], ["BST", (record) => text(record.bst, "rw-catalog__number")]],
  },
  moves: {
    searchPlaceholder: "Search moves or machine numbers",
    filters: [{ key: "type", label: "Type" }, { key: "damage_class", label: "Class" }, { key: "access_methods", label: "Available as", multi: true }],
    ranges: [{ key: "power", label: "Power" }],
    sorts: [["label", "Name"], ["power", "Power"], ["accuracy", "Accuracy"], ["pp", "PP"]],
    columns: [["Move", recordLink], ["Type", (record) => typeBadge(record.type)], ["Class", (record) => classBadge(record.damage_class)], ["Power", (record) => numberOrDash(record.power)], ["Accuracy", (record) => text(record.accuracy ? `${record.accuracy}%` : "Always hits")], ["PP", (record) => text(record.pp, "rw-catalog__number")], ["Available as", accessMethods]],
  },
  trainers: {
    searchPlaceholder: "Search trainers, locations, or party Pokémon",
    filters: [{ key: "class_name", label: "Class", control: "combobox" }, { key: "locations", label: "Location", control: "combobox" }, { key: "pokemon", label: "Party Pokémon", control: "combobox" }, { key: "battle_format", label: "Battle format" }],
    ranges: [{ key: "level", label: "Party level", mode: "overlap", minKey: "min_level", maxKey: "max_level" }],
    sorts: [["label", "Name"], ["route_id", "ID"], ["min_level", "Minimum level"], ["max_level", "Maximum level"], ["party_size", "Party size"]],
    columns: [["Trainer", recordLink], ["ID", routeId], ["Location", (record) => record.location_refs?.length ? referenceList(record.location_refs) : text("Unlinked")], ["Party", trainerPartySummary], ["Format", (record) => text(title(record.battle_format))]],
  },
  locations: {
    searchPlaceholder: "Search location or internal map name",
    filters: [{ key: "features", label: "Contains", multi: true }],
    sorts: [["label", "Name"], ["section_name", "Section"], ["route_id", "Map ID"]],
    columns: [["Location", recordLink], ["Section", (record) => text(record.section_name || "—", "rw-catalog__id")], ["Map ID", routeId], ["Contains", (record) => text(record.features.map(title).join(", ") || "—")]],
  },
  encounters: {
    searchPlaceholder: "Search areas or wild Pokémon",
    filters: [{ key: "methods", label: "Method", multi: true }, { key: "pokemon", label: "Pokémon", control: "combobox" }],
    ranges: [{ key: "level", label: "Level", mode: "overlap", minKey: "min_level", maxKey: "max_level" }],
    correlations: [{ left: "methods", right: "pokemon", path: "method_pokemon" }],
    sorts: [["label", "Area"], ["route_id", "ID"], ["min_level", "Minimum level"], ["max_level", "Maximum level"]],
    columns: [["Area", recordLink], ["ID", routeId], ["Methods", (record) => text(record.methods.map(title).join(", ") || "—")], ["Levels", (record) => text(record.min_level == null ? "—" : record.min_level === record.max_level ? record.min_level : `${record.min_level}–${record.max_level}`, "rw-catalog__number")], ["Pokémon", (record) => referencePreviewList(record.pokemon_refs)]],
  },
};

for (const config of Object.values(CATALOGS)) {
  config.filters.unshift({ key: "change_status", label: "Change status" });
}
