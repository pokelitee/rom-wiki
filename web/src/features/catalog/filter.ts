import type { IndexRecord } from "../../data/types";

export const PAGE_SIZE = 50;

export function filterRecords(
  records: IndexRecord[],
  params: URLSearchParams,
): IndexRecord[] {
  const query = (params.get("q") ?? "").trim().toLocaleLowerCase();
  const filters = [...params.entries()].filter(
    ([key, value]) => value && key.startsWith("f."),
  );
  const ranges = [...params.entries()].filter(
    ([key, value]) =>
      value && (key.startsWith("min.") || key.startsWith("max.")),
  );
  const result = records.filter((record) => {
    if (query && !record.search.includes(query) && !record.id.includes(query))
      return false;
    for (const [key, value] of filters) {
      const field = record.fields[key.slice(2)];
      if (
        Array.isArray(field) ? !field.includes(value) : String(field) !== value
      )
        return false;
    }
    for (const [key, value] of ranges) {
      const field = record.fields[key.slice(4)];
      if (!Number.isFinite(Number(value))) continue;
      if (
        typeof field !== "number" ||
        (key.startsWith("min.") ? field < Number(value) : field > Number(value))
      )
        return false;
    }
    return true;
  });
  const sort = params.get("sort") ?? "name";
  const direction = params.get("dir") === "desc" ? -1 : 1;
  return result.sort((a, b) => {
    const left = a.fields[sort] ?? "";
    const right = b.fields[sort] ?? "";
    const comparison =
      typeof left === "number" && typeof right === "number"
        ? left - right
        : String(left).localeCompare(String(right), undefined, {
            numeric: true,
          });
    return direction * comparison || a.id.localeCompare(b.id);
  });
}

export function pageNumber(params: URLSearchParams, total: number): number {
  const value = Number(params.get("page") ?? 1);
  return Math.max(
    1,
    Math.min(
      Number.isFinite(value) ? Math.floor(value) : 1,
      Math.max(1, Math.ceil(total / PAGE_SIZE)),
    ),
  );
}
