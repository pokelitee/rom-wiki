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

export function routeId(record) {
  return text(record.route_id || "—", "rw-catalog__id");
}

function referenceLink(reference) {
  if (!reference?.url) return text(reference?.label || "—");
  const link = document.createElement("a");
  link.href = reference.url;
  link.textContent = reference.label;
  if (!reference.hidden) return link;
  const fragment = document.createDocumentFragment();
  fragment.append(link, hiddenAbilityMarker());
  return fragment;
}

// Mirrors `HIDDEN_ABILITY_MARKER` in renderers/mkdocs/components.py, so a
// Pokémon's hidden ability (`reference.hidden`, set from the ROM's own
// ability-slot position) is marked the same way whether the page is
// server-rendered or built client-side from catalog.json.
function hiddenAbilityMarker() {
  const marker = document.createElement("abbr");
  marker.className = "rw-hidden-ability";
  marker.title = "Hidden Ability";
  marker.textContent = "*";
  return marker;
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

export function classBadge(value) {
  return text(title(value), `rw-class rw-class--${value}`);
}

export function numberOrDash(value) {
  return text(value || "—", "rw-catalog__number");
}

export function accessMethods(record) {
  return text(
    record.access_methods.map((value) => displayFilter("access_methods", value)).join(", ") || "—"
  );
}

export function pokemonAvailability(record) {
  const methods = record.availability_methods.map((method) => {
    const label = displayFilter("availability_methods", method);
    if (method !== "wild" || !record.wild_location_count) return label;
    const count = record.wild_location_count.toLocaleString();
    const locations = record.wild_location_count === 1 ? "location" : "locations";
    return `${label} (${count} ${locations})`;
  });
  return text(methods.join(" · "));
}

export function levelRange(record) {
  return text(
    record.min_level == null
      ? "—"
      : record.min_level === record.max_level
        ? record.min_level
        : `${record.min_level}–${record.max_level}`,
    "rw-catalog__number",
  );
}
