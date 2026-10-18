import type { ComponentType } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import type {
  DataObject,
  Game,
  IndexRecord,
  Json,
  RecordDetail,
} from "../../data/types";
import { useResource } from "../../data/use-resource";
import { ResourceState } from "../../components/resource-state";
import { OptionSelect } from "../../components/option-select";
import { StatBars } from "../../components/stat-bars";
import { title } from "../../lib/utils";
import { Value } from "./value";
import { RecordHero } from "./record-hero";
import { TypeMatchups, TypeMoves, TypePokemon } from "./type-sections";
import { Warps } from "./location-sections";
import { recordContext } from "./same-name";
import { EntityLink } from "../../components/entity-link";
import {
  Evolutions,
  MovesPanel,
  PokemonSummary,
  WildEncounters,
  type SectionProps,
} from "./pokemon-sections";
import { Party } from "./trainer-sections";
import {
  coversAllVersions,
  fieldLabel,
  hasNoEncounters,
  isEmpty,
  isNamedReference,
  isTechnical,
  OPTIONAL_FEATURES,
  orderEntries,
} from "./fields";
import { object } from "../../lib/json";

export function Detail({
  game,
  section,
  id,
}: {
  game: Game;
  section: string;
  id: string;
}) {
  const resource = useResource<{ records: IndexRecord[] }>(
    game.sections[section].index,
  );
  const row = resource.value?.records.find((entry) => entry.id === id);
  return (
    <ResourceState error={resource.error} retry={resource.retry}>
      {resource.value &&
        (row ? (
          <DetailChunk
            key={`${section}/${id}`}
            game={game}
            section={section}
            row={row}
          />
        ) : (
          <div className="notice">
            <h1>Record not found</h1>
            <Link to={`/${game.id}/${section}`}>Browse {title(section)}</Link>
          </div>
        ))}
    </ResourceState>
  );
}

function DetailChunk({
  game,
  section,
  row,
}: {
  game: Game;
  section: string;
  row: IndexRecord;
}) {
  const resource = useResource<Record<string, RecordDetail>>(row.chunk);
  const detail = resource.value?.[row.id];
  return (
    <ResourceState error={resource.error} retry={resource.retry}>
      {resource.value &&
        (detail ? (
          <RecordPage game={game} section={section} row={row} detail={detail} />
        ) : (
          <p role="alert">This record is missing from the published data.</p>
        ))}
    </ResourceState>
  );
}

// Gen 4 and 5 store two type slots, repeating the type of a single-type
// Pokémon.
function typeNames(record: DataObject): string[] {
  const types = Array.isArray(record.types)
    ? record.types
    : record.type
      ? [record.type]
      : [];
  return [
    ...new Set(types.map((value) => String(object(value).name ?? value))),
  ];
}

// Sections whose generic rendering would hide what matters about them.
const SECTION_RENDERERS: Record<string, ComponentType<SectionProps>> = {
  "pokemon.evolutions": Evolutions,
  "pokemon.moves": MovesPanel,
  "trainers.party": Party,
  "types.matchups": TypeMatchups,
  "locations.warps": Warps,
  "pokemon.wild_encounters": WildEncounters,
};

// Pokémon facts shown in the summary rather than the overview.
const POKEMON_SUMMARY_FIELDS = [
  "abilities",
  "egg_groups",
  "gender_ratio",
  "catch_rate",
  "growth_rate",
  "ev_yields",
];
const POKEMON_MOVE_FIELDS = [
  "level_up_moves",
  "machines",
  "egg_moves",
  "tutor_moves",
];

// The four ways a Pokémon learns moves share one tabbed section, placed
// where the first of them would have been.
function combineMoves(entries: [string, Json][]): [string, Json][] {
  const moves = entries.filter(([key]) => POKEMON_MOVE_FIELDS.includes(key));
  if (!moves.length) return entries;
  const first = entries.indexOf(moves[0]);
  const rest = entries.filter(([key]) => !POKEMON_MOVE_FIELDS.includes(key));
  rest.splice(first, 0, ["moves", Object.fromEntries(moves)]);
  return rest;
}

function RecordPage({
  game,
  section,
  row,
  detail,
}: {
  game: Game;
  section: string;
  row: IndexRecord;
  detail: RecordDetail;
}) {
  const [params, setParams] = useSearchParams();
  const metadataResource = useResource<DataObject>(
    game.sections[section].metadata_path,
  );
  const metadata = metadataResource.value ?? game.sections[section].metadata;
  const base = detail.record;
  const variants = object(base.version_variants);
  const seasons = object(base.season_variants);
  const version = params.get("version") ?? "";
  const season = params.get("season") ?? Object.keys(seasons)[0] ?? "";
  const selected =
    version && variants[version]
      ? { ...base, ...object(variants[version]) }
      : base;
  const record = season && seasons[season] ? object(seasons[season]) : selected;
  const referenceVariants = object(base.reference_variants);
  const reference = object(
    version && version in referenceVariants
      ? referenceVariants[version]
      : record.reference,
  );
  const features = new Set(
    (game.sections[section].metadata.features ?? []) as string[],
  );
  const entries = Object.entries(record).filter(
    ([key, value]) =>
      ![
        "name",
        "types",
        "base_stats",
        "reference",
        "version_variants",
        "reference_variants",
        "season_variants",
      ].includes(key) &&
      !(key === "versions" && coversAllVersions(value, game.versions)) &&
      (!OPTIONAL_FEATURES[key] || features.has(OPTIONAL_FEATURES[key])),
  );
  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  };
  const versions = [
    ...new Set([...Object.keys(variants), ...Object.keys(referenceVariants)]),
  ];
  const summarized = section === "pokemon" ? POKEMON_SUMMARY_FIELDS : [];
  const facts = entries.filter(
    ([key, value]) =>
      !summarized.includes(key) &&
      !isTechnical(key) &&
      ((value !== null && typeof value !== "object") ||
        isNamedReference(value)),
  );
  const ordered = orderEntries(
    section,
    entries.filter(
      ([key, value]) =>
        !summarized.includes(key) &&
        !isTechnical(key) &&
        value !== null &&
        typeof value === "object" &&
        !isNamedReference(value) &&
        !isEmpty(value) &&
        !hasNoEncounters(value),
    ),
  );
  // A Pokémon's family tree replaces the evolutions leaving it, and also
  // gives final stages, which evolve into nothing, an evolutions section.
  const chain = section === "pokemon" && detail.relationships.evolution_chain;
  const sections =
    section === "pokemon"
      ? combineMoves(
          chain
            ? orderEntries(section, [
                ...ordered.filter(([key]) => key !== "evolutions"),
                ["evolutions", chain],
              ])
            : ordered,
        )
      : ordered;
  const relationships = Object.entries(detail.relationships).filter(
    ([key, value]) =>
      key !== "evolution_chain" &&
      // The record's own section already shows these, such as an
      // encounter area's locations.
      !sections.some(([name]) => name === key) &&
      !isEmpty(value),
  );
  const outline: [string, string][] = [
    ...(section === "pokemon"
      ? ([
          ["section-profile", "Profile"],
          ["section-base-stats", "Base stats"],
        ] as [string, string][])
      : []),
    ...(facts.length
      ? [["section-overview", "Overview"] as [string, string]]
      : []),
    ...[...sections, ...relationships].map(
      ([key]) => [`section-${key}`, title(key)] as [string, string],
    ),
    ...(section === "types"
      ? ([
          ["section-pokemon", "Pokémon"],
          ["section-moves", "Moves"],
        ] as [string, string][])
      : []),
  ];
  return (
    <div className="record-page">
      <Link className="back-link" to={`/${game.id}/${section}`}>
        <ArrowLeft size={14} />
        All {title(section)}
      </Link>
      <RecordHero
        eyebrow={`${title(section)} · ${row.id}`}
        label={section === "types" ? title(row.label) : row.label}
        record={record}
        reference={reference}
        types={typeNames(record)}
      />
      <div className="variant-controls">
        {versions.length > 0 && (
          <OptionSelect
            label="Version"
            value={version}
            onChange={(value) => update("version", value)}
            options={[
              { value: "", label: "Shared record" },
              ...versions.map((value) => ({ value, label: fieldLabel(value) })),
            ]}
          />
        )}
        {Object.keys(seasons).length > 0 && (
          <OptionSelect
            label="Season"
            value={season}
            onChange={(value) => update("season", value)}
            options={Object.keys(seasons).map((value) => ({
              value,
              label: title(value),
            }))}
          />
        )}
      </div>
      {outline.length >= 4 && (
        <nav className="record-nav" aria-label="On this page">
          {outline.map(([id, label]) => (
            <a
              key={id}
              href={`#${id}`}
              onClick={(event) => {
                event.preventDefault();
                document.getElementById(id)?.scrollIntoView();
              }}
            >
              {label}
            </a>
          ))}
        </nav>
      )}
      {section === "pokemon" ? (
        <PokemonSummary record={record} reference={reference} game={game} />
      ) : (
        record.base_stats && (
          <section className="panel detail-section" id="section-base-stats">
            <h2>Base stats</h2>
            <StatBars stats={object(record.base_stats)} />
          </section>
        )
      )}
      {facts.length > 0 && (
        <section className="panel detail-section" id="section-overview">
          <h2>Overview</h2>
          <Value value={Object.fromEntries(facts)} game={game.id} />
        </section>
      )}
      {sections.map(([key, value]) => {
        const Renderer = SECTION_RENDERERS[`${section}.${key}`];
        return (
          <section
            className="panel detail-section"
            key={key}
            id={`section-${key}`}
          >
            <h2>{title(key)}</h2>
            {Renderer ? (
              <Renderer value={value} game={game} record={record} />
            ) : (
              <Value
                value={value}
                game={game.id}
                field={key}
                encounters={section === "encounters"}
              />
            )}
          </section>
        );
      })}
      {relationships.map(([key, value]) => {
        const Renderer = SECTION_RENDERERS[`${section}.${key}`];
        return (
          <section
            className="panel detail-section"
            key={key}
            id={`section-${key}`}
          >
            <h2>{title(key)}</h2>
            {Renderer ? (
              <Renderer value={value} game={game} record={record} />
            ) : (
              <Value value={value} game={game.id} field={key} />
            )}
          </section>
        );
      })}
      {section === "types" && (
        <>
          <TypePokemon game={game} type={String(record.name)} />
          <TypeMoves game={game} type={String(record.name)} />
        </>
      )}
      {section === "trainers" && (
        <TrainerFamilies game={game} record={record} metadata={metadata} />
      )}
      <SameNameRecords
        game={game}
        section={section}
        row={row}
        exclude={
          section === "trainers"
            ? familyTrainerIds(metadata, record.trainer_id)
            : new Set()
        }
      />
      {Object.keys(reference).some(
        (key) =>
          ![
            "effect",
            "short_effect",
            "flavor_text",
            "source",
            "source_url",
            "version",
            "sprite_url",
            "flavor_text_source",
            "flavor_text_label",
          ].includes(key),
      ) && (
        <section className="panel detail-section">
          <h2>Reference information</h2>
          <Value
            value={Object.fromEntries(
              Object.entries(reference).filter(
                ([key]) =>
                  ![
                    "effect",
                    "short_effect",
                    "flavor_text",
                    "sprite_url",
                    // The description's own source line says these.
                    "flavor_text_source",
                    "flavor_text_label",
                    // The Pokémon summary already shows these.
                    ...(section === "pokemon"
                      ? ["height_dm", "weight_hg"]
                      : []),
                  ].includes(key),
              ),
            )}
            game={game.id}
          />
        </section>
      )}
      {metadataResource.error && (
        <ResourceState
          error={metadataResource.error}
          retry={metadataResource.retry}
        />
      )}
      <details className="panel detail-section">
        <summary>Sources and record details</summary>
        <RawFacts
          values={Object.fromEntries(
            entries.filter(([key]) => isTechnical(key)),
          )}
        />
        <RawFacts values={object(metadata.source)} />
        <details className="raw-record">
          <summary>Full record</summary>
          <pre>{JSON.stringify(base, null, 2)}</pre>
        </details>
        <Link to={`/${game.id}/docs/data-sources`}>
          Data sources and known limitations
        </Link>
      </details>
    </div>
  );
}

// Source details as stored, without the presentation rules that hide them
// from the main content.
function RawFacts({ values }: { values: DataObject }) {
  const keys = Object.keys(values);
  if (!keys.length) return null;
  return (
    <dl className="fact-list">
      {keys.map((key) => {
        const value = values[key];
        return (
          <div key={key}>
            <dt>{title(key)}</dt>
            <dd>
              {value !== null && typeof value === "object" ? (
                <pre>{JSON.stringify(value, null, 2)}</pre>
              ) : (
                String(value) || <span className="muted">—</span>
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

// Every trainer in the battle families that include this trainer; the
// Battle variants section already links those.
function familyTrainerIds(metadata: DataObject, trainerId: Json | undefined) {
  const ids = new Set<string>();
  const families = Array.isArray(metadata.battle_families)
    ? metadata.battle_families
    : [];
  const collect = (value: Json, into: Set<number>) => {
    if (Array.isArray(value)) value.forEach((entry) => collect(entry, into));
    else if (value && typeof value === "object") {
      if (typeof value.trainer_id === "number") into.add(value.trainer_id);
      Object.values(value).forEach((entry) => collect(entry, into));
    }
  };
  for (const family of families) {
    const members = new Set<number>();
    collect(family, members);
    if (typeof trainerId === "number" && members.has(trainerId))
      members.forEach((id) =>
        ids.add(`trainer-${String(id).padStart(4, "0")}`),
      );
  }
  return ids;
}

// Other records in this section that share the record's name, each with the
// detail that tells it apart.
function SameNameRecords({
  game,
  section,
  row,
  exclude,
}: {
  game: Game;
  section: string;
  row: IndexRecord;
  exclude: Set<string>;
}) {
  const index = useResource<{ records: IndexRecord[] }>(
    game.sections[section].index,
  );
  const others = (index.value?.records ?? []).filter(
    (other) =>
      other.label === row.label &&
      other.id !== row.id &&
      !exclude.has(other.id),
  );
  if (!others.length) return null;
  return (
    <section className="panel detail-section" id="section-same-name">
      <h2>Also named {row.label}</h2>
      <ul className="link-list">
        {others.map((other) => (
          <li key={other.id}>
            <EntityLink game={game.id} route={`${section}/${other.id}`}>
              {other.label}
            </EntityLink>
            <span className="row-context">{recordContext(section, other)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function TrainerFamilies({
  game,
  record,
  metadata,
}: {
  game: Game;
  record: DataObject;
  metadata: DataObject;
}) {
  const families = metadata.battle_families;
  if (!Array.isArray(families)) return null;
  const containsTrainer = (value: Json): boolean => {
    if (Array.isArray(value)) return value.some(containsTrainer);
    if (value && typeof value === "object")
      return (
        value.trainer_id === record.trainer_id ||
        Object.values(value).some(containsTrainer)
      );
    return false;
  };
  const matches = families.filter(containsTrainer);
  if (!matches.length) return null;
  return (
    <section className="panel detail-section">
      <h2>Battle variants</h2>
      {matches.map((family, index) => {
        const value = object(family);
        const variants = Array.isArray(value.variants) ? value.variants : [];
        return (
          <div className="battle-family" key={index}>
            <h3>{String(value.label ?? "Battle family")}</h3>
            {variants.map((variant, variantIndex) => {
              const entry = object(variant);
              const conditions = Array.isArray(entry.conditions)
                ? entry.conditions
                : [];
              const labels = conditions
                .map(object)
                .filter((condition) =>
                  [
                    "starter-choice",
                    "difficulty-mode",
                    "season",
                    "rematch-stage",
                    "sibling-version",
                  ].includes(String(condition.kind)),
                )
                .map((condition) => String(condition.label));
              return (
                <Link
                  className="battle-variant"
                  key={variantIndex}
                  to={`/${game.id}/trainers/trainer-${String(entry.trainer_id).padStart(4, "0")}`}
                >
                  {labels.join(" · ") || `Variant ${variantIndex + 1}`}
                  <span>Trainer {String(entry.trainer_id)}</span>
                </Link>
              );
            })}
            <details>
              <summary>Selection rule and source</summary>
              <Value value={value.provenance ?? null} game={game.id} />
            </details>
          </div>
        );
      })}
    </section>
  );
}
