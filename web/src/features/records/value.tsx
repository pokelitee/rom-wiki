import { EntityLink } from "../../components/entity-link";
import type { DataObject, Json } from "../../data/types";
import { TypeBadge } from "../../components/type-badge";
import { object } from "../../lib/json";
import {
  countRepeats,
  fieldLabel,
  tableScroll,
  formatName,
  formatScalar,
  isEmpty,
  isNamedReference,
  isScriptCommand,
  isTechnical,
} from "./fields";
import { columnRoute, entityRoute } from "./routes";
import { encounterGroups, isSlotList } from "./encounter";
import { GroupedSlotTable, SlotTable } from "./slot-table";

const TYPE_FIELDS = new Set(["type", "types", "natural_gift_type"]);
const NAME_KEYS = [
  "name",
  "pokemon_name",
  "trainer_name",
  "area_name",
  "destination_name",
];

// Relationship rows name places as [map header, name] pairs.
function isHeaderPair(value: Json): value is [number, string] {
  return (
    Array.isArray(value) &&
    value.length === 2 &&
    typeof value[0] === "number" &&
    typeof value[1] === "string"
  );
}

function visibleKeys(value: DataObject): string[] {
  return Object.keys(value).filter(
    (key) =>
      !isTechnical(key) || (key === "source" && isNamedReference(value[key])),
  );
}

// Nested lists and objects with nothing in them, such as an encounter's
// empty Unown form list, are left out of fact lists.
// Nested lists and objects with nothing in them are left out. Inside a
// record section, so are "No" and zero, which there only mean "does not
// apply" (an item's dozens of unused party effects, an unused shard cost).
function factKeys(value: DataObject, hideUnset: boolean): string[] {
  return visibleKeys(value).filter((key) => {
    const entry = value[key];
    if (hideUnset && (entry === false || entry === 0 || entry === null))
      return false;
    return !(entry && typeof entry === "object" && isEmpty(entry));
  });
}

function isScalarFact(value: Json | undefined): boolean {
  return (
    (value !== null && typeof value !== "object") || isNamedReference(value)
  );
}

// A column holding the same value on every row says nothing per row.
function isConstant(rows: DataObject[], key: string): boolean {
  if (rows.length < 3) return false;
  const first = JSON.stringify(rows[0][key]);
  return rows.every((row) => JSON.stringify(row[key]) === first);
}

function NamedReference({
  value,
  game,
  field,
  count = 1,
}: {
  value: DataObject;
  game: string;
  field: string;
  count?: number;
}) {
  const name = String(value.name);
  if (TYPE_FIELDS.has(field)) return <TypeBadge name={name} />;
  const route = entityRoute(value, field);
  const quantity = count > 1 && <span className="chip-count">×{count}</span>;
  return route ? (
    <EntityLink game={game} route={route}>
      {formatName(name)}
      {quantity}
    </EntityLink>
  ) : (
    <span>
      {formatScalar(field, name)}
      {quantity}
    </span>
  );
}

export function Value({
  value,
  game,
  field = "",
  depth = 0,
  encounters = false,
}: {
  value: Json;
  game: string;
  field?: string;
  depth?: number;
  // The value is an encounter area's section, where Pokémon are encounters.
  encounters?: boolean;
}) {
  if (value === null) return <span className="muted">—</span>;
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  if (typeof value === "number")
    return <span className="numeric">{formatScalar(field, value)}</span>;
  if (typeof value === "string") {
    if (/^https?:\/\//.test(value))
      return (
        <a href={value} rel="noreferrer" target="_blank">
          {field.includes("source") ? "View source ↗" : "View reference ↗"}
        </a>
      );
    return (
      <span className={field === "name" ? "font-medium" : undefined}>
        {value ? formatScalar(field, value) : "—"}
      </span>
    );
  }
  if (Array.isArray(value)) {
    const entries = value.filter(
      (entry) => !(entry && typeof entry === "object" && isEmpty(entry)),
    );
    if (!entries.length)
      return <span className="muted">{depth > 0 ? "—" : "No entries"}</span>;
    if (entries.every(isHeaderPair))
      return (
        <span className="badge-list chip-list">
          {entries.map(([header, name]) => (
            <EntityLink
              key={header}
              game={game}
              route={`locations/header-${String(header).padStart(3, "0")}`}
            >
              {name}
            </EntityLink>
          ))}
        </span>
      );
    if (entries.every((entry) => typeof entry !== "object"))
      return (
        <span className="badge-list">
          {entries.map((entry, index) =>
            TYPE_FIELDS.has(field) ? (
              <TypeBadge key={index} name={String(entry)} />
            ) : (
              <span className="badge" key={index}>
                {formatScalar(field, entry as string | number | boolean)}
              </span>
            ),
          )}
        </span>
      );
    if (entries.every(isNamedReference))
      return (
        <span className="badge-list chip-list">
          {(TYPE_FIELDS.has(field)
            ? entries
                .filter(
                  (entry, index) =>
                    entries.findIndex(
                      (other) => object(other).name === object(entry).name,
                    ) === index,
                )
                .map((value) => ({ value, count: 1 }))
            : countRepeats(entries)
          ).map(({ value: entry, count }, index) => (
            <NamedReference
              key={index}
              value={entry as DataObject}
              game={game}
              field={field}
              count={count}
            />
          ))}
        </span>
      );
    const rows = entries.map(object);
    if (isSlotList(rows)) return <SlotTable rows={rows} game={game} />;
    // Trainers read as "Galactic Grunt", class and name together.
    const trainerRows = rows.every(
      (row) =>
        typeof row.trainer_id === "number" &&
        typeof row.class_name === "string",
    );
    const nameOf = (row: DataObject, key: string) =>
      trainerRows && (key === "name" || key === "trainer_name")
        ? `${String(row.class_name)} ${String(row[key])}`
        : formatName(String(row[key]));
    const keys = [...new Set(rows.flatMap(visibleKeys))].filter(
      (key) =>
        !(trainerRows && key === "class_name") &&
        !rows.every(
          (row) => isEmpty(row[key]) || isScriptCommand(key, row[key]),
        ) &&
        (NAME_KEYS.includes(key) || !isConstant(rows, key)),
    );
    if (keys.length === 1 && rows.every((row) => isScalarFact(row[keys[0]])))
      return (
        <span className="badge-list chip-list">
          {rows.map((row, index) => {
            const cell = row[keys[0]];
            if (isNamedReference(cell))
              return (
                <NamedReference
                  key={index}
                  value={cell as DataObject}
                  game={game}
                  field={keys[0]}
                />
              );
            const route = NAME_KEYS.includes(keys[0])
              ? entityRoute(row, field)
              : undefined;
            // A lone value other than a name, such as a static
            // encounter's level, says what it is.
            const label = NAME_KEYS.includes(keys[0])
              ? nameOf(row, keys[0])
              : `${fieldLabel(keys[0])} ${formatScalar(keys[0], cell as string | number | boolean)}`;
            return route ? (
              <EntityLink key={index} game={game} route={route}>
                {label}
              </EntityLink>
            ) : (
              <span className="badge" key={index}>
                {label}
              </span>
            );
          })}
        </span>
      );
    if (keys.length && keys.length <= 9 && depth < 5)
      return (
        <div className={tableScroll(rows.length)}>
          <table className="detail-table">
            <thead>
              <tr>
                {keys.map((key) => (
                  <th key={key}>{fieldLabel(key)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index}>
                  {keys.map((key) => {
                    const route = NAME_KEYS.includes(key)
                      ? entityRoute(row, field)
                      : columnRoute(row, key);
                    return (
                      <td key={key}>
                        {route ? (
                          <EntityLink game={game} route={route}>
                            {nameOf(row, key)}
                          </EntityLink>
                        ) : row[key] === undefined ||
                          isScriptCommand(key, row[key]) ? (
                          "—"
                        ) : (
                          <Value
                            value={row[key]}
                            game={game}
                            field={key}
                            depth={depth + 1}
                          />
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    return (
      <div className="value-list">
        {entries.map((entry, index) => (
          <div key={index}>
            <Value value={entry} game={game} field={field} depth={depth + 1} />
          </div>
        ))}
      </div>
    );
  }
  if (isNamedReference(value))
    return (
      <NamedReference value={value as DataObject} game={game} field={field} />
    );
  // An encounter method: how often it triggers, then its Pokémon.
  if (typeof value.rate === "number" && Array.isArray(value.slots)) {
    const slots = value.slots.filter((slot) => slot !== null).map(object);
    if (isSlotList(slots))
      return (
        <div className="encounter-method">
          <p className="muted">Encounter rate {value.rate}</p>
          <SlotTable rows={slots} game={game} />
        </div>
      );
  }
  const groups = encounterGroups(value, encounters);
  if (groups?.length) return <GroupedSlotTable groups={groups} game={game} />;
  const route = entityRoute(value, field);
  const name = value.name ?? value.pokemon_name ?? value.area_name;
  if (route && name) {
    const extra = Object.entries(value).filter(
      ([key, item]) =>
        !NAME_KEYS.includes(key) &&
        !isTechnical(key) &&
        item !== null &&
        typeof item !== "object",
    );
    return (
      <span className="entity-value">
        <EntityLink game={game} route={route}>
          {formatName(String(name))}
        </EntityLink>
        {extra.map(([key, item]) => (
          <span className="badge" key={key}>
            {fieldLabel(key)}:{" "}
            {formatScalar(key, item as string | number | boolean)}
          </span>
        ))}
      </span>
    );
  }
  const keys = factKeys(value, field !== "");
  if (!keys.length) return <span className="muted">—</span>;
  const grid = depth === 0 && keys.every((key) => isScalarFact(value[key]));
  return (
    <dl className={grid ? "fact-grid" : "fact-list"}>
      {keys.map((key) => (
        <div key={key}>
          <dt>{fieldLabel(key)}</dt>
          <dd>
            <Value
              value={value[key]}
              game={game}
              field={key}
              depth={depth + 1}
            />
          </dd>
        </div>
      ))}
    </dl>
  );
}
