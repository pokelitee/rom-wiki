import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const LABELS: Record<string, string> = {
  national_dex_id: "Pokédex number",
  bst: "Base stat total",
  height_dm: "Height",
  weight_hg: "Weight",
};
const WORDS: Record<string, string> = {
  ai: "AI",
  ev: "EV",
  evs: "EVs",
  hm: "HM",
  hp: "HP",
  id: "ID",
  iv: "IV",
  ivs: "IVs",
  pokemon: "Pokémon",
  pp: "PP",
  rom: "ROM",
  tm: "TM",
  us: "US",
};

// Labels read in sentence case. Only all-lowercase words change, because
// proper names such as "Shed Skin" also pass through here.
export function title(value: string) {
  if (value in LABELS) return LABELS[value];
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((word, index) => {
      if (word !== word.toLowerCase()) return word;
      if (word in WORDS) return WORDS[word];
      return index === 0 ? word[0].toUpperCase() + word.slice(1) : word;
    })
    .join(" ");
}

// Matches the exporter's `_search_text`: locale-independent Unicode default
// lowercasing, so queries behave the same for every viewer's language.
export function searchText(value: string) {
  return value.toLowerCase();
}
