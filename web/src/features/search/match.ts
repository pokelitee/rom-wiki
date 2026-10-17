import { searchText } from "../../lib/utils";

export interface SearchEntry {
  label: string;
  path: string;
  section: string;
  search?: string;
  sprite?: string;
  // Tells the entry apart from others in its section with the same label.
  context?: string;
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
