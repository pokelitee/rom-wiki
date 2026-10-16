import type { DataObject, Json } from "../data/types";
import { title } from "../lib/utils";

const STAT_ORDER = [
  "hp",
  "attack",
  "defense",
  "special_attack",
  "special_defense",
  "speed",
];

// A stat is a number, or a range when the game picks it at runtime.
function bounds(value: Json): [number, number] {
  if (value && typeof value === "object" && !Array.isArray(value))
    return [Number(value.minimum), Number(value.maximum)];
  return [Number(value), Number(value)];
}

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
  const totals = names
    .map((name) => bounds(stats[name]))
    .reduce(([low, high], [min, max]) => [low + min, high + max], [0, 0]);
  const range = ([low, high]: [number, number]) =>
    low === high ? String(low) : `${low}–${high}`;
  return (
    <div className="stat-bars">
      {names.map((name) => {
        const [low, high] = bounds(stats[name]);
        return (
          <div className="stat-row" key={name}>
            <span>{title(name)}</span>
            <strong>{range([low, high])}</strong>
            <div className="stat-track">
              <div style={{ width: `${Math.min(100, (high / max) * 100)}%` }} />
            </div>
          </div>
        );
      })}
      <div className="stat-total">
        Total <strong>{range(totals as [number, number])}</strong>
      </div>
    </div>
  );
}
