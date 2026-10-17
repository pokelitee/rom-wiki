import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search } from "lucide-react";
import type { Comparison, DataObject, Game, Json } from "../../data/types";
import { useResource } from "../../data/use-resource";
import { ResourceState } from "../../components/resource-state";
import { OptionSelect } from "../../components/option-select";
import { EntityLink } from "../../components/entity-link";
import { Button } from "../../components/ui/button";
import { object } from "../../lib/json";
import { countLabel, title } from "../../lib/utils";
import { Value } from "../records/value";
import { CHANGE_STATUSES, changeSummary } from "./change-summary";

const PAGE_SIZE = 50;

export function Changes({ game }: { game: Game }) {
  const [params, setParams] = useSearchParams();
  const kind = params.get("section") ?? Object.keys(game.comparisons)[0];
  const status = params.get("status") ?? "";
  const resource = useResource<Comparison>(game.comparisons[kind]);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Compared with the base game</p>
          <h1>Changes</h1>
        </div>
      </div>
      <div className="panel filter-panel change-controls">
        <OptionSelect
          label="Section"
          value={kind}
          onChange={(value) =>
            setParams({ section: value, ...(status && { status }) })
          }
          options={Object.keys(game.comparisons).map((value) => ({
            value,
            label: title(value),
          }))}
        />
        {resource.value && (
          <div className="status-filter" role="group" aria-label="Show changes">
            {["", ...CHANGE_STATUSES].map((value) => {
              const count = value
                ? (resource.value?.counts[value] ?? 0)
                : CHANGE_STATUSES.reduce(
                    (total, key) => total + (resource.value?.counts[key] ?? 0),
                    0,
                  );
              if (value && !count) return null;
              return (
                <button
                  key={value}
                  type="button"
                  data-status={value || undefined}
                  aria-pressed={status === value}
                  onClick={() =>
                    setParams({
                      section: kind,
                      ...(value && { status: value }),
                    })
                  }
                >
                  {value ? title(value) : "All changes"}
                  <span className="tab-count">{count}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
      <ResourceState error={resource.error} retry={resource.retry}>
        {resource.value && (
          <ChangeRecords
            key={`${kind}-${status}`}
            game={game}
            kind={kind}
            status={status}
            comparison={resource.value}
          />
        )}
      </ResourceState>
    </>
  );
}

// Each changed field with its value in the base game and in this game.
function FieldChanges({ record, game }: { record: DataObject; game: string }) {
  const changes = Array.isArray(record.changes)
    ? record.changes.map(object)
    : [];
  return (
    <div className="table-scroll">
      <table className="detail-table change-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Base game</th>
            <th>This game</th>
          </tr>
        </thead>
        <tbody>
          {changes.map((change, index) => (
            <tr key={index}>
              <th scope="row">
                {String(change.label ?? title(String(change.field ?? "")))}
              </th>
              <td>
                <Value
                  value={(change.before ?? null) as Json}
                  game={game}
                  field={String(change.field ?? "")}
                />
              </td>
              <td>
                <Value
                  value={(change.after ?? null) as Json}
                  game={game}
                  field={String(change.field ?? "")}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChangeRecords({
  game,
  kind,
  status,
  comparison,
}: {
  game: Game;
  kind: string;
  status: string;
  comparison: Comparison;
}) {
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(PAGE_SIZE);
  const needle = query.trim().toLowerCase();
  const records = comparison.records.filter(
    (record) =>
      (status ? record.status === status : record.status !== "unchanged") &&
      String(record.label ?? record.key)
        .toLowerCase()
        .includes(needle),
  );
  return (
    <>
      <div className="results-line">
        <span>
          {countLabel(records.length, "record")} · compared with{" "}
          {comparison.baseline}
        </span>
        <label className="search-field compact">
          <Search size={15} />
          <span className="sr-only">Filter by name</span>
          <input
            type="search"
            placeholder="Filter by name"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setShown(PAGE_SIZE);
            }}
          />
        </label>
      </div>
      {records.length > 0 ? (
        <div className="panel change-list">
          {records.slice(0, shown).map((record, index) => {
            const label = String(record.label ?? record.key);
            const route =
              typeof record.route === "string" && record.status !== "removed"
                ? `${kind}/${record.route}`
                : undefined;
            const summary = (
              <>
                <span
                  className="badge status-badge"
                  data-status={String(record.status)}
                >
                  {title(String(record.status))}
                </span>
                <span className="change-name">
                  {route ? (
                    <EntityLink game={game.id} route={route}>
                      {label}
                    </EntityLink>
                  ) : (
                    label
                  )}
                </span>
                {record.status === "changed" && (
                  <span className="change-summary">
                    {changeSummary(record)}
                  </span>
                )}
              </>
            );
            // Added records have nothing to compare; their page has the rest.
            if (record.status === "added")
              return (
                <div className="change-record" key={index}>
                  <div className="change-row">{summary}</div>
                </div>
              );
            return (
              <details className="change-record" key={index}>
                <summary className="change-row">{summary}</summary>
                {record.status === "changed" ? (
                  <FieldChanges record={record} game={game.id} />
                ) : (
                  <Value
                    value={object(record.baseline_record)}
                    game={game.id}
                  />
                )}
              </details>
            );
          })}
        </div>
      ) : (
        <p className="empty-state">No changes match.</p>
      )}
      {records.length > shown && (
        <div className="pagination">
          <Button
            variant="outline"
            onClick={() => setShown((value) => value + PAGE_SIZE)}
          >
            Show more ({records.length - shown} left)
          </Button>
        </div>
      )}
    </>
  );
}
