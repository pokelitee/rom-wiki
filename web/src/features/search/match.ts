import { searchText } from "../../lib/utils";

export interface SearchEntry {
  label: string;
  path: string;
  section: string;
  search?: string;
}

export function matchSearch(
  entries: SearchEntry[],
  query: string,
): SearchEntry[] {
  const term = searchText(query.trim());
  return entries.filter((entry) =>
    (entry.search ?? searchText(entry.label)).includes(term),
  );
}
