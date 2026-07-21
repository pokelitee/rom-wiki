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

export function changeStatus(record) {
  const status = record.change_status;
  if (!status) return text("—");
  return text(title(status), `rw-change-status rw-change-status--${status}`);
}

export function referenceLink(reference) {
  if (!reference?.url) return text(reference?.label || "—");
  const link = document.createElement("a");
  link.href = reference.url;
  link.textContent = reference.label;
  return link;
}

export function referenceList(references, className = "rw-catalog__list") {
  const wrap = document.createElement("span");
  wrap.className = className;
  if (!references?.length) {
    wrap.textContent = "—";
    return wrap;
  }
  references.forEach((reference, index) => {
    if (index) wrap.append(", ");
    wrap.append(referenceLink(reference));
  });
  return wrap;
}

export function referencePreviewList(references) {
  const visible = (references || []).slice(0, 6);
  const wrap = referenceList(visible);
  const remaining = (references || []).length - visible.length;
  if (remaining > 0) wrap.append(` +${remaining} more`);
  return wrap;
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
  const wrap = document.createElement("span");
  wrap.className = "rw-catalog__list";
  record.party.forEach((member, index) => {
    if (index) wrap.append(", ");
    wrap.append(
      member.pokemon_ref ? referenceLink(member.pokemon_ref) : member.name,
      ` Lv. ${member.level}`,
    );
  });
  return wrap;
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
