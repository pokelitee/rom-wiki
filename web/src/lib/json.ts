import type { DataObject, Json } from "../data/types";

export function object(value: Json | undefined): DataObject {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}
