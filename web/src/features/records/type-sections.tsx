import { Link } from "react-router-dom";
import type {
  DataObject,
  IndexRecord,
  Json,
  RecordDetail,
} from "../../data/types";
import { TypeBadge } from "../../components/type-badge";
import { useResource } from "../../data/use-resource";
import { object } from "../../lib/json";
import type { SectionProps } from "./pokemon-sections";

const GROUPS: { multiplier: string; label: string }[] = [
  { multiplier: "2", label: "2×" },
  { multiplier: "1/2", label: "½×" },
  { multiplier: "0", label: "0×" },
];

type Matchup = { attacker: string; defender: string; multiplier: string };

function matchups(attacker: string, value: Json | undefined): Matchup[] {
  return (Array.isArray(value) ? value : []).map((entry) => ({
    attacker,
    defender: String(object(entry).defending_type),
    multiplier: String(object(entry).multiplier),
  }));
}

function MatchupGroups({
  title,
  game,
  entries,
  pick,
}: {
  title: string;
  game: string;
  entries: Matchup[];
  pick: (entry: Matchup) => string;
}) {
  return (
    <div className="matchup-column">
      <h3>{title}</h3>
      <dl>
        {GROUPS.map(({ multiplier, label }) => {
          const types = entries.filter(
            (entry) => entry.multiplier === multiplier,
          );
          return (
            <div key={multiplier} data-multiplier={multiplier}>
              <dt>{label}</dt>
              <dd className="badge-list">
                {types.length ? (
                  types.map((entry) => (
                    <Link
                      key={pick(entry)}
                      to={`/${game}/types/${pick(entry)}`}
                    >
                      <TypeBadge name={pick(entry)} />
                    </Link>
                  ))
                ) : (
                  <span className="muted">None</span>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

// Damage this type deals, from its own record, and damage it takes, from
// every other type's record.
export function TypeMatchups({ value, game, record }: SectionProps) {
  const name = String(record.name);
  const index = useResource<{ records: IndexRecord[] }>(
    game.sections.types?.index,
  );
  const chunk = useResource<Record<string, RecordDetail>>(
    index.value?.records[0]?.chunk,
  );
  const defending = Object.values(chunk.value ?? {}).flatMap((detail) => {
    const attacker: DataObject = detail.record;
    return matchups(String(attacker.name), attacker.matchups).filter(
      (entry) => entry.defender === name,
    );
  });
  return (
    <div className="matchup-grid">
      <MatchupGroups
        title="Attacking"
        game={game.id}
        entries={matchups(name, value)}
        pick={(entry) => entry.defender}
      />
      {defending.length > 0 && (
        <MatchupGroups
          title="Defending"
          game={game.id}
          entries={defending}
          pick={(entry) => entry.attacker}
        />
      )}
    </div>
  );
}
