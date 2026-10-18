import { Link } from "react-router-dom";
import type {
  DataObject,
  Game,
  IndexRecord,
  Json,
  RecordDetail,
} from "../../data/types";
import { EntityLink } from "../../components/entity-link";
import { TypeBadge } from "../../components/type-badge";
import { useResource } from "../../data/use-resource";
import { object } from "../../lib/json";
import type { SectionProps } from "./pokemon-sections";
import { formatScalar, tableScroll } from "./fields";

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

// Every Pokémon with this type in either slot, in Pokédex order, read from
// the Pokémon index since type records do not list their Pokémon.
export function TypePokemon({ game, type }: { game: Game; type: string }) {
  const index = useResource<{ records: IndexRecord[] }>(
    game.sections.pokemon?.index,
  );
  const members = (index.value?.records ?? [])
    .filter(
      (row) =>
        Array.isArray(row.fields.types) && row.fields.types.includes(type),
    )
    .sort(
      (a, b) =>
        Number(a.fields.national_dex_id) - Number(b.fields.national_dex_id),
    );
  if (!members.length) return null;
  return (
    <section className="panel detail-section" id="section-pokemon">
      <h2>Pokémon</h2>
      <span className="badge-list chip-list">
        {members.map((row) => (
          <EntityLink key={row.id} game={game.id} route={`pokemon/${row.id}`}>
            {row.label}
          </EntityLink>
        ))}
      </span>
    </section>
  );
}

// Every move of this type, read from the moves index like the Pokémon above.
export function TypeMoves({ game, type }: { game: Game; type: string }) {
  const index = useResource<{ records: IndexRecord[] }>(
    game.sections.moves?.index,
  );
  const moves = (index.value?.records ?? [])
    .filter(
      (row) => Array.isArray(row.fields.type) && row.fields.type.includes(type),
    )
    .sort((a, b) => a.label.localeCompare(b.label));
  if (!moves.length) return null;
  const stat = (value: Json | undefined) =>
    typeof value === "number" && value > 0 ? value : "—";
  return (
    <section className="panel detail-section" id="section-moves">
      <h2>Moves</h2>
      <div className={tableScroll(moves.length)}>
        <table className="detail-table">
          <thead>
            <tr>
              <th>Move</th>
              <th>Category</th>
              <th>Power</th>
              <th>Accuracy</th>
              <th>PP</th>
            </tr>
          </thead>
          <tbody>
            {moves.map((row) => {
              const category = Array.isArray(row.fields.damage_class)
                ? row.fields.damage_class[0]
                : row.fields.damage_class;
              return (
                <tr key={row.id}>
                  <td>
                    <EntityLink game={game.id} route={`moves/${row.id}`}>
                      {row.label}
                    </EntityLink>
                  </td>
                  <td>
                    {typeof category === "string"
                      ? formatScalar("damage_class", category)
                      : "—"}
                  </td>
                  <td className="numeric">{stat(row.fields.power)}</td>
                  <td className="numeric">{stat(row.fields.accuracy)}</td>
                  <td className="numeric">{stat(row.fields.pp)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
