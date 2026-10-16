import { EntityLink } from "../../components/entity-link";
import type { DataObject, Json } from "../../data/types";
import { StatBars } from "../../components/stat-bars";
import { TypeBadge } from "../../components/type-badge";
import { object } from "../../lib/json";
import { title } from "../../lib/utils";
import { formatName, formatScalar } from "./fields";
import type { SectionProps } from "./pokemon-sections";

function RecordName({
  value,
  section,
  game,
}: {
  value: Json;
  section: string;
  game: string;
}) {
  const entity = object(value);
  if (typeof entity.name !== "string") return <span className="muted">—</span>;
  const name = formatName(entity.name);
  return typeof entity.slug === "string" ? (
    <EntityLink game={game} route={`${section}/${entity.slug}`}>
      {name}
    </EntityLink>
  ) : (
    <span>{name}</span>
  );
}

function uniqueTypes(value: Json): string[] {
  const types = Array.isArray(value) ? value : [];
  return [...new Set(types.map((type) => String(object(type).name)))];
}

// IVs and EVs are usually uniform for trainer Pokémon, so say so once.
function statSpread(value: Json): string {
  const values = Object.values(object(object(value).values)).map(Number);
  if (!values.length) return "Unknown";
  return values.every((entry) => entry === values[0])
    ? `${values[0]} in every stat`
    : Object.entries(object(object(value).values))
        .map(([stat, amount]) => `${title(stat)} ${String(amount)}`)
        .join(" · ");
}

function PartyCard({ member, game }: { member: DataObject; game: string }) {
  const pokemon = object(member.pokemon);
  const sprite = object(pokemon.sprite).url;
  const stats = object(object(member.calculated_stats).values);
  const highest = Math.max(
    ...Object.values(stats).map((value) =>
      Number(object(value).maximum ?? value),
    ),
  );
  const moves = Array.isArray(member.moves) ? member.moves.map(object) : [];
  return (
    <article className="party-card">
      <header>
        {typeof sprite === "string" && (
          <img src={sprite} alt="" width={64} height={64} loading="lazy" />
        )}
        <div>
          <h3>
            <RecordName value={member.pokemon} section="pokemon" game={game} />
          </h3>
          <p className="badge-list">
            <span className="badge">Level {String(member.level)}</span>
            {uniqueTypes(pokemon.types).map((type) => (
              <TypeBadge key={type} name={type} />
            ))}
          </p>
        </div>
      </header>
      <dl className="party-facts">
        <div>
          <dt>Ability</dt>
          <dd>
            <RecordName
              value={member.ability}
              section="abilities"
              game={game}
            />
          </dd>
        </div>
        <div>
          <dt>Held item</dt>
          <dd>
            <RecordName value={member.held_item} section="items" game={game} />
          </dd>
        </div>
        <div>
          <dt>Nature</dt>
          <dd>{String(object(member.nature).name ?? "Varies")}</dd>
        </div>
        <div>
          <dt>Gender</dt>
          <dd>{String(object(member.gender).name ?? "—")}</dd>
        </div>
      </dl>
      {moves.length > 0 && (
        <ul className="party-moves">
          {moves.map((move, index) => (
            <li key={index}>
              <RecordName value={move} section="moves" game={game} />
              {typeof object(move.type).name === "string" && (
                <TypeBadge name={String(object(move.type).name)} />
              )}
              <span className="muted">
                {formatScalar(
                  "damage_class",
                  String(object(move.damage_class).name ?? ""),
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {Object.keys(stats).length > 0 && (
        <StatBars stats={stats} max={Math.max(highest, 1)} />
      )}
      <details>
        <summary>Generated values</summary>
        <dl className="party-facts">
          <div>
            <dt>IVs</dt>
            <dd>{statSpread(member.ivs)}</dd>
          </div>
          <div>
            <dt>EVs</dt>
            <dd>{statSpread(member.evs)}</dd>
          </div>
        </dl>
      </details>
    </article>
  );
}

export function Party({ value, game }: SectionProps) {
  const members = Array.isArray(value) ? value.map(object) : [];
  return (
    <div className="party-grid">
      {members.map((member, index) => (
        <PartyCard key={index} member={member} game={game.id} />
      ))}
    </div>
  );
}
