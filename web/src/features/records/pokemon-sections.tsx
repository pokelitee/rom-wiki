import { useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { EntityLink } from "../../components/entity-link";
import { StatBars } from "../../components/stat-bars";
import { TypeBadge } from "../../components/type-badge";
import type { DataObject, Game, IndexRecord, Json } from "../../data/types";
import { useResource } from "../../data/use-resource";
import { useSprite } from "../../data/sprite-context";
import { object } from "../../lib/json";
import { title } from "../../lib/utils";
import { evolutionCondition } from "./evolution";
import { fieldLabel, formatName, formatScalar, tableScroll } from "./fields";
import { compactEncounters, type WildEncounter } from "./wild-encounters";
import { recordNumber } from "./same-name";

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

function Condition({
  evolution,
  game,
}: {
  evolution: DataObject;
  game: string;
}) {
  return (
    <span className="evolution-condition">
      {evolutionCondition(evolution).map((part, index) =>
        typeof part === "string" ? (
          part
        ) : part.route ? (
          <EntityLink key={index} game={game} route={part.route}>
            {part.name}
          </EntityLink>
        ) : (
          <strong key={index}>{part.name}</strong>
        ),
      )}
    </span>
  );
}

function Stage({
  node,
  game,
  current,
}: {
  node: DataObject;
  game: string;
  current: Json | undefined;
}) {
  const route = `pokemon/${String(node.slug)}`;
  const sprite = useSprite(route);
  const isCurrent = node.national_dex_id === current;
  // Branches read in Pokédex order, as Eevee's evolutions are usually listed.
  const steps = (Array.isArray(node.evolutions) ? node.evolutions : [])
    .map(object)
    .sort(
      (a, b) =>
        Number(object(a.target).national_dex_id) -
        Number(object(b.target).national_dex_id),
    );
  return (
    <div className="evolution-branch">
      <Link
        className="evolution-stage"
        to={`/${game}/${route}`}
        aria-current={isCurrent ? "page" : undefined}
      >
        {sprite && <img src={sprite} alt="" width={56} height={56} />}
        <span>{formatName(String(node.name))}</span>
      </Link>
      {steps.length > 0 && (
        <ul
          className={
            steps.length > 3 ? "evolution-steps is-many" : "evolution-steps"
          }
        >
          {steps.map((step, index) => (
            <li key={index}>
              <div className="evolution-step">
                <ArrowRight size={16} aria-hidden="true" />
                <Condition evolution={step} game={game} />
              </div>
              <Stage node={object(step.target)} game={game} current={current} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// The whole family, from its first stage through every branch, with this
// Pokémon marked. Records published without a family tree show only the
// evolutions leaving this Pokémon.
export function Evolutions({ value, game, record }: SectionProps) {
  const root = Array.isArray(value)
    ? {
        name: record.name ?? null,
        slug: record.slug ?? null,
        national_dex_id: record.national_dex_id ?? null,
        evolutions: value.map((evolution) => {
          const target = object(object(evolution).target);
          return {
            ...object(evolution),
            target: { ...target, national_dex_id: null },
          };
        }),
      }
    : object(value);
  return (
    <div className="evolution-tree">
      <Stage node={root} game={game.id} current={record.national_dex_id} />
    </div>
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
        className={tableScroll((lists[tab.field] as Json[]).length)}
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

// Where this Pokémon appears in the wild, one row per distinct encounter,
// grouped by area.
export function WildEncounters({ value, game }: SectionProps) {
  const rows = compactEncounters(
    (Array.isArray(value) ? value : []).map(object),
    game.versions,
  ).sort(
    (a, b) =>
      a.area.localeCompare(b.area, undefined, { numeric: true }) ||
      String(a.route).localeCompare(String(b.route)) ||
      a.method.localeCompare(b.method) ||
      (b.chance ?? 0) - (a.chance ?? 0),
  );
  const areas: WildEncounter[][] = [];
  for (const row of rows) {
    const last = areas.at(-1);
    if (last && last[0].route === row.route && last[0].area === row.area)
      last.push(row);
    else areas.push([row]);
  }
  const shared = new Set(
    areas
      .map((group) => group[0].area)
      .filter((area, index, all) => all.indexOf(area) !== index),
  );
  const showWhen = rows.some((row) => row.when.length);
  const showVersions = rows.some((row) => row.versions.length);
  return (
    <div className={tableScroll(rows.length)}>
      <table className="detail-table grouped-slot-table">
        <thead>
          <tr>
            <th>Area</th>
            <th>Method</th>
            <th>Level</th>
            <th>Chance</th>
            {showWhen && <th>When</th>}
            {showVersions && <th>Versions</th>}
          </tr>
        </thead>
        {areas.map((group) => (
          <tbody key={`${group[0].route}/${group[0].area}`}>
            {group.map((row, index) => (
              <tr key={index}>
                {index === 0 && (
                  <th scope="rowgroup" rowSpan={group.length}>
                    {row.route ? (
                      <EntityLink
                        game={game.id}
                        route={`encounters/${row.route}`}
                      >
                        {row.area}
                      </EntityLink>
                    ) : (
                      row.area
                    )}
                    {row.route && shared.has(row.area) && (
                      <span className="row-context">
                        {recordNumber(row.route)}
                      </span>
                    )}
                  </th>
                )}
                <td>{row.method}</td>
                <td className="numeric">{row.levels}</td>
                <td className="numeric">
                  {row.chance === null ? "—" : `${row.chance}%`}
                </td>
                {showWhen && <td>{row.when.join(" · ") || "Always"}</td>}
                {showVersions && (
                  <td>
                    {row.versions.length
                      ? row.versions.map(fieldLabel).join(", ")
                      : game.versions.length === 2
                        ? "Both"
                        : "All"}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
