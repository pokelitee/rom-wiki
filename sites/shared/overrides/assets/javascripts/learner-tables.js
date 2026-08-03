const LEARNER_TABLE_SCHEMA_VERSION = 1;

export function initializeLearnerTables() {
  document
    .querySelectorAll("[data-rw-learner-table]")
    .forEach(initializeLearnerTable);
}

function initializeLearnerTable(root) {
  if (root.dataset.rwInitialized) return;
  root.dataset.rwInitialized = "true";

  const interactive = root.querySelector("[data-rw-learner-interactive]");
  const payloadNode = root.querySelector("[data-rw-learner-data]");
  const fallback = root.querySelector("[data-rw-learner-fallback]");

  try {
    if (!interactive || !payloadNode || !fallback) {
      throw new Error("Learner table markup is incomplete.");
    }

    const data = validatePayload(JSON.parse(payloadNode.textContent));
    const pageCount = Math.max(1, Math.ceil(data.rows.length / data.page_size));
    let currentPage = requestedPage(data.page_param, pageCount);

    const summary = document.createElement("p");
    summary.className = "rw-learner-table__summary";
    summary.setAttribute("role", "status");
    summary.setAttribute("aria-live", "polite");

    const tableWrap = document.createElement("div");
    tableWrap.className = "rw-learner-table__table-wrap";
    const table = document.createElement("table");
    table.className = "rw-learner-table__table";
    const caption = document.createElement("caption");
    caption.className = "rw-visually-hidden";
    caption.textContent = data.label;
    table.append(caption, buildHead(data.columns));
    const body = document.createElement("tbody");
    table.append(body);
    tableWrap.append(table);

    const pagination = document.createElement("nav");
    pagination.className = "rw-learner-table__pagination";
    pagination.setAttribute("aria-label", `${data.label} pages`);
    const previous = paginationButton("Previous");
    const pageStatus = document.createElement("span");
    pageStatus.className = "rw-learner-table__page-status";
    const next = paginationButton("Next");
    pagination.append(previous, pageStatus, next);

    const render = () => {
      currentPage = Math.min(Math.max(currentPage, 1), pageCount);
      const start = (currentPage - 1) * data.page_size;
      const end = Math.min(start + data.page_size, data.rows.length);
      body.replaceChildren(
        ...data.rows.slice(start, end).map((row) => buildRow(row)),
      );
      summary.textContent = `${start + 1}–${end} of ${data.rows.length} learners`;
      pageStatus.textContent = `Page ${currentPage} of ${pageCount}`;
      previous.disabled = currentPage === 1;
      next.disabled = currentPage === pageCount;
      updatePageQuery(data.page_param, currentPage);
    };

    previous.addEventListener("click", () => {
      currentPage -= 1;
      render();
    });
    next.addEventListener("click", () => {
      currentPage += 1;
      render();
    });

    interactive.replaceChildren(summary, tableWrap, pagination);
    render();
    interactive.hidden = false;
    fallback.hidden = true;
    root.classList.add("rw-learner-table--ready");
  } catch (error) {
    root.classList.remove("rw-learner-table--ready");
    root.classList.add("rw-learner-table--failed");
    if (interactive) interactive.hidden = true;
    if (fallback) fallback.hidden = false;
  }
}

function validatePayload(value) {
  if (
    !value ||
    value.schema_version !== LEARNER_TABLE_SCHEMA_VERSION ||
    typeof value.label !== "string" ||
    !/^[a-z0-9_]+$/.test(value.page_param) ||
    !Number.isInteger(value.page_size) ||
    value.page_size < 1 ||
    !Array.isArray(value.columns) ||
    value.columns.length === 0 ||
    !value.columns.every((column) => typeof column === "string") ||
    !Array.isArray(value.rows) ||
    value.rows.length === 0
  ) {
    throw new Error("Learner table payload is invalid.");
  }
  value.rows.forEach((row) => {
    if (!Array.isArray(row) || row.length !== value.columns.length) {
      throw new Error("Learner table row is invalid.");
    }
    row.forEach(validateCell);
  });
  return value;
}

function validateCell(cell) {
  if (!cell || typeof cell !== "object") {
    throw new Error("Learner table cell is invalid.");
  }
  if (cell.kind === "text" && typeof cell.value === "string") return;
  if (
    cell.kind === "pokemon" &&
    typeof cell.label === "string" &&
    optionalString(cell.url) &&
    optionalString(cell.sprite_url)
  ) {
    return;
  }
  if (
    cell.kind === "types" &&
    Array.isArray(cell.values) &&
    cell.values.every(
      (type) =>
        type &&
        /^[a-z0-9-]+$/.test(type.name) &&
        typeof type.label === "string",
    )
  ) {
    return;
  }
  throw new Error("Learner table cell is invalid.");
}

function optionalString(value) {
  return value === null || typeof value === "string";
}

function requestedPage(pageParam, pageCount) {
  const value = new URL(window.location.href).searchParams.get(pageParam);
  if (!value || !/^\d+$/.test(value)) return 1;
  const requested = Number(value);
  return Number.isSafeInteger(requested)
    ? Math.min(Math.max(requested, 1), pageCount)
    : 1;
}

function updatePageQuery(pageParam, page) {
  const url = new URL(window.location.href);
  if (page === 1) url.searchParams.delete(pageParam);
  else url.searchParams.set(pageParam, String(page));
  window.history.replaceState(window.history.state, "", url);
}

function buildHead(columns) {
  const head = document.createElement("thead");
  const row = document.createElement("tr");
  columns.forEach((column) => {
    const heading = document.createElement("th");
    heading.scope = "col";
    heading.textContent = column;
    row.append(heading);
  });
  head.append(row);
  return head;
}

function buildRow(cells) {
  const row = document.createElement("tr");
  cells.forEach((cell) => row.append(buildCell(cell)));
  return row;
}

function buildCell(cell) {
  const tableCell = document.createElement("td");
  if (cell.kind === "text") {
    tableCell.textContent = cell.value;
  } else if (cell.kind === "pokemon") {
    tableCell.append(buildPokemonCell(cell));
  } else {
    tableCell.append(buildTypeCell(cell.values));
  }
  return tableCell;
}

function buildPokemonCell(cell) {
  const media = document.createElement("span");
  media.className = "rw-cell-media";
  if (cell.sprite_url) {
    const sprite = document.createElement("img");
    sprite.className = "rw-table-sprite";
    sprite.src = cell.sprite_url;
    sprite.alt = "";
    sprite.loading = "lazy";
    sprite.referrerPolicy = "no-referrer";
    media.append(sprite);
  }
  const label = document.createElement(cell.url ? "a" : "span");
  if (cell.url) label.href = cell.url;
  label.textContent = cell.label;
  media.append(label);
  return media;
}

function buildTypeCell(types) {
  if (types.length === 0) return document.createTextNode("—");
  const list = document.createElement("span");
  list.className = "rw-type-list";
  types.forEach((type) => {
    const badge = document.createElement("span");
    badge.className = `rw-type rw-type--${type.name}`;
    badge.textContent = type.label;
    list.append(badge);
  });
  return list;
}

function paginationButton(label) {
  const button = document.createElement("button");
  button.className = "rw-learner-table__page-button";
  button.type = "button";
  button.textContent = label;
  return button;
}
