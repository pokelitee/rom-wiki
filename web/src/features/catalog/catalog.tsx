import { Link, useSearchParams } from "react-router-dom";
import { ArrowDownUp, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useResource } from "../../data/use-resource";
import type { Game, IndexRecord } from "../../data/types";
import { ResourceState } from "../../components/resource-state";
import { Button } from "../../components/ui/button";
import { title } from "../../lib/utils";
import { filterRecords, PAGE_SIZE, pageNumber } from "./filter";
import type { DataObject, RecordDetail } from "../../data/types";
import { object } from "../../lib/json";

export function Catalog({ game, section }: { game: Game; section: string }) {
  const resource = useResource<{ records: IndexRecord[] }>(
    game.sections[section].index,
  );
  return (
    <ResourceState error={resource.error} retry={resource.retry}>
      {resource.value && (
        <>
          <CatalogTable
            game={game}
            section={section}
            records={resource.value.records}
          />
          {section === "types" && resource.value.records[0] && (
            <TypeChart game={game} chunk={resource.value.records[0].chunk} />
          )}
        </>
      )}
    </ResourceState>
  );
}

function TypeChart({ game, chunk }: { game: Game; chunk: string }) {
  const resource = useResource<Record<string, RecordDetail>>(chunk);
  const types = Object.values(resource.value ?? {}).map(
    (detail) => detail.record,
  );
  return (
    <ResourceState error={resource.error} retry={resource.retry}>
      {resource.value && (
        <section className="panel detail-section">
          <h2>Type effectiveness</h2>
          <p className="muted">
            Attacking types are rows; defending types are columns. Values are
            exact damage multipliers.
          </p>
          <div className="table-scroll">
            <table className="type-chart">
              <thead>
                <tr>
                  <th scope="col">Attack / Defend</th>
                  {types.map((type) => (
                    <th scope="col" key={String(type.name)}>
                      {title(String(type.name))}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {types.map((type) => (
                  <tr key={String(type.name)}>
                    <th scope="row">
                      <Link to={`/${game.id}/types/${type.name}`}>
                        {title(String(type.name))}
                      </Link>
                    </th>
                    {types.map((defender) => {
                      const matchup = (type.matchups as DataObject[]).find(
                        (entry) =>
                          object(entry).defending_type === defender.name,
                      );
                      const multiplier = String(matchup?.multiplier ?? "—");
                      return (
                        <td
                          key={String(defender.name)}
                          className={`effectiveness-${multiplier.replace("/", "-")}`}
                        >
                          {multiplier}×
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </ResourceState>
  );
}

function CatalogTable({
  game,
  section,
  records,
}: {
  game: Game;
  section: string;
  records: IndexRecord[];
}) {
  const [params, setParams] = useSearchParams();
  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next, { replace: key === "q" });
  };
  const fields = [
    ...new Set(records.flatMap((record) => Object.keys(record.fields))),
  ].filter((key) => !["name", "id"].includes(key));
  const categorical = fields.filter((key) =>
    records.some((row) => Array.isArray(row.fields[key])),
  );
  const numeric = fields.filter((key) =>
    records.some((row) => typeof row.fields[key] === "number"),
  );
  const filtered = filterRecords(records, params);
  const page = pageNumber(params, filtered.length);
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const columns = fields
    .filter((key) => !["pokemon", "features", "egg_groups"].includes(key))
    .slice(0, 5);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Game reference</p>
          <h1>{title(section)}</h1>
        </div>
        <span className="count">{records.length.toLocaleString()} records</span>
      </div>
      <div className="panel filter-panel">
        <label className="search-field">
          <Search size={18} />
          <span className="sr-only">Search {section}</span>
          <input
            placeholder={`Search ${title(section).toLowerCase()}…`}
            value={params.get("q") ?? ""}
            onChange={(event) => update("q", event.target.value)}
          />
        </label>
        <div className="filters">
          {categorical.map((key) => {
            const values = [
              ...new Set(
                records.flatMap((row) => row.fields[key] ?? []).map(String),
              ),
            ].sort();
            if (values.length < 2) return null;
            return (
              <label key={key}>
                {title(key)}
                <select
                  value={params.get(`f.${key}`) ?? ""}
                  onChange={(event) => update(`f.${key}`, event.target.value)}
                >
                  <option value="">All</option>
                  {values.map((value) => (
                    <option key={value} value={value}>
                      {title(value)}
                    </option>
                  ))}
                </select>
              </label>
            );
          })}
        </div>
        <details className="advanced-filters">
          <summary>Ranges and sorting</summary>
          <div className="filters">
            {numeric.map((key) => (
              <div className="range-filter" key={key}>
                <span>{title(key)}</span>
                <label>
                  <span className="sr-only">Minimum {title(key)}</span>
                  <input
                    type="number"
                    placeholder="Min"
                    value={params.get(`min.${key}`) ?? ""}
                    onChange={(event) =>
                      update(`min.${key}`, event.target.value)
                    }
                  />
                </label>
                <label>
                  <span className="sr-only">Maximum {title(key)}</span>
                  <input
                    type="number"
                    placeholder="Max"
                    value={params.get(`max.${key}`) ?? ""}
                    onChange={(event) =>
                      update(`max.${key}`, event.target.value)
                    }
                  />
                </label>
              </div>
            ))}
            <label>
              Sort by
              <select
                value={params.get("sort") ?? "name"}
                onChange={(event) => update("sort", event.target.value)}
              >
                {["name", "id", ...numeric].map((key) => (
                  <option key={key} value={key}>
                    {title(key)}
                  </option>
                ))}
              </select>
            </label>
            <Button
              variant="outline"
              onClick={() =>
                update("dir", params.get("dir") === "desc" ? "asc" : "desc")
              }
            >
              <ArrowDownUp size={14} />
              {params.get("dir") === "desc" ? "Descending" : "Ascending"}
            </Button>
          </div>
        </details>
      </div>
      <div className="results-line">
        <span>{filtered.length.toLocaleString()} results</span>
        <Button variant="ghost" size="sm" onClick={() => setParams({})}>
          Reset filters
        </Button>
      </div>
      <div className="panel table-scroll">
        <table className="catalog-table">
          <thead>
            <tr>
              <th>Name</th>
              {columns.map((key) => (
                <th key={key}>{title(key)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link to={`/${game.id}/${section}/${row.id}`}>
                    {row.label}
                  </Link>
                  <small>{row.id}</small>
                </td>
                {columns.map((key) => (
                  <td key={key}>
                    {Array.isArray(row.fields[key])
                      ? (row.fields[key] as string[]).map((value) => (
                          <span className={`badge type-${value}`} key={value}>
                            {title(value)}
                          </span>
                        ))
                      : (row.fields[key] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {!visible.length && (
          <p className="empty-state">No records match these filters.</p>
        )}
      </div>
      <div className="pagination">
        <Button
          variant="outline"
          disabled={page <= 1}
          onClick={() => update("page", String(page - 1))}
        >
          <ChevronLeft size={15} />
          Previous
        </Button>
        <span>
          Page {page} of {Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))}
        </span>
        <Button
          variant="outline"
          disabled={page * PAGE_SIZE >= filtered.length}
          onClick={() => update("page", String(page + 1))}
        >
          Next
          <ChevronRight size={15} />
        </Button>
      </div>
    </>
  );
}
