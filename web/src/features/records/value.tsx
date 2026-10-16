import { Link } from "react-router-dom";
import type { DataObject, Json } from "../../data/types";
import { TypeBadge } from "../../components/type-badge";
import { title } from "../../lib/utils";
import { object } from "../../lib/json";
import {
  formatName,
  formatScalar,
  isEmpty,
  isNamedReference,
  isTechnical,
} from "./fields";
import { entityRoute } from "./routes";
import { isSlotList } from "./encounter";
import { SlotTable } from "./slot-table";

const TYPE_FIELDS = new Set(["type", "types", "natural_gift_type"]);
const NAME_KEYS = ["name", "pokemon_name", "area_name"];

function visibleKeys(value: DataObject): string[] {
  return Object.keys(value).filter((key) => !isTechnical(key));
}

// Nested lists and objects with nothing in them, such as an encounter's
// empty Unown form list, are left out of fact lists.
function factKeys(value: DataObject): string[] {
  return visibleKeys(value).filter((key) => {
    const entry = value[key];
    return !(entry && typeof entry === "object" && isEmpty(entry));
  });
}

function NamedReference({
  value,
  game,
  field,
}: {
  value: DataObject;
  game: string;
  field: string;
}) {
  const name = String(value.name);
  if (TYPE_FIELDS.has(field)) return <TypeBadge name={name} />;
  const route = entityRoute(value, field);
  return route ? (
    <Link to={`/${game}/${route}`}>{formatName(name)}</Link>
  ) : (
    <span>{formatScalar(field, name)}</span>
  );
}

export function Value({
  value,
  game,
  field = "",
  depth = 0,
}: {
  value: Json;
  game: string;
  field?: string;
  depth?: number;
}) {
  if (value === null) return <span className="muted">None</span>;
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
    if (!entries.length) return <span className="muted">No entries</span>;
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
        <span className="badge-list">
          {(TYPE_FIELDS.has(field)
            ? entries.filter(
                (entry, index) =>
                  entries.findIndex(
                    (other) => object(other).name === object(entry).name,
                  ) === index,
              )
            : entries
          ).map((entry, index) => (
            <NamedReference
              key={index}
              value={entry as DataObject}
              game={game}
              field={field}
            />
          ))}
        </span>
      );
    const rows = entries.map(object);
    if (isSlotList(rows)) return <SlotTable rows={rows} game={game} />;
    const keys = [...new Set(rows.flatMap(visibleKeys))].filter(
      (key) => !rows.every((row) => isEmpty(row[key])),
    );
    if (keys.length && keys.length <= 9 && depth < 5)
      return (
        <div className="table-scroll">
          <table className="detail-table">
            <thead>
              <tr>
                {keys.map((key) => (
                  <th key={key}>{title(key)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index}>
                  {keys.map((key) => {
                    const route = NAME_KEYS.includes(key)
                      ? entityRoute(row, field)
                      : undefined;
                    return (
                      <td key={key}>
                        {route ? (
                          <Link to={`/${game}/${route}`}>
                            {formatName(String(row[key]))}
                          </Link>
                        ) : row[key] === undefined ? (
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
  const route = entityRoute(value, field);
  const name = value.name ?? value.pokemon_name ?? value.area_name;
  const sprite = object(value.sprite).url;
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
        {typeof sprite === "string" && (
          <img loading="lazy" src={sprite} alt="" width={40} height={40} />
        )}
        <Link to={`/${game}/${route}`}>{formatName(String(name))}</Link>
        {extra.map(([key, item]) => (
          <span className="badge" key={key}>
            {title(key)}: {formatScalar(key, item as string | number | boolean)}
          </span>
        ))}
      </span>
    );
  }
  return (
    <dl className="fact-list">
      {factKeys(value).map((key) => (
        <div key={key}>
          <dt>{title(key)}</dt>
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
