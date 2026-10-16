import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function title(value: string) {
  const labels: Record<string, string> = {
    pokemon: "Pokémon",
    national_dex_id: "Pokédex number",
    bst: "Base stat total",
    hp: "HP",
    pp: "PP",
    ev_yields: "EV yields",
  };
  if (value in labels) return labels[value];
  return value
    .replaceAll(/[_-]/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

// Matches the exporter's `_search_text`: locale-independent Unicode default
// lowercasing, so queries behave the same for every viewer's language.
export function searchText(value: string) {
  return value.toLowerCase();
}
