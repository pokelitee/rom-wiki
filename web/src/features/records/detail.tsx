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
import { StatBars } from "../../components/stat-bars";
import { TypeBadge } from "../../components/type-badge";
import { title } from "../../lib/utils";
import { Value } from "./value";
import { Evolutions, EvYields } from "./pokemon-sections";
import { Party } from "./trainer-sections";
import {
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
const SECTION_RENDERERS: Record<
  string,
  ComponentType<{ value: Json; game: string }>
> = {
  "pokemon.evolutions": Evolutions,
  "pokemon.ev_yields": EvYields,
  "trainers.party": Party,
};

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
  const sprite =
    object(record.sprite).url ?? object(record.reference).sprite_url;
  const features = new Set(
    (game.sections[section].metadata.features ?? []) as string[],
  );
  const entries = Object.entries(record).filter(
    ([key]) =>
      ![
        "name",
        "types",
        "base_stats",
        "reference",
        "version_variants",
        "reference_variants",
        "season_variants",
      ].includes(key) &&
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
  const facts = entries.filter(
    ([key, value]) =>
      !isTechnical(key) &&
      ((value !== null && typeof value !== "object") ||
        isNamedReference(value)),
  );
  const sections = orderEntries(
    section,
    entries.filter(
      ([key, value]) =>
        !isTechnical(key) &&
        value !== null &&
        typeof value === "object" &&
        !isNamedReference(value) &&
        !isEmpty(value) &&
        !hasNoEncounters(value),
    ),
  );
  return (
    <>
      <Link className="back-link" to={`/${game.id}/${section}`}>
        <ArrowLeft size={14} />
        All {title(section)}
      </Link>
      <div className="record-hero panel">
        {typeof sprite === "string" && (
          <img
            className="record-sprite"
            src={sprite}
            alt=""
            width={104}
            height={104}
          />
        )}
        <div>
          <p className="eyebrow">
            {title(section)} · {row.id}
          </p>
          <h1>{section === "types" ? title(row.label) : row.label}</h1>
          <div className="badge-list">
            {typeNames(record).map((name) => (
              <TypeBadge key={name} name={name} />
            ))}
          </div>
        </div>
      </div>
      <div className="variant-controls">
        {versions.length > 0 && (
          <label>
            Version
            <select
              value={version}
              onChange={(event) => update("version", event.target.value)}
            >
              <option value="">Shared record</option>
              {versions.map((value) => (
                <option key={value} value={value}>
                  {title(value)}
                </option>
              ))}
            </select>
          </label>
        )}
        {Object.keys(seasons).length > 0 && (
          <label>
            Season
            <select
              value={season}
              onChange={(event) => update("season", event.target.value)}
            >
              {Object.keys(seasons).map((value) => (
                <option key={value} value={value}>
                  {title(value)}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {(reference.flavor_text ||
        reference.short_effect ||
        reference.effect) && (
        <div className="reference-prose">
          <p>{String(reference.flavor_text ?? reference.short_effect ?? "")}</p>
          {reference.effect && <p>{String(reference.effect)}</p>}
          <small>
            {reference.source ? String(reference.source) : ""}
            {reference.flavor_text_source === "rom"
              ? " · Description decoded from ROM"
              : ""}
          </small>
        </div>
      )}
      {record.base_stats && (
        <section className="panel detail-section">
          <h2>Base stats</h2>
          <StatBars stats={object(record.base_stats)} />
        </section>
      )}
      {facts.length > 0 && (
        <section className="panel detail-section">
          <h2>Overview</h2>
          <Value value={Object.fromEntries(facts)} game={game.id} />
        </section>
      )}
      {sections.map(([key, value]) => {
        const Renderer = SECTION_RENDERERS[`${section}.${key}`];
        return (
          <section className="panel detail-section" key={key}>
            <h2>{title(key)}</h2>
            {Renderer ? (
              <Renderer value={value} game={game.id} />
            ) : (
              <Value value={value} game={game.id} field={key} />
            )}
          </section>
        );
      })}
      {Object.entries(detail.relationships)
        .filter(([, value]) => !isEmpty(value))
        .map(([key, value]) => (
          <section className="panel detail-section" key={key}>
            <h2>{title(key)}</h2>
            <Value value={value} game={game.id} field={key} />
          </section>
        ))}
      {section === "trainers" && (
        <TrainerFamilies game={game} record={record} metadata={metadata} />
      )}
      {record.cry && typeof object(record.cry).url === "string" && (
        <section className="panel detail-section">
          <h2>Cry</h2>
          <audio controls preload="none" src={String(object(record.cry).url)} />
          <small>{String(object(record.cry).source ?? "")}</small>
        </section>
      )}
      {Array.isArray(record.sprites) && record.sprites.length > 1 && (
        <section className="panel detail-section">
          <h2>Sprites</h2>
          <div className="sprite-gallery">
            {record.sprites.map((entry, index) => (
              <figure key={index}>
                <img
                  loading="lazy"
                  width={96}
                  height={96}
                  alt={String(object(entry).label ?? "Sprite")}
                  src={String(object(entry).url)}
                />
                <figcaption>{String(object(entry).label ?? "")}</figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}
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
    </>
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
                String(value)
              )}
            </dd>
          </div>
        );
      })}
    </dl>
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
