import { Link } from "react-router-dom";
import type { DataObject, Json } from "../../data/types";
import { title } from "../../lib/utils";
import { object } from "../../lib/json";

function entityRoute(value: DataObject, field: string): string | undefined {
  if (
    typeof value.encounter_route_key === "string" ||
    typeof value.encounter_route_key === "number"
  )
    return `encounters/${typeof value.encounter_route_key === "number" ? `area-${String(value.encounter_route_key).padStart(3, "0")}` : value.encounter_route_key}`;
  if (typeof value.trainer_id === "number")
    return `trainers/trainer-${String(value.trainer_id).padStart(4, "0")}`;
  if (typeof value.header_id === "number")
    return `locations/header-${String(value.header_id).padStart(3, "0")}`;
  if (typeof value.pokemon_slug === "string")
    return `pokemon/${value.pokemon_slug}`;
  if (typeof value.slug !== "string") return undefined;
  if (field.includes("abilit")) return `abilities/${value.slug}`;
  if (field.includes("move") || field === "replaces")
    return `moves/${value.slug}`;
  if (
    field.includes("item") ||
    field.includes("held") ||
    field === "victory_item"
  )
    return `items/${value.slug}`;
  if (
    field.includes("pokemon") ||
    field.includes("species") ||
    field.includes("evolution") ||
    field === "base_species"
  )
    return `pokemon/${value.slug}`;
  return undefined;
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
    return <span className="numeric">{value.toLocaleString()}</span>;
  if (typeof value === "string") {
    if (/^https?:\/\//.test(value))
      return (
        <a href={value} rel="noreferrer" target="_blank">
          {field.includes("source") ? "View source ↗" : "View reference ↗"}
        </a>
      );
    return (
      <span className={field === "name" ? "font-medium" : undefined}>
        {value || "—"}
      </span>
    );
  }
  if (Array.isArray(value)) {
    if (!value.length) return <span className="muted">No entries</span>;
    if (value.every((entry) => typeof entry !== "object"))
      return (
        <span className="badge-list">
          {value.map((entry, index) => (
            <span className="badge" key={index}>
              {String(entry)}
            </span>
          ))}
        </span>
      );
    const rows = value.map(object);
    const keys = [...new Set(rows.flatMap(Object.keys))].filter(
      (key) =>
        !["sprite", "sprites", "provenance", "slug", "source_url"].includes(
          key,
        ),
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
              {value.map((entry, index) => (
                <tr key={index}>
                  {keys.map((key) => {
                    const row = object(entry);
                    const route = [
                      "name",
                      "pokemon_name",
                      "area_name",
                    ].includes(key)
                      ? entityRoute(row, field)
                      : undefined;
                    return (
                      <td key={key}>
                        {route ? (
                          <Link to={`/${game}/${route}`}>
                            {String(row[key])}
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
        {value.map((entry, index) => (
          <div key={index}>
            <Value value={entry} game={game} field={field} depth={depth + 1} />
          </div>
        ))}
      </div>
    );
  }
  const route = entityRoute(value, field);
  const name = value.name ?? value.pokemon_name ?? value.area_name;
  const sprite = object(value.sprite).url;
  if (route && name) {
    const extra = Object.entries(value).filter(
      ([key]) =>
        ![
          "name",
          "pokemon_name",
          "slug",
          "sprite",
          "id",
          "member",
          "national_dex_id",
          "header_id",
          "trainer_id",
          "pokemon_slug",
        ].includes(key),
    );
    return (
      <span className="entity-value">
        {typeof sprite === "string" && (
          <img loading="lazy" src={sprite} alt="" width={40} height={40} />
        )}
        <Link to={`/${game}/${route}`}>{String(name)}</Link>
        {extra
          .filter(([, item]) => item !== null && typeof item !== "object")
          .map(([key, item]) => (
            <span className="badge" key={key}>
              {title(key)}: {String(item)}
            </span>
          ))}
      </span>
    );
  }
  return (
    <dl className="fact-list">
      {Object.entries(value).map(([key, entry]) => (
        <div key={key}>
          <dt>{title(key)}</dt>
          <dd>
            <Value value={entry} game={game} field={key} depth={depth + 1} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
