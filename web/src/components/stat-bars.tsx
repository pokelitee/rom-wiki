import type { DataObject } from "../data/types";
import { title } from "../lib/utils";

const STAT_ORDER = [
  "hp",
  "attack",
  "defense",
  "special_attack",
  "special_defense",
  "speed",
];

// Stats in the order the games list them, on one shared scale.
export function StatBars({
  stats,
  max = 255,
}: {
  stats: DataObject;
  max?: number;
}) {
  const names = [
    ...STAT_ORDER.filter((name) => name in stats),
    ...Object.keys(stats).filter((name) => !STAT_ORDER.includes(name)),
  ];
  const total = names.reduce((sum, name) => sum + Number(stats[name]), 0);
  return (
    <div className="stat-bars">
      {names.map((name) => (
        <div className="stat-row" key={name}>
          <span>{title(name)}</span>
          <strong>{String(stats[name])}</strong>
          <div className="stat-track">
            <div
              style={{
                width: `${Math.min(100, (Number(stats[name]) / max) * 100)}%`,
              }}
            />
          </div>
        </div>
      ))}
      <div className="stat-total">
        Total <strong>{total}</strong>
      </div>
    </div>
  );
}
