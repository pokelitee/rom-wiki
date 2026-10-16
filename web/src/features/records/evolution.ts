import type { DataObject } from "../../data/types";
import { object } from "../../lib/json";
import { title } from "../../lib/utils";
import { formatName } from "./fields";

// A condition reads as text with an optional linked item, move, or Pokémon.
export type ConditionPart = string | { name: string; route?: string };

function reference(value: DataObject): ConditionPart {
  const name = formatName(String(value.name ?? ""));
  const section =
    value.kind === "item"
      ? "items"
      : value.kind === "pokemon"
        ? "pokemon"
        : undefined;
  return section && typeof value.slug === "string"
    ? { name, route: `${section}/${value.slug}` }
    : { name };
}

export function evolutionCondition(evolution: DataObject): ConditionPart[] {
  const method = String(
    object(evolution.method).name ?? evolution.method ?? "",
  );
  const data = object(evolution.parameter_data);
  const value = data.value ?? evolution.parameter;
  const level = `Level ${String(value)}`;
  const ref = reference(data);
  const conditions: Record<string, ConditionPart[]> = {
    level: [level],
    "level-ninjask": [level],
    "level-attack-greater": [`${level}, Attack higher than Defense`],
    "level-attack-equal": [`${level}, Attack equal to Defense`],
    "level-defense-greater": [`${level}, Defense higher than Attack`],
    "level-female": [`${level}, female`],
    "level-male": [`${level}, male`],
    "level-personality-high": [`${level}, depending on personality value`],
    "level-personality-low": [`${level}, depending on personality value`],
    "level-shedinja": [`${level}, with a free party slot and a Poké Ball`],
    "level-held-item-day": ["Level up holding ", ref, " during the day"],
    "level-held-item-night": ["Level up holding ", ref, " at night"],
    "level-knowing-move": ["Level up knowing ", ref],
    "level-with-party-species": ["Level up with ", ref, " in the party"],
    "level-ice-rock": ["Level up near the Ice Rock"],
    "level-moss-rock": ["Level up near the Moss Rock"],
    "level-magnetic-field": ["Level up in a magnetic field"],
    friendship: ["Level up with high friendship"],
    "friendship-day": ["Level up with high friendship during the day"],
    "friendship-night": ["Level up with high friendship at night"],
    beauty: [`Level up with ${String(value)} or more Beauty`],
    trade: ["Trade"],
    "trade-held-item": ["Trade holding ", ref],
    "trade-special": ["Trade for a specific Pokémon"],
    "use-item": ["Use ", ref],
    "use-item-female": ["Use ", ref, " on a female"],
    "use-item-male": ["Use ", ref, " on a male"],
  };
  return conditions[method] ?? [title(method)];
}
