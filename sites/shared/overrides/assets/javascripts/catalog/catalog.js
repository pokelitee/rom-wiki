import { control, enhanceCombobox, enhanceSelect, syncSelect } from "../controls.js";
import { displayFilter } from "../formatting.js";
import { CATALOGS } from "./config.js";

const PAGE_SIZE = 50;

export function initializeCatalogs() {
  document.querySelectorAll("[data-rw-catalog]").forEach(loadCatalog);
}

async function loadCatalog(root) {
  const status = root.querySelector("[data-rw-catalog-status]");
  try {
    const response = await fetch(root.dataset.rwCatalog);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const config = CATALOGS[data.kind];
    if (data.schema_version !== 1 || !config || !Array.isArray(data.records)) {
      throw new Error("Unsupported catalog format");
    }
    enhanceCatalog(root, data.records, config);
    const fallback = document.querySelector("[data-rw-catalog-fallback]");
    if (fallback) fallback.hidden = true;
  } catch (error) {
    if (status) {
      status.textContent = "Interactive catalog unavailable. The complete static list is shown below.";
    }
    root.classList.add("rw-catalog--failed");
    const fallback = document.querySelector("[data-rw-catalog-fallback]");
    if (fallback) {
      fallback.hidden = false;
      fallback.classList.add("rw-catalog-fallback--visible");
    }
  }
}

function enhanceCatalog(root, records, config) {
  const params = new URLSearchParams(window.location.search);
  const state = { visible: Math.max(1, Number(params.get("page")) || 1) * PAGE_SIZE };
  root.replaceChildren();
  const form = document.createElement("form");
  form.className = "rw-catalog__controls";
  form.setAttribute("role", "search");
  form.addEventListener("submit", (event) => event.preventDefault());

  const search = control("input", "Search", "q");
  search.input.type = "search";
  search.input.placeholder = config.searchPlaceholder || "Search records";
  search.input.value = params.get("q") || "";
  form.append(search.label);

  for (const filter of config.filters) {
    const { key, label } = filter;
    const kind = filter.control === "combobox" ? "input" : "select";
    const field = control(kind, label, key);
    if (filter.control === "combobox") {
      field.input.type = "search";
      field.input.placeholder = `Any ${label.toLowerCase()}`;
      enhanceCombobox(
        field.input,
        label,
        valuesFor(records, key).map((value) => displayFilter(key, value)),
      );
    } else {
      field.input.multiple = Boolean(filter.multi);
      field.input.dataset.placeholder = `Any ${label.toLowerCase()}`;
      if (!filter.multi) {
        field.input.append(new Option(field.input.dataset.placeholder, ""));
      }
      valuesFor(records, key).forEach((value) => {
        field.input.append(new Option(displayFilter(key, value), String(value)));
      });
    }
    if (filter.multi) {
      const selected = new Set(params.getAll(key));
      for (const option of field.input.options) {
        option.selected = selected.has(option.value);
      }
      const mode = document.createElement("input");
      mode.type = "hidden";
      mode.name = `${key}_mode`;
      mode.dataset.default = "all";
      mode.dataset.rwMatchMode = "";
      mode.defaultValue = "all";
      mode.value = params.get(mode.name) === "any" ? "any" : "all";
      field.label.append(mode);
    } else {
      field.input.value = params.get(key) || "";
    }
    form.append(field.label);
  }

  for (const range of config.ranges || []) {
    for (const bound of ["min", "max"]) {
      const name = `${range.key}_${bound}`;
      const field = control("input", `${range.label} ${bound}`, name);
      field.input.type = "number";
      field.input.min = "0";
      field.input.step = "1";
      field.input.placeholder = bound === "min" ? "Minimum" : "Maximum";
      field.input.value = params.get(name) || "";
      form.append(field.label);
    }
  }

  const sort = control("select", "Sort by", "sort");
  for (const [key, label] of config.sorts) sort.input.append(new Option(label, key));
  sort.input.dataset.default = config.sorts[0][0];
  sort.input.value = params.get("sort") || config.sorts[0][0];
  form.append(sort.label);

  const direction = control("select", "Direction", "direction");
  direction.input.append(new Option("Ascending", "asc"));
  direction.input.append(new Option("Descending", "desc"));
  direction.input.dataset.default = "asc";
  direction.input.value = params.get("direction") || "asc";
  form.append(direction.label);

  const reset = document.createElement("button");
  reset.type = "button";
  reset.className = "rw-catalog__reset";
  reset.textContent = "Reset";
  form.append(reset);

  const summary = document.createElement("p");
  summary.className = "rw-catalog__summary";
  summary.setAttribute("aria-live", "polite");
  const tableWrap = document.createElement("div");
  tableWrap.className = "rw-catalog__table-wrap";
  const table = document.createElement("table");
  table.className = "rw-catalog__table";
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  config.columns.forEach(([label]) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = label;
    headRow.append(cell);
  });
  head.append(headRow);
  const body = document.createElement("tbody");
  table.append(head, body);
  tableWrap.append(table);
  const more = document.createElement("button");
  more.type = "button";
  more.className = "rw-catalog__more";
  more.textContent = `Show ${PAGE_SIZE} more`;
  form.querySelectorAll("select").forEach((select) => {
    const label = select.closest(".rw-control")?.querySelector(".rw-control__label");
    enhanceSelect(select, label?.textContent || select.name);
  });
  root.append(form, summary, tableWrap, more);

  const render = () => {
    const values = formValues(form);
    const query = String(values.q || "").trim().toLowerCase();
    const filtered = records.filter((record) => {
      if (query && !record.search_text.includes(query)) return false;
      const matchesFilters = config.filters.every((filter) => {
        const { key } = filter;
        const selected = filter.multi ? values[key] || [] : String(values[key] || "");
        if (filter.multi ? selected.length === 0 : !selected) return true;
        const current = getValue(record, key);
        if (filter.control === "combobox") {
          const options = Array.isArray(current) ? current : [current];
          const normalized = selected.toLowerCase();
          return options.some((value) =>
            displayFilter(key, value).toLowerCase().includes(normalized)
          );
        }
        if (filter.multi) {
          const options = (Array.isArray(current) ? current : [current]).map(String);
          return matchesSelected(options, selected, values[`${key}_mode`]);
        }
        return Array.isArray(current)
          ? current.map(String).includes(selected)
          : String(current) === selected;
      });
      if (!matchesFilters || !matchesRanges(record, values, config.ranges || [])) {
        return false;
      }
      return (config.correlations || []).every((correlation) =>
        matchesCorrelation(record, values, correlation)
      );
    });
    filtered.sort(compareBy(
      values.sort || config.sorts[0][0],
      values.direction || "asc",
    ));
    body.replaceChildren();
    filtered.slice(0, state.visible).forEach((record) => {
      const row = document.createElement("tr");
      config.columns.forEach(([, renderer]) => {
        const cell = document.createElement("td");
        cell.append(renderer(record));
        row.append(cell);
      });
      body.append(row);
    });
    summary.textContent = `${filtered.length.toLocaleString()} record${filtered.length === 1 ? "" : "s"}`;
    more.hidden = filtered.length <= state.visible;
    tableWrap.hidden = filtered.length === 0;
    updateUrl(form, state.visible);
  };

  form.addEventListener("input", () => { state.visible = PAGE_SIZE; render(); });
  form.addEventListener("change", () => { state.visible = PAGE_SIZE; render(); });
  reset.addEventListener("click", () => {
    form.reset();
    form.querySelectorAll("[data-rw-match-mode]").forEach((mode) => {
      mode.value = mode.dataset.default;
    });
    form.querySelectorAll("select").forEach(syncSelect);
    state.visible = PAGE_SIZE;
    render();
  });
  more.addEventListener("click", () => { state.visible += PAGE_SIZE; render(); });
  window.addEventListener("popstate", () => window.location.reload());
  render();
}

function valuesFor(records, key) {
  const values = records.flatMap((record) => {
    const value = getValue(record, key);
    return Array.isArray(value) ? value : [value];
  }).filter((value) => value !== null && value !== undefined && value !== "");
  return [...new Set(values)].sort((left, right) =>
    String(left).localeCompare(String(right), undefined, { numeric: true })
  );
}

function getValue(record, path) {
  return path.split(".").reduce((value, key) => value == null ? value : value[key], record);
}

function formValues(form) {
  const data = new FormData(form);
  const values = Object.fromEntries(data);
  form.querySelectorAll("select[multiple]").forEach((select) => {
    values[select.name] = data.getAll(select.name).map(String);
  });
  return values;
}

function matchesSelected(options, selected, mode) {
  return mode === "any"
    ? selected.some((value) => options.includes(value))
    : selected.every((value) => options.includes(value));
}

function matchesRanges(record, values, ranges) {
  return ranges.every((range) => {
    const selectedMin = values[`${range.key}_min`];
    const selectedMax = values[`${range.key}_max`];
    if (selectedMin === "" && selectedMax === "") return true;
    if (range.mode === "overlap") {
      const recordMin = getValue(record, range.minKey);
      const recordMax = getValue(record, range.maxKey);
      if (recordMin == null || recordMax == null) return false;
      if (selectedMin !== "" && recordMax < Number(selectedMin)) return false;
      if (selectedMax !== "" && recordMin > Number(selectedMax)) return false;
      return true;
    }
    const current = getValue(record, range.key);
    if (current == null) return false;
    if (selectedMin !== "" && current < Number(selectedMin)) return false;
    return selectedMax === "" || current <= Number(selectedMax);
  });
}

function matchesCorrelation(record, values, correlation) {
  const rawLeft = values[correlation.left];
  const left = (Array.isArray(rawLeft) ? rawLeft : [rawLeft])
    .filter((value) => value !== null && value !== undefined && value !== "")
    .map(String);
  const right = String(values[correlation.right] || "").toLowerCase();
  if (left.length === 0 || !right) return true;
  const related = getValue(record, correlation.path) || {};
  const correlated = left.filter((leftValue) =>
    (related[leftValue] || []).some((value) =>
      displayFilter(correlation.right, value).toLowerCase().includes(right)
    )
  );
  return values[`${correlation.left}_mode`] === "any"
    ? correlated.length > 0
    : correlated.length === left.length;
}

function compareBy(path, direction) {
  const multiplier = direction === "desc" ? -1 : 1;
  return (left, right) => {
    const leftValue = getValue(left, path);
    const rightValue = getValue(right, path);
    if (typeof leftValue === "number" && typeof rightValue === "number") {
      return (leftValue - rightValue) * multiplier;
    }
    return String(leftValue ?? "").localeCompare(
      String(rightValue ?? ""),
      undefined,
      { numeric: true },
    ) * multiplier;
  };
}

function updateUrl(form, visible) {
  const params = new URLSearchParams();
  for (const [key, value] of new FormData(form)) {
    const field = form.elements.namedItem(key);
    if (value && (!field.dataset.default || field.dataset.default !== value)) {
      params.append(key, value);
    }
  }
  if (visible > PAGE_SIZE) params.set("page", String(Math.ceil(visible / PAGE_SIZE)));
  const query = params.toString();
  history.replaceState(
    null,
    "",
    `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`,
  );
}
