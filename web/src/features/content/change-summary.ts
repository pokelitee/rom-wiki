import type { DataObject, Json } from "../../data/types";
import { object } from "../../lib/json";
import { title } from "../../lib/utils";

export const CHANGE_STATUSES = ["added", "changed", "removed"];

function scalar(value: Json | undefined): string | undefined {
  if (value === null || value === undefined) return "none";
  if (typeof value === "object") {
    const name = object(value).name;
    return Array.isArray(value) || typeof name !== "string" ? undefined : name;
  }
  return String(value);
}

// One line naming each changed field, with before and after values when
// both are simple enough to read inline.
export function changeSummary(record: DataObject): string {
  const changes = Array.isArray(record.changes)
    ? record.changes.map(object)
    : [];
  return changes
    .map((change) => {
      const label = String(change.label ?? title(String(change.field ?? "")));
      const before = scalar(change.before);
      const after = scalar(change.after);
      return before !== undefined && after !== undefined
        ? `${label} ${before} → ${after}`
        : label;
    })
    .join(" · ");
}
