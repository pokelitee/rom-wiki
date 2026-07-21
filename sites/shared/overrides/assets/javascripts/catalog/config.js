import { title } from "../formatting.js";
import {
  accessMethods,
  changeStatus,
  locationIdentifier,
  numberOrDash,
  pokemonName,
  referenceList,
  referencePreviewList,
  recordLink,
  stat,
  text,
  trainerParty,
  typeBadge,
  typeList,
} from "./renderers.js";

export const CATALOGS = {
  items: {
    searchPlaceholder: "Search items, locations, or uses",
    filters: [{ key: "pocket", label: "Pocket" }, { key: "field_use", label: "Field use" }, { key: "features", label: "Referenced by", multi: true }, { key: "locations", label: "Location", control: "combobox" }],
    ranges: [{ key: "price", label: "Price" }, { key: "fling_power", label: "Fling power" }],
    sorts: [["id", "Item ID"], ["label", "Name"], ["price", "Price"], ["fling_power", "Fling power"]],
    columns: [["Item", recordLink], ["Pocket", (record) => text(title(record.pocket))], ["Price", (record) => text(record.price ? `₽${record.price.toLocaleString()}` : "Not sold", "rw-catalog__number")], ["Fling", (record) => numberOrDash(record.fling_power)], ["Referenced by", (record) => text(record.features.map(title).join(", ") || "—")], ["Locations", (record) => referencePreviewList(record.location_refs)]],
  },
  abilities: {
    searchPlaceholder: "Search abilities or Pokémon",
    filters: [{ key: "pokemon", label: "Pokémon", control: "combobox" }, { key: "status", label: "Assignment" }],
    sorts: [["id", "Ability ID"], ["label", "Name"], ["pokemon_count", "Pokémon count"]],
    columns: [["Ability", recordLink], ["ID", (record) => text(record.id, "rw-catalog__number")], ["Pokémon", (record) => referencePreviewList(record.pokemon_refs)], ["Count", (record) => text(record.pokemon_count, "rw-catalog__number")]],
  },
  pokemon: {
    searchPlaceholder: "Search Pokémon, types, or abilities",
    filters: [{ key: "types", label: "Type", multi: true }, { key: "abilities", label: "Ability", control: "combobox" }, { key: "egg_groups", label: "Egg group", multi: true }],
    ranges: [{ key: "bst", label: "BST" }],
    sorts: [["dex", "Pokédex number"], ["label", "Name"], ["bst", "Base stat total"], ["stats.hp", "HP"], ["stats.attack", "Attack"], ["stats.defense", "Defense"], ["stats.special_attack", "Sp. Atk"], ["stats.special_defense", "Sp. Def"], ["stats.speed", "Speed"]],
    columns: [["Pokémon", pokemonName], ["Type", typeList], ["Abilities", (record) => referenceList(record.ability_refs)], ["HP", (record) => stat(record, "hp")], ["Atk", (record) => stat(record, "attack")], ["Def", (record) => stat(record, "defense")], ["SpA", (record) => stat(record, "special_attack")], ["SpD", (record) => stat(record, "special_defense")], ["Spe", (record) => stat(record, "speed")], ["BST", (record) => text(record.bst, "rw-catalog__number")]],
  },
  moves: {
    searchPlaceholder: "Search moves or machine numbers",
    filters: [{ key: "type", label: "Type" }, { key: "damage_class", label: "Class" }, { key: "access_methods", label: "Available as", multi: true }],
    ranges: [{ key: "power", label: "Power" }],
    sorts: [["label", "Name"], ["id", "Move ID"], ["power", "Power"], ["accuracy", "Accuracy"], ["pp", "PP"]],
    columns: [["Move", recordLink], ["Type", (record) => typeBadge(record.type)], ["Class", (record) => text(title(record.damage_class))], ["Power", (record) => numberOrDash(record.power)], ["Accuracy", (record) => text(record.accuracy ? `${record.accuracy}%` : "Always")], ["PP", (record) => text(record.pp, "rw-catalog__number")], ["Available as", accessMethods]],
  },
  trainers: {
    searchPlaceholder: "Search trainers, locations, or party Pokémon",
    filters: [{ key: "class_name", label: "Class", control: "combobox" }, { key: "locations", label: "Location", control: "combobox" }, { key: "pokemon", label: "Party Pokémon", control: "combobox" }, { key: "double_battle", label: "Battle format" }, { key: "linked", label: "Location status" }],
    ranges: [{ key: "level", label: "Party level", mode: "overlap", minKey: "min_level", maxKey: "max_level" }],
    sorts: [["label", "Name"], ["id", "Trainer ID"], ["min_level", "Minimum level"], ["max_level", "Maximum level"], ["party_size", "Party size"]],
    columns: [["Trainer", recordLink], ["Location", (record) => record.location_refs?.length ? referenceList(record.location_refs) : text("Unlinked")], ["Party", trainerParty], ["Format", (record) => text(record.double_battle ? "Double" : "Single")]],
  },
  locations: {
    searchPlaceholder: "Search location or internal map name",
    filters: [{ key: "features", label: "Contains", multi: true }],
    sorts: [["label", "Name"], ["id", "Header ID"]],
    columns: [["Location", recordLink], ["Contains", (record) => text(record.features.map(title).join(", ") || "—")], ["Map ID", locationIdentifier]],
  },
  encounters: {
    searchPlaceholder: "Search areas or wild Pokémon",
    filters: [{ key: "methods", label: "Method", multi: true }, { key: "pokemon", label: "Pokémon", control: "combobox" }],
    ranges: [{ key: "level", label: "Level", mode: "overlap", minKey: "min_level", maxKey: "max_level" }],
    correlations: [{ left: "methods", right: "pokemon", path: "method_pokemon" }],
    sorts: [["label", "Location"], ["id", "Area ID"], ["min_level", "Minimum level"], ["max_level", "Maximum level"]],
    columns: [["Area", recordLink], ["Methods", (record) => text(record.methods.map(title).join(", "))], ["Levels", (record) => text(record.min_level == null ? "—" : `${record.min_level}–${record.max_level}`, "rw-catalog__number")], ["Pokémon", (record) => referencePreviewList(record.pokemon_refs)]],
  },
};

for (const config of Object.values(CATALOGS)) {
  config.filters.unshift({ key: "change_status", label: "Change status" });
  config.columns.splice(1, 0, ["Changes", changeStatus]);
}
