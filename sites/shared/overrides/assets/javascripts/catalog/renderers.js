import { displayFilter, title } from "../formatting.js";

export function text(value, className) {
  const span = document.createElement("span");
  if (className) span.className = className;
  span.textContent = value;
  return span;
}

export function recordLink(record) {
  const link = document.createElement("a");
  link.href = record.url;
  link.textContent = record.label;
  return link;
}

export function pokemonName(record) {
  const wrap = document.createElement("span");
  wrap.className = "rw-catalog__name";
  const number = text(`#${String(record.dex).padStart(3, "0")}`, "rw-catalog__dex");
  wrap.append(number, recordLink(record));
  return wrap;
}

export function typeBadge(value) {
  return text(title(value), `rw-type rw-type--${value}`);
}

export function typeList(record) {
  const wrap = document.createElement("span");
  wrap.className = "rw-type-list";
  record.types.forEach((value) => wrap.append(typeBadge(value)));
  return wrap;
}

export function numberOrDash(value) {
  return text(value || "—", "rw-catalog__number");
}

export function stat(record, key) {
  return text(record.stats[key], "rw-catalog__number");
}

export function accessMethods(record) {
  return text(
    record.access_methods.map((value) => displayFilter("access_methods", value)).join(", ") || "—"
  );
}

export function trainerParty(record) {
  return text(
    record.party.map((member) => `${member.name} Lv. ${member.level}`).join(", "),
    "rw-catalog__list",
  );
}

export function locationIdentifier(record) {
  const wrap = document.createElement("span");
  wrap.className = "rw-catalog__map-id";
  wrap.append(
    text(record.internal_name, "rw-catalog__code"),
    text(`Header ${record.id}`, "rw-catalog__number"),
  );
  return wrap;
}

export function previewList(values) {
  const visible = values.slice(0, 6);
  const remaining = values.length - visible.length;
  return text(
    `${visible.join(", ")}${remaining > 0 ? ` +${remaining} more` : ""}` || "—",
    "rw-catalog__list",
  );
}
