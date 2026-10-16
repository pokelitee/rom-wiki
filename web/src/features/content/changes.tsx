import { Link, useSearchParams } from "react-router-dom";
import type { Comparison, DataObject, Game } from "../../data/types";
import { useResource } from "../../data/use-resource";
import { ResourceState } from "../../components/resource-state";
import { OptionSelect } from "../../components/option-select";
import { title } from "../../lib/utils";
import { Value } from "../records/value";
import { CHANGE_STATUSES, changeSummary } from "./change-summary";

export function Changes({ game }: { game: Game }) {
  const [params, setParams] = useSearchParams();
  const kind = params.get("section") ?? Object.keys(game.comparisons)[0];
  const status = params.get("status") ?? "";
  const resource = useResource<Comparison>(game.comparisons[kind]);
  return (
    <>
      <p className="eyebrow">Compared with the base game</p>
      <h1>Changes</h1>
      <div className="filter-row">
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
        <OptionSelect
          label="Show"
          value={status}
          onChange={(value) =>
            setParams({ section: kind, ...(value && { status: value }) })
          }
          options={[
            { value: "", label: "All changes" },
            ...CHANGE_STATUSES.map((value) => ({
              value,
              label: title(value),
            })),
          ]}
        />
      </div>
      <ResourceState error={resource.error} retry={resource.retry}>
        {resource.value && (
          <ChangeRecords
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
  const records = comparison.records.filter((record) =>
    status ? record.status === status : record.status !== "unchanged",
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
            <span className="badge">{title(String(record.status))}</span>
            {String(record.label ?? record.key)}
            {record.status === "changed" && (
              <span className="change-summary">{changeSummary(record)}</span>
            )}
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
