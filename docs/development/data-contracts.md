# Data contracts

Each site's `wiki/data/*.json.gz` downloads contain the complete normalized
datasets, including ROM facts, provenance, relationships, and PokéDB reference
objects. Comparison/diff data is not published there; it's changelog data, not
part of the dataset itself.

The in-memory `RelationshipIndex` is not a publication layer. It derives reverse
references for presentation from normalized datasets. Its encounter, acquisition,
trainer, learner, and location references are presentation-only views of facts
already present in public downloads.

Every dataset envelope contains a dataset name, game and engine identity, schema
version, top-level record count, source metadata, and its dataset-specific payload.
Published enriched datasets also carry a sorted `features` list. A feature means
the exact engine/profile combination supports that mechanic. Record-level emptiness
is separate: an empty list means the mechanic exists but this record has no entries.

Encounter and location envelopes also name the semantic shape of their records:
`wild_encounters` carries `encounter_format` (`conditional`, `seasonal`,
`method-table`, or `unsupported`) and `locations` carries `location_format`
(`event-map`, `encounter-map`, or `unsupported`). Both come from the engine
adapter's declared formats, so consumers select a record shape from the dataset
itself rather than resolving the engine that produced it.

## Compatibility

Schema constants live in `src/romwiki/schema/versions.py`. Increment the affected
raw or enriched schema whenever a serialized field changes meaning, shape, or
required presence. Do not invalidate unrelated datasets.

Local orchestration and publication-tooling formats keep their own version
constants beside their owning module instead of `schema/versions.py` — for
example `sites/snapshot.py`'s `DIRECTORY_SNAPSHOT_SCHEMA_VERSION`,
`sites/data_exports.py`'s
`PUBLIC_DATA_MANIFEST_SCHEMA_VERSION`, and
`pipeline/build/regeneration.py`'s `REGENERATION_STATE_SCHEMA_VERSION`. These
version an ignored local state file, snapshot archive, or manifest shape, not a
public dataset contract, so they change independently of the raw/enriched
schemas above. A version constant for an actual dataset field, shape, or
required presence belongs in `schema/versions.py` regardless of which module
emits it.

Enriched encounter schema 7 added `encounter_format` and renamed the marker on
the `special` object of areas whose walking slots vary by time of day:
`"format": "hgss"` became `"format": "direct-species"`, describing its shape
(special-condition species named directly rather than as walking-slot
replacements) instead of the engine family that introduced it. Consumers of
schema 6 archives that matched the old value should match the new one; the
object's other fields are unchanged. Published locations
previously used the raw locations schema version (15); they now have their own
enriched version, starting at 16 when `location_format` was added, so the
published number keeps increasing.

Sibling-version merging requires the same dataset kind, schema version, feature
contract, and semantic format on every side. Differing current records are retained only for
dataset kinds registered as supporting version variants.

## Public downloads

The data exporter serializes canonical compact UTF-8 JSON and writes deterministic
gzip archives. `data/manifest.json` lists every archive with its schema version,
record count, compressed byte size, and SHA-256 checksum. Snapshot validation
decompresses and parses each archive and verifies its checksum, so publication
cannot silently ship missing or corrupt data.

The archives never contain ROM or patch bytes. External reference fields remain
labeled as PokéDB-derived. When a profile declares a decoded ROM description
bank, its exact prose replaces only the reference object's `flavor_text` and is
labeled with `flavor_text_source = "rom"`; structured effects, sprites, and other
reference metadata remain PokéDB-derived. Exact mechanics and comparisons remain
ROM-derived.

The normalized `types` archive records the selected generation chart and its shared
chart family, attacking and defending type identities, exact multipliers, game
identity, source kind, and provenance. Profiles explicitly select an engine chart
or provide validated overrides, so the dataset never infers mechanics merely from
displayed type names.

Trainer data keeps prize money distinct from AI battle items and victory items.
Calculated base prize money is serialized only when all generation-specific inputs
are exact, and the stored multiplier retains its ROM provenance. Unsupported or
unresolved payouts are absent rather than represented by an estimate.

Location data keeps coordinate-bearing `items` (visible and hidden map events)
separate from `script_awarded_items`. A script award records item ID, quantity,
script member, command offset, and command identity; it has no invented map
coordinates. Reverse item relationships preserve the distinction through their
normalized `kind` value.

Trainer datasets also carry an independently versioned `battle_families` list
and `trainer_variant_support` capability map. A family is a relationship over
exact `trainer_id` records, never a replacement trainer. Every variant has a
stable order and one or more typed conditions (`starter-choice`,
`difficulty-mode`, `rematch-stage`, `story-stage`, `sibling-version`, or
`season`), while
every family records the source, reference, and verification of its selection
rule. Validation rejects dangling IDs, duplicate variants, duplicate ordering,
contradictory conditions, and missing provenance.

Resolvers see normalized records only. Selectors that live in the ROM image —
such as the DPPT Vs. Seeker rematch table — are decoded in the trainer pipeline,
which passes them to the resolver as `selector_data` and records their location
under `source`. Profiles own the offsets, so a hack that moves or rewrites a
selector declares its own without changing engine code.

Selector coverage is engine-wide rather than title- or axis-limited. Starter,
difficulty, version, season, rematch, story, and partner relationships may all be
published when their ROM selector is decoded. Records whose selector is unknown
stay unrelated rather than being grouped by names, adjacent IDs, levels, or party
similarity. Runtime selectors without a code or table anchor remain explicit
capability gaps rather than an excuse to publish inferred relationships.

The resolver never combines exact trainer records. All source slots, seasonal
records, weights, provenance, and `version_variants` stay intact in normalized
downloads and comparisons, and conditional encounter pools (Headbutt, Hidden
Grotto, Daily Swarm, Safari Zone) are never merged into ordinary wild slots.

`version_variants` describe different values stored in sibling ROM datasets.
Battle-family conditions describe runtime selection among trainer records. The
two axes are not interchangeable: sibling merging requires matching family
capabilities and rules, while exact trainer records remain the units compared and
indexed by Pokémon appearances, items, locations, and other backlinks.

Reference prose is presentation metadata rather than a mechanical record
difference. When sibling ROMs provide different effect or flavor text, merging
retains it under `reference_variants`.
Identical prose remains one shared reference object.

## React publication contract

The frontend contract is versioned independently by `FRONTEND_SCHEMA_VERSION`. The top-level manifest describes published games, section indexes and metadata resources, authored documents, comparison resources, and complete normalized downloads. Each section's manifest metadata includes `published_count`, the number of index entries; the dataset's `record_count` also counts placeholder records that are not published. Index entries contain a stable route ID, label, search fields, filter/sort fields, and a content-addressed detail chunk path; Pokémon entries also carry a `sprite` URL when one is known. Guides are titled by a frontmatter `title`, then their first level-one heading, then their file name, and each folder's `index` guide is listed first. Each chunk maps route IDs to an unchanged normalized record plus derived reverse relationships. Up to 50 records share a chunk; seasonal encounters share a route and retain each exact season record.

Frontend comparisons are separate presentation resources. They retain comparison statuses, changes, removed-record snapshots, and baseline identity, with a current detail route where available. Normalized downloads do not acquire comparison fields. Unsupported capabilities remain distinct from supported mechanics with no entries.

Frontend snapshot schema 1 pins the complete gzip archive and every resource checksum. Restoration validates the entire inventory and member checksums before writing files, then verifies all manifest references and downloadable archives. Resource filenames are content-addressed; stale unreferenced build resources are excluded from snapshots.
