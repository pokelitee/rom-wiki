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
