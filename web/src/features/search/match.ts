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
  const term = query.trim().toLocaleLowerCase();
  return entries.filter((entry) =>
    (entry.search ?? entry.label.toLocaleLowerCase()).includes(term),
  );
}
