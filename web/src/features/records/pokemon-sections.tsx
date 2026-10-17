import { useState, type KeyboardEvent } from "react";
import { ArrowRight } from "lucide-react";
import { EntityLink } from "../../components/entity-link";
import { StatBars } from "../../components/stat-bars";
import { TypeBadge } from "../../components/type-badge";
import type { DataObject, Game, IndexRecord, Json } from "../../data/types";
import { useResource } from "../../data/use-resource";
import { object } from "../../lib/json";
import { title } from "../../lib/utils";
import { evolutionCondition } from "./evolution";
import { formatName, formatScalar } from "./fields";

export interface SectionProps {
  value: Json;
  game: Game;
  record: DataObject;
}

function names(value: Json): string[] {
  return (Array.isArray(value) ? value : []).flatMap((entry) => {
    const name = object(entry).name;
    return typeof name === "string" ? [name] : [];
  });
}

const STAT_LABELS: Record<string, string> = {
  hp: "HP",
  attack: "Attack",
  defense: "Defense",
  special_attack: "Sp. Atk",
  special_defense: "Sp. Def",
  speed: "Speed",
};

// Only the stats a Pokémon actually yields; most yield one or two.
function evYield(value: Json | undefined): string {
  return Object.entries(object(value))
    .filter(([, amount]) => Number(amount) > 0)
    .map(
      ([stat, amount]) =>
        `+${String(amount)} ${STAT_LABELS[stat] ?? title(stat)}`,
    )
    .join(", ");
}

function numberFact(field: string, value: Json | undefined): string {
  return typeof value === "number" ? formatScalar(field, value) : "";
}

export function PokemonSummary({
  record,
  reference,
  game,
}: {
  record: DataObject;
  reference: DataObject;
  game: Game;
}) {
  const abilities = (Array.isArray(record.abilities) ? record.abilities : [])
    .map(object)
    .filter((ability) => typeof ability.name === "string");
  const growth = object(record.growth_rate).name ?? record.growth_rate;
  const facts: [string, string][] = [
    ["Height", numberFact("height_dm", reference.height_dm)],
    ["Weight", numberFact("weight_hg", reference.weight_hg)],
    ["Gender", numberFact("gender_ratio", record.gender_ratio)],
    ["Catch rate", numberFact("catch_rate", record.catch_rate)],
    [
      "Growth rate",
      typeof growth === "string" ? formatScalar("growth_rate", growth) : "",
    ],
    [
      "Egg groups",
      [
        ...new Set(
          names(record.egg_groups).map((name) =>
            formatScalar("egg_group", name),
          ),
        ),
      ].join(", "),
    ],
    ["EV yield", evYield(record.ev_yields)],
  ];
  return (
    <div className="pokemon-summary">
      <section className="panel detail-section" id="section-profile">
        <h2>Profile</h2>
        {abilities.length > 0 && (
          <div className="summary-abilities">
            <span className="muted">Abilities</span>
            <span className="badge-list chip-list">
              {abilities.map((ability) =>
                typeof ability.slug === "string" ? (
                  <EntityLink
                    key={ability.slug}
                    game={game.id}
                    route={`abilities/${ability.slug}`}
                  >
                    {formatName(String(ability.name))}
                    {ability.is_hidden === true && (
                      <span className="hidden-tag">Hidden</span>
                    )}
                  </EntityLink>
                ) : (
                  <span key={String(ability.name)}>
                    {formatName(String(ability.name))}
                  </span>
                ),
              )}
            </span>
          </div>
        )}
        <dl className="fact-grid">
          {facts
            .filter(([, value]) => value)
            .map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
        </dl>
      </section>
      {record.base_stats !== undefined && (
        <section className="panel detail-section" id="section-base-stats">
          <h2>Base stats</h2>
          <StatBars stats={object(record.base_stats)} />
        </section>
      )}
    </div>
  );
}

export function Evolutions({ value, game }: SectionProps) {
  const evolutions = Array.isArray(value) ? value.map(object) : [];
  return (
    <ul className="evolution-list">
      {evolutions.map((evolution, index) => {
        const target = object(evolution.target);
        return (
          <li className="evolution-card" key={index}>
            <ArrowRight size={16} aria-hidden="true" />
            <div>
              {typeof target.slug === "string" ? (
                <EntityLink game={game.id} route={`pokemon/${target.slug}`}>
                  {formatName(String(target.name))}
                </EntityLink>
              ) : (
                <strong>{String(target.name ?? "Unknown")}</strong>
              )}
              <p className="evolution-condition">
                {evolutionCondition(evolution).map((part, partIndex) =>
                  typeof part === "string" ? (
                    part
                  ) : part.route ? (
                    <EntityLink
                      key={partIndex}
                      game={game.id}
                      route={part.route}
                    >
                      {part.name}
                    </EntityLink>
                  ) : (
                    <strong key={partIndex}>{part.name}</strong>
                  ),
                )}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

const MOVE_TABS: { field: string; label: string; lead?: string }[] = [
  { field: "level_up_moves", label: "Level up", lead: "Level" },
  { field: "machines", label: "TM/HM", lead: "Machine" },
  { field: "egg_moves", label: "Egg" },
  { field: "tutor_moves", label: "Tutor", lead: "Tutor" },
];

function moveRows(field: string, value: Json) {
  const entries = (Array.isArray(value) ? value : []).map(object);
  if (field === "egg_moves") return entries.map((move) => ({ lead: "", move }));
  return entries.map((entry) => {
    const location = object(entry.location).name ?? entry.location;
    return {
      lead:
        field === "level_up_moves"
          ? String(entry.level ?? "")
          : field === "machines"
            ? String(entry.name ?? "")
            : typeof location === "string"
              ? formatScalar("location", location)
              : "",
      move: object(entry.move),
    };
  });
}

// One panel for every way a Pokémon learns moves, with each move's battle
// data joined from the moves index.
export function MovesPanel({ value, game }: SectionProps) {
  const lists = object(value);
  const tabs = MOVE_TABS.filter((tab) => {
    const list = lists[tab.field];
    return Array.isArray(list) && list.length > 0;
  });
  const [active, setActive] = useState(tabs[0]?.field ?? "");
  const movesIndex = useResource<{ records: IndexRecord[] }>(
    game.sections.moves?.index,
  );
  const moveFields = new Map(
    (movesIndex.value?.records ?? []).map((record) => [
      record.id,
      record.fields,
    ]),
  );
  const tab = tabs.find((entry) => entry.field === active) ?? tabs[0];
  if (!tab) return null;
  const onKeyDown = (event: KeyboardEvent) => {
    const offset =
      event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!offset) return;
    const next = tabs[(tabs.indexOf(tab) + offset + tabs.length) % tabs.length];
    setActive(next.field);
    document.getElementById(`tab-${next.field}`)?.focus();
  };
  return (
    <>
      <div
        className="tab-list"
        role="tablist"
        aria-label="How it learns moves"
        onKeyDown={onKeyDown}
      >
        {tabs.map((entry) => (
          <button
            key={entry.field}
            type="button"
            role="tab"
            id={`tab-${entry.field}`}
            aria-selected={entry === tab}
            aria-controls={`panel-${entry.field}`}
            tabIndex={entry === tab ? 0 : -1}
            onClick={() => setActive(entry.field)}
          >
            {entry.label}
            <span className="tab-count">
              {(lists[entry.field] as Json[]).length}
            </span>
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`panel-${tab.field}`}
        aria-labelledby={`tab-${tab.field}`}
        className="table-scroll"
      >
        <table className="detail-table move-table">
          <thead>
            <tr>
              {tab.lead && <th>{tab.lead}</th>}
              <th>Move</th>
              <th>Type</th>
              <th>Category</th>
              <th>Power</th>
              <th>Accuracy</th>
              <th>PP</th>
            </tr>
          </thead>
          <tbody>
            {moveRows(tab.field, lists[tab.field]).map(
              ({ lead, move }, index) => {
                const slug =
                  typeof move.slug === "string" ? move.slug : undefined;
                const fields = slug ? moveFields.get(slug) : undefined;
                const first = (key: string) => {
                  const entry = fields?.[key];
                  return Array.isArray(entry) ? entry[0] : undefined;
                };
                const stat = (key: string) => {
                  const entry = fields?.[key];
                  return typeof entry === "number" && entry !== 0
                    ? String(entry)
                    : "—";
                };
                const type = first("type");
                const category = first("damage_class");
                return (
                  <tr key={index}>
                    {tab.lead && <td className="numeric">{lead}</td>}
                    <td>
                      {slug ? (
                        <EntityLink game={game.id} route={`moves/${slug}`}>
                          {formatName(String(move.name))}
                        </EntityLink>
                      ) : (
                        formatName(String(move.name ?? "—"))
                      )}
                    </td>
                    <td>{type ? <TypeBadge name={type} /> : "—"}</td>
                    <td>
                      {category ? formatScalar("damage_class", category) : "—"}
                    </td>
                    <td className="numeric">{stat("power")}</td>
                    <td className="numeric">{stat("accuracy")}</td>
                    <td className="numeric">{stat("pp")}</td>
                  </tr>
                );
              },
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
