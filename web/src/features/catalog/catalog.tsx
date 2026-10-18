import { Link, useSearchParams } from "react-router-dom";
import { useState } from "react";
import {
  ArrowDownWideNarrow,
  ArrowUpNarrowWide,
  ChevronLeft,
  ChevronRight,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { useResource } from "../../data/use-resource";
import type { Game, IndexRecord } from "../../data/types";
import { ResourceState } from "../../components/resource-state";
import { OptionSelect } from "../../components/option-select";
import { TypeBadge } from "../../components/type-badge";
import { Button } from "../../components/ui/button";
import { countLabel, title } from "../../lib/utils";
import { defaultSort, filterRecords, PAGE_SIZE, pageNumber } from "./filter";
import type { DataObject, RecordDetail } from "../../data/types";
import { object } from "../../lib/json";
import { recordContext, sharedLabels } from "../records/same-name";

const TYPE_FIELDS = new Set(["types", "type"]);

export function Catalog({ game, section }: { game: Game; section: string }) {
  const resource = useResource<{ records: IndexRecord[] }>(
    game.sections[section].index,
  );
  return (
    <ResourceState error={resource.error} retry={resource.retry}>
      {resource.value && (
        <>
          {section === "types" ? (
            <TypeGrid game={game} records={resource.value.records} />
          ) : (
            <CatalogTable
              game={game}
              section={section}
              records={resource.value.records}
            />
          )}
          {section === "types" && resource.value.records[0] && (
            <TypeChart game={game} chunk={resource.value.records[0].chunk} />
          )}
        </>
      )}
    </ResourceState>
  );
}

const MULTIPLIER_LABELS: Record<string, string> = { "1/2": "½", "1/4": "¼" };

// There are only 18 types, so they read better as tiles than as a table.
function TypeGrid({ game, records }: { game: Game; records: IndexRecord[] }) {
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Game reference</p>
          <h1>Types</h1>
        </div>
        <span className="count">{countLabel(records.length, "type")}</span>
      </div>
      <ul className="type-grid">
        {records.map((row) => (
          <li key={row.id}>
            <Link
              className="type-tile"
              data-type={row.label.toLowerCase()}
              to={`/${game.id}/types/${row.id}`}
            >
              <TypeBadge name={row.label} />
              <ChevronRight size={15} aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
    </>
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
                        <TypeBadge name={String(type.name)} />
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
                          {MULTIPLIER_LABELS[multiplier] ?? multiplier}×
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
  const hasRange = [...params.keys()].some(
    (key) => key.startsWith("min.") || key.startsWith("max."),
  );
  const [showRanges, setShowRanges] = useState(hasRange);
  const filtering = [...params.keys()].some(
    (key) => key !== "page" && key !== "sort" && key !== "dir",
  );
  const descending = params.get("dir") === "desc";
  const filtered = filterRecords(records, params, defaultSort(section));
  const page = pageNumber(params, filtered.length);
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const shared = sharedLabels(records);
  // A filter needs at least two values to choose between.
  const choices = categorical
    .map(
      (key) =>
        [
          key,
          [
            ...new Set(
              records.flatMap((row) => row.fields[key] ?? []).map(String),
            ),
          ].sort(),
        ] as const,
    )
    .filter(([, values]) => values.length > 1);
  const columns = fields
    .filter(
      (key) =>
        !["pokemon", "features", "egg_groups", "section_name"].includes(key),
    )
    .slice(0, 5);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Game reference</p>
          <h1>{title(section)}</h1>
        </div>
        <span className="count">{countLabel(records.length, "record")}</span>
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
        {choices.length > 0 && (
          <div className="filters">
            {choices.map(([key, values]) => (
              <OptionSelect
                key={key}
                label={title(key)}
                value={params.get(`f.${key}`) ?? ""}
                onChange={(value) => update(`f.${key}`, value)}
                options={[
                  { value: "", label: "All" },
                  ...values.map((value) => ({ value, label: title(value) })),
                ]}
              />
            ))}
          </div>
        )}
        {numeric.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="more-filters"
            aria-expanded={showRanges}
            onClick={() => setShowRanges((value) => !value)}
          >
            <SlidersHorizontal size={14} />
            {showRanges ? "Fewer filters" : "More filters"}
          </Button>
        )}
        {showRanges && (
          <div className="filters range-filters">
            {numeric.map((key) => (
              <fieldset className="range-filter" key={key}>
                <legend>{title(key)}</legend>
                <input
                  type="number"
                  inputMode="numeric"
                  aria-label={`Minimum ${title(key)}`}
                  placeholder="Min"
                  value={params.get(`min.${key}`) ?? ""}
                  onChange={(event) => update(`min.${key}`, event.target.value)}
                />
                <span aria-hidden="true">–</span>
                <input
                  type="number"
                  inputMode="numeric"
                  aria-label={`Maximum ${title(key)}`}
                  placeholder="Max"
                  value={params.get(`max.${key}`) ?? ""}
                  onChange={(event) => update(`max.${key}`, event.target.value)}
                />
              </fieldset>
            ))}
          </div>
        )}
      </div>
      <div className="results-line">
        <span>{countLabel(filtered.length, "result")}</span>
        <div className="results-actions">
          {filtering && (
            <Button variant="ghost" size="sm" onClick={() => setParams({})}>
              <X size={14} />
              Reset filters
            </Button>
          )}
          <OptionSelect
            className="sort-select"
            label="Sort by"
            value={params.get("sort") ?? defaultSort(section)}
            onChange={(value) => update("sort", value)}
            options={["name", ...numeric].map((key) => ({
              value: key,
              label: title(key),
            }))}
          />
          <Button
            variant="outline"
            size="icon"
            className="sort-direction"
            aria-label={descending ? "Sort ascending" : "Sort descending"}
            title={descending ? "Descending" : "Ascending"}
            onClick={() => update("dir", descending ? "asc" : "desc")}
          >
            {descending ? (
              <ArrowDownWideNarrow size={16} />
            ) : (
              <ArrowUpNarrowWide size={16} />
            )}
          </Button>
        </div>
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
                  <Link
                    className={row.sprite ? "catalog-name" : undefined}
                    to={`/${game.id}/${section}/${row.id}`}
                  >
                    {row.sprite && (
                      <img
                        src={row.sprite}
                        alt=""
                        width={40}
                        height={40}
                        loading="lazy"
                      />
                    )}
                    {row.label}
                  </Link>
                  {shared.has(row.label) && (
                    <span className="row-context">
                      {recordContext(section, row)}
                    </span>
                  )}
                </td>
                {columns.map((key) => (
                  <td key={key} data-label={title(key)}>
                    {Array.isArray(row.fields[key]) &&
                    (row.fields[key] as string[]).length ? (
                      (row.fields[key] as string[]).map((value) =>
                        TYPE_FIELDS.has(key) ? (
                          <TypeBadge name={value} key={value} />
                        ) : (
                          <span className="badge" key={value}>
                            {title(value)}
                          </span>
                        ),
                      )
                    ) : Array.isArray(row.fields[key]) ? (
                      <span className="muted">—</span>
                    ) : (
                      (row.fields[key] ?? "—")
                    )}
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
      {filtered.length > PAGE_SIZE && (
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
      )}
    </>
  );
}
