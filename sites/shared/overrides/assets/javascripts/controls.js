import { title } from "./formatting.js";

const COMBOBOX_RESULT_LIMIT = 50;
const comboboxWidgets = new WeakMap();
const selectWidgets = new WeakMap();
let elementSequence = 0;

export function initializeControls() {
  document.addEventListener("pointerdown", (event) => {
    const openWidget = event.target.closest?.(".rw-select--open, .rw-combobox--open");
    closeOpenMenus(openWidget);
  });
}

export function control(kind, labelText, name) {
  const field = document.createElement("div");
  field.className = "rw-control";
  const caption = document.createElement("label");
  caption.className = "rw-control__label";
  caption.textContent = labelText;
  const input = document.createElement(kind);
  input.id = `rw-control-${++elementSequence}`;
  input.name = name;
  caption.htmlFor = input.id;
  field.append(caption, input);
  return { label: field, input };
}

export function enhanceCombobox(input, label, values) {
  if (comboboxWidgets.has(input)) return;
  const widget = document.createElement("div");
  widget.className = "rw-combobox";
  const menu = document.createElement("div");
  menu.id = `rw-combobox-menu-${++elementSequence}`;
  menu.className = "rw-select__menu rw-combobox__menu";
  menu.hidden = true;
  const optionList = document.createElement("div");
  optionList.id = `${menu.id}-options`;
  optionList.className = "rw-select__options";
  optionList.role = "listbox";
  optionList.setAttribute("aria-label", `${label} suggestions`);
  const status = document.createElement("div");
  status.className = "rw-combobox__status";
  status.setAttribute("aria-live", "polite");
  menu.append(optionList, status);

  input.setAttribute("autocomplete", "off");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-controls", optionList.id);
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("role", "combobox");
  input.insertAdjacentElement("afterend", widget);
  widget.append(input, menu);

  const parts = { activeIndex: -1, input, menu, optionList, status, values, widget };
  comboboxWidgets.set(input, parts);
  comboboxWidgets.set(widget, parts);

  input.addEventListener("focus", () => openCombobox(widget));
  input.addEventListener("input", () => openCombobox(widget));
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (!widget.classList.contains("rw-combobox--open")) return;
      event.preventDefault();
      closeCombobox(widget);
      return;
    }
    if (event.key === "Enter" && parts.activeIndex >= 0) {
      event.preventDefault();
      const options = [...optionList.querySelectorAll(".rw-select__option")];
      chooseComboboxOption(input, options[parts.activeIndex]);
      return;
    }
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    if (!widget.classList.contains("rw-combobox--open")) openCombobox(widget);
    const options = [...optionList.querySelectorAll(".rw-select__option")];
    const last = options.length - 1;
    if (last < 0) return;
    if (event.key === "Home") parts.activeIndex = 0;
    if (event.key === "End") parts.activeIndex = last;
    if (event.key === "ArrowDown") parts.activeIndex = Math.min(parts.activeIndex + 1, last);
    if (event.key === "ArrowUp") {
      parts.activeIndex = parts.activeIndex < 0 ? last : Math.max(parts.activeIndex - 1, 0);
    }
    syncComboboxActive(parts);
  });
  widget.addEventListener("focusout", (event) => {
    if (!widget.contains(event.relatedTarget)) closeCombobox(widget);
  });
}

function renderComboboxOptions(parts) {
  const query = parts.input.value.trim().toLowerCase();
  const matches = parts.values.filter((value) => value.toLowerCase().includes(query));
  const visible = matches.slice(0, COMBOBOX_RESULT_LIMIT);
  parts.activeIndex = -1;
  parts.input.removeAttribute("aria-activedescendant");
  parts.optionList.replaceChildren();
  visible.forEach((value, index) => {
    const option = document.createElement("button");
    option.type = "button";
    option.id = `${parts.menu.id}-option-${index}`;
    option.className = "rw-select__option";
    option.role = "option";
    option.tabIndex = -1;
    option.textContent = value;
    option.setAttribute("aria-selected", "false");
    option.addEventListener("pointerdown", (event) => event.preventDefault());
    option.addEventListener("click", () => chooseComboboxOption(parts.input, option));
    option.addEventListener("pointermove", () => {
      parts.activeIndex = index;
      syncComboboxActive(parts);
    });
    parts.optionList.append(option);
  });
  parts.status.textContent = matches.length === 0
    ? "No suggestions"
    : matches.length > visible.length
      ? `${visible.length} of ${matches.length} suggestions shown. Keep typing to narrow the list.`
      : `${matches.length} suggestion${matches.length === 1 ? "" : "s"}`;
}

function chooseComboboxOption(input, option) {
  if (!option) return;
  input.value = option.textContent;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  closeCombobox(comboboxWidgets.get(input).widget);
  input.focus();
}

function syncComboboxActive(parts) {
  const options = [...parts.optionList.querySelectorAll(".rw-select__option")];
  options.forEach((option, index) => {
    const active = index === parts.activeIndex;
    option.classList.toggle("rw-select__option--active", active);
    option.setAttribute("aria-selected", String(active));
  });
  const active = options[parts.activeIndex];
  if (active) {
    parts.input.setAttribute("aria-activedescendant", active.id);
    active.scrollIntoView({ block: "nearest" });
  } else {
    parts.input.removeAttribute("aria-activedescendant");
  }
}

function openCombobox(widget) {
  const parts = comboboxWidgets.get(widget);
  if (!parts) return;
  closeOpenMenus(widget);
  renderComboboxOptions(parts);
  widget.classList.add("rw-combobox--open");
  parts.input.setAttribute("aria-expanded", "true");
  parts.menu.hidden = false;
  positionMenu(widget, parts.input, parts.menu);
}

function closeCombobox(widget) {
  const parts = comboboxWidgets.get(widget);
  if (!parts) return;
  widget.classList.remove("rw-combobox--open");
  parts.input.setAttribute("aria-expanded", "false");
  parts.input.removeAttribute("aria-activedescendant");
  parts.menu.hidden = true;
  parts.activeIndex = -1;
}

export function enhanceSelect(select, label) {
  if (selectWidgets.has(select)) return;
  const widget = document.createElement("div");
  widget.className = "rw-select";
  widget.classList.toggle("rw-select--multiple", select.multiple);
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.id = `rw-select-trigger-${++elementSequence}`;
  trigger.className = "rw-select__trigger";
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  const menu = document.createElement("div");
  menu.id = `rw-select-menu-${++elementSequence}`;
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
  let match = null;
  let modeInput = null;
  const modeButtons = [];
  if (select.multiple) {
    modeInput = select.parentElement.querySelector("[data-rw-match-mode]");
    match = document.createElement("div");
    match.className = "rw-select__match";
    match.hidden = true;
    const matchLabel = document.createElement("span");
    matchLabel.textContent = "Match";
    const matchOptions = document.createElement("span");
    matchOptions.className = "rw-select__match-options";
    matchOptions.role = "group";
    matchOptions.setAttribute("aria-label", `${label} match mode`);
    for (const [value, text] of [["all", "All"], ["any", "Any"]]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "rw-select__match-option";
      button.dataset.value = value;
      button.textContent = text;
      button.addEventListener("click", () => {
        if (!modeInput || modeInput.value === value) return;
        modeInput.value = value;
        syncSelect(select);
        modeInput.dispatchEvent(new Event("change", { bubbles: true }));
      });
      modeButtons.push(button);
      matchOptions.append(button);
    }
    match.append(matchLabel, matchOptions);
    menu.append(match);
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
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const focus = event.key === "ArrowUp" || event.key === "End"
      ? "last"
      : event.key === "Home" ? "first" : "selected";
    openSelect(widget, focus);
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
  const parts = {
    clear,
    label,
    match,
    menu,
    modeButtons,
    modeInput,
    optionList,
    trigger,
    widget,
  };
  selectWidgets.set(select, parts);
  selectWidgets.set(widget, parts);
  select.addEventListener("change", () => syncSelect(select));
  syncSelect(select);
}

export function syncSelect(select) {
  const parts = selectWidgets.get(select);
  if (!parts) return;
  const selected = [...select.selectedOptions];
  if (selected.length < 2 && parts.modeInput) parts.modeInput.value = "all";
  const mode = parts.modeInput?.value === "any" ? "any" : "all";
  parts.trigger.textContent = select.multiple
    ? selected.length === 0
      ? select.dataset.placeholder || "Any"
      : selected.length === 1
        ? selected[0].textContent
        : `${selected.length} selected · ${title(mode)}`
    : selected[0]?.textContent || "Select";
  const modeLabel = selected.length > 1 ? `, match ${mode}` : "";
  parts.trigger.setAttribute(
    "aria-label",
    `${parts.label}: ${selected.length > 1 ? `${selected.length} selected` : parts.trigger.textContent}${modeLabel}`
  );
  const selectedValues = new Set(selected.map((option) => option.value));
  parts.menu.querySelectorAll(".rw-select__option").forEach((option) => {
    const active = selectedValues.has(option.dataset.value);
    option.classList.toggle("rw-select__option--selected", active);
    option.setAttribute("aria-selected", String(active));
  });
  if (parts.clear) parts.clear.disabled = selected.length === 0;
  if (parts.match) parts.match.hidden = selected.length < 2;
  parts.modeButtons.forEach((button) => {
    const active = button.dataset.value === mode;
    button.classList.toggle("rw-select__match-option--selected", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function openSelect(widget, focus = "selected") {
  const parts = selectWidgets.get(widget);
  if (!parts) return;
  closeOpenMenus(widget);
  widget.classList.add("rw-select--open");
  parts.trigger.setAttribute("aria-expanded", "true");
  parts.menu.hidden = false;
  positionMenu(widget, parts.trigger, parts.menu);
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

function closeOpenMenus(except) {
  document.querySelectorAll(".rw-select--open").forEach((widget) => {
    if (widget !== except) closeSelect(widget);
  });
  document.querySelectorAll(".rw-combobox--open").forEach((widget) => {
    if (widget !== except) closeCombobox(widget);
  });
}

function positionMenu(widget, anchor, menu) {
  widget.classList.remove("rw-menu--above", "rw-menu--align-right");
  const anchorBounds = anchor.getBoundingClientRect();
  const menuBounds = menu.getBoundingClientRect();
  if (menuBounds.right > window.innerWidth - 16) {
    widget.classList.add("rw-menu--align-right");
  }
  const spaceBelow = window.innerHeight - anchorBounds.bottom;
  if (menuBounds.height > spaceBelow - 16 && anchorBounds.top > spaceBelow) {
    widget.classList.add("rw-menu--above");
  }
}
