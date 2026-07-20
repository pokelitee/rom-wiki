(function () {
  "use strict";

  const theme = document.querySelector('meta[name="romwiki-theme"]');
  if (theme) document.documentElement.dataset.romwikiTheme = theme.content;

  document.querySelectorAll("[data-rw-game-picker]").forEach((picker) => {
    picker.addEventListener("change", () => {
      if (picker.value) window.location.assign(picker.value);
    });
  });

  document.querySelectorAll("img[data-rw-sprite]").forEach((image) => {
    image.addEventListener("error", () => {
      image.hidden = true;
      const fallback = image.parentElement.querySelector(".rw-summary__placeholder");
      if (fallback) fallback.hidden = false;
    }, { once: true });
  });

  const CATALOGS = {
    pokemon: {
      searchPlaceholder: "Search Pokémon, types, or abilities",
      filters: [{ key: "types", label: "Type" }, { key: "abilities", label: "Ability", control: "datalist" }, { key: "egg_groups", label: "Egg group" }],
      ranges: [{ key: "bst", label: "BST" }],
      sorts: [["dex", "Pokédex number"], ["label", "Name"], ["bst", "Base stat total"], ["stats.hp", "HP"], ["stats.attack", "Attack"], ["stats.defense", "Defense"], ["stats.special_attack", "Sp. Atk"], ["stats.special_defense", "Sp. Def"], ["stats.speed", "Speed"]],
      columns: [["Pokémon", pokemonName], ["Type", typeList], ["Abilities", (r) => text(r.abilities.map(title).join(", ") || "—")], ["HP", (r) => stat(r, "hp")], ["Atk", (r) => stat(r, "attack")], ["Def", (r) => stat(r, "defense")], ["SpA", (r) => stat(r, "special_attack")], ["SpD", (r) => stat(r, "special_defense")], ["Spe", (r) => stat(r, "speed")], ["BST", (r) => text(r.bst, "rw-catalog__number")]],
    },
    moves: {
      searchPlaceholder: "Search moves or machine numbers",
      filters: [{ key: "type", label: "Type" }, { key: "damage_class", label: "Class" }, { key: "access_methods", label: "Available as" }],
      ranges: [{ key: "power", label: "Power" }],
      sorts: [["label", "Name"], ["id", "Move ID"], ["power", "Power"], ["accuracy", "Accuracy"], ["pp", "PP"]],
      columns: [["Move", recordLink], ["Type", (r) => typeBadge(r.type)], ["Class", (r) => text(title(r.damage_class))], ["Power", (r) => numberOrDash(r.power)], ["Accuracy", (r) => text(r.accuracy ? `${r.accuracy}%` : "Always")], ["PP", (r) => text(r.pp, "rw-catalog__number")], ["Available as", accessMethods]],
    },
    trainers: {
      searchPlaceholder: "Search trainers, locations, or party Pokémon",
      filters: [{ key: "class_name", label: "Class", control: "datalist" }, { key: "locations", label: "Location", control: "datalist" }, { key: "pokemon", label: "Party Pokémon", control: "datalist" }, { key: "double_battle", label: "Battle format" }, { key: "linked", label: "Location status" }],
      ranges: [{ key: "level", label: "Party level", mode: "overlap", minKey: "min_level", maxKey: "max_level" }],
      sorts: [["label", "Name"], ["id", "Trainer ID"], ["min_level", "Minimum level"], ["max_level", "Maximum level"], ["party_size", "Party size"]],
      columns: [["Trainer", recordLink], ["Location", (r) => text(r.location_label || "Unlinked")], ["Party", trainerParty], ["Format", (r) => text(r.double_battle ? "Double" : "Single")]],
    },
    locations: {
      searchPlaceholder: "Search location or internal map name",
      filters: [{ key: "features", label: "Contains" }],
      sorts: [["label", "Name"], ["id", "Header ID"]],
      columns: [["Location", recordLink], ["Contains", (r) => text(r.features.map(title).join(", ") || "—")], ["Map ID", locationIdentifier]],
    },
    encounters: {
      searchPlaceholder: "Search areas or wild Pokémon",
      filters: [{ key: "methods", label: "Method" }, { key: "pokemon", label: "Pokémon", control: "datalist" }],
      ranges: [{ key: "level", label: "Level", mode: "overlap", minKey: "min_level", maxKey: "max_level" }],
      correlations: [{ left: "methods", right: "pokemon", path: "method_pokemon" }],
      sorts: [["label", "Location"], ["id", "Area ID"], ["min_level", "Minimum level"], ["max_level", "Maximum level"]],
      columns: [["Area", recordLink], ["Methods", (r) => text(r.methods.map(title).join(", "))], ["Levels", (r) => text(r.min_level == null ? "—" : `${r.min_level}–${r.max_level}`, "rw-catalog__number")], ["Pokémon", (r) => previewList(r.pokemon)]],
    },
  };

  document.querySelectorAll("[data-rw-catalog]").forEach(loadCatalog);

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
      status.textContent = "Interactive catalog unavailable. The complete static list is shown below.";
      root.classList.add("rw-catalog--failed");
    }
  }

  function enhanceCatalog(root, records, config) {
    const params = new URLSearchParams(window.location.search);
    const state = { visible: Math.max(1, Number(params.get("page")) || 1) * 50 };
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
      const kind = filter.control === "datalist" ? "input" : "select";
      const field = control(kind, label, key);
      if (filter.control === "datalist") {
        field.input.type = "search";
        field.input.placeholder = `Any ${label.toLowerCase()}`;
        const options = document.createElement("datalist");
        options.id = `rw-${root.dataset.rwKind}-${key}`;
        valuesFor(records, key).forEach((value) => {
          options.append(new Option(displayFilter(key, value)));
        });
        field.input.setAttribute("list", options.id);
        field.label.append(options);
      } else {
        field.input.append(new Option(`Any ${label.toLowerCase()}`, ""));
        valuesFor(records, key).forEach((value) => {
          field.input.append(new Option(displayFilter(key, value), String(value)));
        });
      }
      field.input.value = params.get(key) || "";
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
    more.textContent = "Show 50 more";
    root.append(form, summary, tableWrap, more);

    const render = () => {
      const values = Object.fromEntries(new FormData(form));
      const query = String(values.q || "").trim().toLowerCase();
      let filtered = records.filter((record) => {
        if (query && !record.search_text.includes(query)) return false;
        const matchesFilters = config.filters.every((filter) => {
          const { key } = filter;
          const selected = String(values[key] || "");
          if (!selected) return true;
          const current = getValue(record, key);
          if (filter.control === "datalist") {
            const options = Array.isArray(current) ? current : [current];
            const normalized = selected.toLowerCase();
            return options.some((value) =>
              displayFilter(key, value).toLowerCase().includes(normalized)
            );
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

    form.addEventListener("input", () => { state.visible = 50; render(); });
    form.addEventListener("change", () => { state.visible = 50; render(); });
    reset.addEventListener("click", () => { form.reset(); state.visible = 50; render(); });
    more.addEventListener("click", () => { state.visible += 50; render(); });
    window.addEventListener("popstate", () => window.location.reload());
    render();
  }

  function control(kind, labelText, name) {
    const label = document.createElement("label");
    const caption = document.createElement("span");
    caption.textContent = labelText;
    const input = document.createElement(kind);
    input.name = name;
    label.append(caption, input);
    return { label, input };
  }

  function valuesFor(records, key) {
    const values = records.flatMap((record) => {
      const value = getValue(record, key);
      return Array.isArray(value) ? value : [value];
    }).filter((value) => value !== null && value !== undefined && value !== "");
    return [...new Set(values)].sort((a, b) => String(a).localeCompare(String(b), undefined, { numeric: true }));
  }

  function getValue(record, path) {
    return path.split(".").reduce((value, key) => value == null ? value : value[key], record);
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
    const left = String(values[correlation.left] || "");
    const right = String(values[correlation.right] || "").toLowerCase();
    if (!left || !right) return true;
    const related = getValue(record, correlation.path)?.[left] || [];
    return related.some((value) =>
      displayFilter(correlation.right, value).toLowerCase().includes(right)
    );
  }

  function compareBy(path, direction) {
    const multiplier = direction === "desc" ? -1 : 1;
    return (left, right) => {
      const a = getValue(left, path);
      const b = getValue(right, path);
      if (typeof a === "number" && typeof b === "number") return (a - b) * multiplier;
      return String(a ?? "").localeCompare(String(b ?? ""), undefined, { numeric: true }) * multiplier;
    };
  }

  function updateUrl(form, visible) {
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(form)) {
      const field = form.elements.namedItem(key);
      if (value && (!field.dataset.default || field.dataset.default !== value)) {
        params.set(key, value);
      }
    }
    if (visible > 50) params.set("page", String(Math.ceil(visible / 50)));
    const query = params.toString();
    history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`);
  }

  function displayFilter(key, value) {
    if (key === "double_battle") return value === true ? "Double" : "Single";
    if (key === "linked") return value === true ? "Mapped" : "Unlinked";
    if (key === "referenced") return value === true ? "Referenced" : "Unreferenced";
    if (key === "access_methods" && value === "machine") return "TM / HM";
    return title(String(value));
  }

  function title(value) {
    return String(value).replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function text(value, className) {
    const span = document.createElement("span");
    if (className) span.className = className;
    span.textContent = value;
    return span;
  }

  function recordLink(record) {
    const link = document.createElement("a");
    link.href = record.url;
    link.textContent = record.label;
    return link;
  }

  function pokemonName(record) {
    const wrap = document.createElement("span");
    wrap.className = "rw-catalog__name";
    const number = text(`#${String(record.dex).padStart(3, "0")}`, "rw-catalog__dex");
    wrap.append(number, recordLink(record));
    return wrap;
  }

  function typeBadge(value) {
    return text(title(value), `rw-type rw-type--${value}`);
  }

  function typeList(record) {
    const wrap = document.createElement("span");
    wrap.className = "rw-type-list";
    record.types.forEach((value) => wrap.append(typeBadge(value)));
    return wrap;
  }

  function numberOrDash(value) {
    return text(value || "—", "rw-catalog__number");
  }

  function stat(record, key) {
    return text(record.stats[key], "rw-catalog__number");
  }

  function accessMethods(record) {
    return text(
      record.access_methods.map((value) => displayFilter("access_methods", value)).join(", ") || "—"
    );
  }

  function trainerParty(record) {
    return text(
      record.party.map((member) => `${member.name} Lv. ${member.level}`).join(", "),
      "rw-catalog__list",
    );
  }

  function locationIdentifier(record) {
    const wrap = document.createElement("span");
    wrap.className = "rw-catalog__map-id";
    wrap.append(
      text(record.internal_name, "rw-catalog__code"),
      text(`Header ${record.id}`, "rw-catalog__number"),
    );
    return wrap;
  }

  function previewList(values) {
    const visible = values.slice(0, 6);
    const remaining = values.length - visible.length;
    return text(
      `${visible.join(", ")}${remaining > 0 ? ` +${remaining} more` : ""}` || "—",
      "rw-catalog__list",
    );
  }
})();
