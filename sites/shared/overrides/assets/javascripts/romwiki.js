(function () {
  "use strict";

  const theme = document.querySelector('meta[name="romwiki-theme"]');
  if (theme) document.documentElement.dataset.romwikiTheme = theme.content;

  const DISPLAY_NAMES = Object.freeze({
    "poke-balls": "Poké Balls",
    "poke-radar": "Poké Radar",
    "tm-hm": "TM / HM",
    "vs-recorder": "Vs. Recorder",
    "vs-seeker": "Vs. Seeker",
  });
  const selectWidgets = new WeakMap();
  let selectSequence = 0;

  document.querySelectorAll("[data-rw-game-picker]").forEach((picker) => {
    picker.addEventListener("change", () => {
      if (picker.value) window.location.assign(picker.value);
    });
    enhanceSelect(picker, "Choose a game");
  });

  document.addEventListener("pointerdown", (event) => {
    document.querySelectorAll(".rw-select--open").forEach((widget) => {
      if (!widget.contains(event.target)) closeSelect(widget);
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
    items: {
      searchPlaceholder: "Search items, locations, or uses",
      filters: [{ key: "pocket", label: "Pocket" }, { key: "field_use", label: "Field use" }, { key: "features", label: "Referenced by", multi: true }, { key: "locations", label: "Location", control: "datalist" }],
      ranges: [{ key: "price", label: "Price" }, { key: "fling_power", label: "Fling power" }],
      sorts: [["id", "Item ID"], ["label", "Name"], ["price", "Price"], ["fling_power", "Fling power"]],
      columns: [["Item", recordLink], ["Pocket", (r) => text(title(r.pocket))], ["Price", (r) => text(r.price ? `₽${r.price.toLocaleString()}` : "Not sold", "rw-catalog__number")], ["Fling", (r) => numberOrDash(r.fling_power)], ["Referenced by", (r) => text(r.features.map(title).join(", ") || "—")]],
    },
    abilities: {
      searchPlaceholder: "Search abilities or Pokémon",
      filters: [{ key: "pokemon", label: "Pokémon", control: "datalist" }, { key: "status", label: "Assignment" }],
      sorts: [["id", "Ability ID"], ["label", "Name"], ["pokemon_count", "Pokémon count"]],
      columns: [["Ability", recordLink], ["ID", (r) => text(r.id, "rw-catalog__number")], ["Pokémon", (r) => previewList(r.pokemon)], ["Count", (r) => text(r.pokemon_count, "rw-catalog__number")]],
    },
    pokemon: {
      searchPlaceholder: "Search Pokémon, types, or abilities",
      filters: [{ key: "types", label: "Type", multi: true }, { key: "abilities", label: "Ability", control: "datalist" }, { key: "egg_groups", label: "Egg group", multi: true }],
      ranges: [{ key: "bst", label: "BST" }],
      sorts: [["dex", "Pokédex number"], ["label", "Name"], ["bst", "Base stat total"], ["stats.hp", "HP"], ["stats.attack", "Attack"], ["stats.defense", "Defense"], ["stats.special_attack", "Sp. Atk"], ["stats.special_defense", "Sp. Def"], ["stats.speed", "Speed"]],
      columns: [["Pokémon", pokemonName], ["Type", typeList], ["Abilities", (r) => text(r.abilities.map(title).join(", ") || "—")], ["HP", (r) => stat(r, "hp")], ["Atk", (r) => stat(r, "attack")], ["Def", (r) => stat(r, "defense")], ["SpA", (r) => stat(r, "special_attack")], ["SpD", (r) => stat(r, "special_defense")], ["Spe", (r) => stat(r, "speed")], ["BST", (r) => text(r.bst, "rw-catalog__number")]],
    },
    moves: {
      searchPlaceholder: "Search moves or machine numbers",
      filters: [{ key: "type", label: "Type" }, { key: "damage_class", label: "Class" }, { key: "access_methods", label: "Available as", multi: true }],
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
      filters: [{ key: "features", label: "Contains", multi: true }],
      sorts: [["label", "Name"], ["id", "Header ID"]],
      columns: [["Location", recordLink], ["Contains", (r) => text(r.features.map(title).join(", ") || "—")], ["Map ID", locationIdentifier]],
    },
    encounters: {
      searchPlaceholder: "Search areas or wild Pokémon",
      filters: [{ key: "methods", label: "Method", multi: true }, { key: "pokemon", label: "Pokémon", control: "datalist" }],
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
    more.textContent = "Show 50 more";
    form.querySelectorAll("select").forEach((select) => {
      const label = select.closest(".rw-control")?.querySelector(".rw-control__label");
      enhanceSelect(select, label?.textContent || select.name);
    });
    root.append(form, summary, tableWrap, more);

    const render = () => {
      const values = formValues(form);
      const query = String(values.q || "").trim().toLowerCase();
      let filtered = records.filter((record) => {
        if (query && !record.search_text.includes(query)) return false;
        const matchesFilters = config.filters.every((filter) => {
          const { key } = filter;
          const selected = filter.multi
            ? values[key] || []
            : String(values[key] || "");
          if (filter.multi ? selected.length === 0 : !selected) return true;
          const current = getValue(record, key);
          if (filter.control === "datalist") {
            const options = Array.isArray(current) ? current : [current];
            const normalized = selected.toLowerCase();
            return options.some((value) =>
              displayFilter(key, value).toLowerCase().includes(normalized)
            );
          }
          if (filter.multi) {
            const options = (Array.isArray(current) ? current : [current]).map(String);
            return selected.every((value) => options.includes(value));
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
    reset.addEventListener("click", () => {
      form.reset();
      form.querySelectorAll("select").forEach(syncSelect);
      state.visible = 50;
      render();
    });
    more.addEventListener("click", () => { state.visible += 50; render(); });
    window.addEventListener("popstate", () => window.location.reload());
    render();
  }

  function control(kind, labelText, name) {
    const field = document.createElement("div");
    field.className = "rw-control";
    const caption = document.createElement("label");
    caption.className = "rw-control__label";
    caption.textContent = labelText;
    const input = document.createElement(kind);
    input.id = `rw-control-${++selectSequence}`;
    input.name = name;
    caption.htmlFor = input.id;
    field.append(caption, input);
    return { label: field, input };
  }

  function enhanceSelect(select, label) {
    if (selectWidgets.has(select)) return;
    const widget = document.createElement("div");
    widget.className = "rw-select";
    widget.classList.toggle("rw-select--multiple", select.multiple);
    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.id = `rw-select-trigger-${++selectSequence}`;
    trigger.className = "rw-select__trigger";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    const menu = document.createElement("div");
    menu.id = `rw-select-menu-${++selectSequence}`;
    menu.className = "rw-select__menu";
    menu.hidden = true;
    const optionList = document.createElement("div");
    optionList.className = "rw-select__options";
    optionList.role = "listbox";
    optionList.setAttribute("aria-label", label);
    if (select.multiple) optionList.setAttribute("aria-multiselectable", "true");
    trigger.setAttribute("aria-controls", menu.id);

    for (const option of select.options) {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "rw-select__option";
      item.role = "option";
      item.tabIndex = -1;
      item.dataset.value = option.value;
      item.textContent = option.textContent;
      item.addEventListener("click", () => {
        if (select.multiple) {
          option.selected = !option.selected;
        } else {
          select.value = option.value;
        }
        syncSelect(select);
        select.dispatchEvent(new Event("change", { bubbles: true }));
        if (!select.multiple) {
          closeSelect(widget);
          trigger.focus();
        }
      });
      optionList.append(item);
    }

    let clear = null;
    if (select.multiple) {
      const hint = document.createElement("p");
      hint.className = "rw-select__hint";
      hint.textContent = "Matches all selected";
      menu.append(hint);
      clear = document.createElement("button");
      clear.type = "button";
      clear.className = "rw-select__clear";
      clear.textContent = "Clear selection";
      clear.addEventListener("click", () => {
        for (const option of select.options) option.selected = false;
        syncSelect(select);
        select.dispatchEvent(new Event("change", { bubbles: true }));
        optionList.querySelector(".rw-select__option")?.focus();
      });
    }
    menu.append(optionList);
    if (clear) menu.append(clear);

    trigger.addEventListener("click", () => {
      if (widget.classList.contains("rw-select--open")) {
        closeSelect(widget);
      } else {
        openSelect(widget);
      }
    });
    trigger.addEventListener("keydown", (event) => {
      if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        const focus = event.key === "ArrowUp" || event.key === "End"
          ? "last"
          : event.key === "Home" ? "first" : "selected";
        openSelect(widget, focus);
      }
    });
    menu.addEventListener("keydown", (event) => {
      const options = [...menu.querySelectorAll(".rw-select__option")];
      const current = options.indexOf(document.activeElement);
      let target = null;
      if (event.key === "ArrowDown") target = options[Math.min(current + 1, options.length - 1)];
      if (event.key === "ArrowUp") target = options[Math.max(current - 1, 0)];
      if (event.key === "Home") target = options[0];
      if (event.key === "End") target = options.at(-1);
      if (event.key === "Escape") {
        event.preventDefault();
        closeSelect(widget);
        trigger.focus();
        return;
      }
      if (!target && event.key.length === 1 && event.key.trim()) {
        const ordered = [...options.slice(current + 1), ...options.slice(0, current + 1)];
        target = ordered.find((option) =>
          option.textContent.trim().toLowerCase().startsWith(event.key.toLowerCase())
        );
      }
      if (target) {
        event.preventDefault();
        target.focus();
      }
    });
    widget.addEventListener("focusout", (event) => {
      if (!widget.contains(event.relatedTarget)) closeSelect(widget);
    });

    select.hidden = true;
    select.setAttribute("aria-hidden", "true");
    select.tabIndex = -1;
    const caption = [...select.parentElement.children].find(
      (element) => element.tagName === "LABEL" && element.htmlFor === select.id
    );
    if (caption) caption.htmlFor = trigger.id;
    select.insertAdjacentElement("afterend", widget);
    widget.append(trigger, menu);
    const parts = { clear, label, menu, optionList, trigger, widget };
    selectWidgets.set(select, parts);
    selectWidgets.set(widget, parts);
    select.addEventListener("change", () => syncSelect(select));
    syncSelect(select);
  }

  function syncSelect(select) {
    const parts = selectWidgets.get(select);
    if (!parts) return;
    const selected = [...select.selectedOptions];
    parts.trigger.textContent = select.multiple
      ? selected.length === 0
        ? select.dataset.placeholder || "Any"
        : selected.length === 1 ? selected[0].textContent : `${selected.length} selected`
      : selected[0]?.textContent || "Select";
    parts.trigger.setAttribute("aria-label", `${parts.label}: ${parts.trigger.textContent}`);
    const selectedValues = new Set(selected.map((option) => option.value));
    parts.menu.querySelectorAll(".rw-select__option").forEach((option) => {
      const active = selectedValues.has(option.dataset.value);
      option.classList.toggle("rw-select__option--selected", active);
      option.setAttribute("aria-selected", String(active));
    });
    if (parts.clear) parts.clear.disabled = selected.length === 0;
  }

  function openSelect(widget, focus = "selected") {
    document.querySelectorAll(".rw-select--open").forEach((openWidget) => {
      if (openWidget !== widget) closeSelect(openWidget);
    });
    const parts = selectWidgets.get(widget);
    if (!parts) return;
    widget.classList.add("rw-select--open");
    parts.trigger.setAttribute("aria-expanded", "true");
    parts.menu.hidden = false;
    widget.classList.remove("rw-select--above", "rw-select--align-right");
    const triggerBounds = parts.trigger.getBoundingClientRect();
    const menuBounds = parts.menu.getBoundingClientRect();
    if (menuBounds.right > window.innerWidth - 16) {
      widget.classList.add("rw-select--align-right");
    }
    const spaceBelow = window.innerHeight - triggerBounds.bottom;
    if (menuBounds.height > spaceBelow - 16 && triggerBounds.top > spaceBelow) {
      widget.classList.add("rw-select--above");
    }
    if (focus) {
      const options = [...parts.menu.querySelectorAll(".rw-select__option")];
      const target = focus === "last"
        ? options.at(-1)
        : focus === "first"
          ? options[0]
          : parts.menu.querySelector(".rw-select__option--selected") || options[0];
      target?.focus();
    }
  }

  function closeSelect(widget) {
    const parts = selectWidgets.get(widget);
    if (!parts) return;
    widget.classList.remove("rw-select--open");
    parts.trigger.setAttribute("aria-expanded", "false");
    parts.menu.hidden = true;
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

  function formValues(form) {
    const data = new FormData(form);
    const values = Object.fromEntries(data);
    form.querySelectorAll("select[multiple]").forEach((select) => {
      values[select.name] = data.getAll(select.name).map(String);
    });
    return values;
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
    return left.every((leftValue) =>
      (related[leftValue] || []).some((value) =>
        displayFilter(correlation.right, value).toLowerCase().includes(right)
      )
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
        params.append(key, value);
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
    const normalized = String(value);
    return DISPLAY_NAMES[normalized]
      || normalized.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
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
