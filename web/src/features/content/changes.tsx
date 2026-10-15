import { Link, useSearchParams } from "react-router-dom";
import type { Comparison, DataObject, Game } from "../../data/types";
import { useResource } from "../../data/use-resource";
import { ResourceState } from "../../components/resource-state";
import { title } from "../../lib/utils";
import { Value } from "../records/value";

export function Changes({ game }: { game: Game }) {
  const [params, setParams] = useSearchParams();
  const kind = params.get("section") ?? Object.keys(game.comparisons)[0];
  const resource = useResource<Comparison>(game.comparisons[kind]);
  return (
    <>
      <p className="eyebrow">Compared with the base game</p>
      <h1>Changes</h1>
      <label className="section-select">
        Section
        <select
          value={kind}
          onChange={(event) => setParams({ section: event.target.value })}
        >
          {Object.keys(game.comparisons).map((value) => (
            <option key={value} value={value}>
              {title(value)}
            </option>
          ))}
        </select>
      </label>
      <ResourceState error={resource.error} retry={resource.retry}>
        {resource.value && (
          <ChangeRecords game={game} kind={kind} comparison={resource.value} />
        )}
      </ResourceState>
    </>
  );
}

function ChangeRecords({
  game,
  kind,
  comparison,
}: {
  game: Game;
  kind: string;
  comparison: Comparison;
}) {
  const records = comparison.records.filter(
    (record) => record.status !== "unchanged",
  );
  return (
    <>
      <p className="muted">Baseline: {comparison.baseline}</p>
      <div className="summary-grid">
        {Object.entries(comparison.counts).map(([key, value]) => (
          <div className="panel summary-card" key={key}>
            <strong>{value}</strong>
            <span>{title(key)}</span>
          </div>
        ))}
      </div>
      {records.map((record, index) => (
        <details className="panel change-record" key={index}>
          <summary>
            <span className="badge">{String(record.status)}</span>
            {String(record.label ?? record.key)}
          </summary>
          {record.route && record.status !== "removed" && (
            <Link to={`/${game.id}/${kind}/${record.route}`}>Open record</Link>
          )}
          <Value
            value={
              (record.status === "removed"
                ? record.baseline_record
                : (record.changes ?? record)) as DataObject
            }
            game={game.id}
          />
        </details>
      ))}
      {!records.length && (
        <p className="empty-state">No changes in this section.</p>
      )}
    </>
  );
}
