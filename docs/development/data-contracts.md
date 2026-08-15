# Data contracts

ROM Wiki has three publication layers with different responsibilities:

- Detail Markdown is curated for people. It presents every supported mechanic
  that is useful on the page, but does not mirror normalized JSON field-for-field.
- `catalog.json` is a compact, versioned presentation index used by the local
  filters and static fallback. It is not a bulk-data API.
- `data/*.json.gz` contains the complete normalized datasets used by renderers,
  including ROM facts, provenance, relationships, and PokéDB reference objects.
  Comparative sites also publish `data/comparisons/*.json.gz`.

The in-memory `RelationshipIndex` is not a fourth publication layer. It derives
reverse references needed by pages and catalogs from normalized datasets once per
build. Its encounter, acquisition, trainer, learner, and location references are
presentation-only views of facts already present in public downloads.

Every dataset envelope contains a dataset name, game and engine identity, schema
version, top-level record count, source metadata, and its dataset-specific payload.
Published enriched datasets also carry a sorted `features` list. A feature means
the exact engine/profile combination supports that mechanic. Record-level emptiness
is separate: an empty list means the mechanic exists but this record has no entries.

## Compatibility

Schema constants live in `src/romwiki/schema/versions.py`. Increment the affected
raw or enriched schema whenever a serialized field changes meaning, shape, or
required presence. Do not invalidate unrelated datasets.

Sibling-version merging requires the same dataset kind, schema version, and
feature contract on every side. Differing current records are retained only for
dataset kinds whose renderers explicitly support version variants.

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

The public renderer names only Starter, Difficulty, Season, Rematch, and Version.
Story-stage-only and other neutral relationships render as `Variant N`. The
resolver and renderer never combine exact trainer records. Encounter row
aggregation and canonical seasonal pages are likewise presentation-only: all
source slots, seasonal records, weights, provenance, and `version_variants` stay
intact in normalized downloads and comparisons. Typed public routes
(`trainer-NNNN`, `header-NNN`, and `map-NNN`) are distinct from raw numeric IDs
and native names such as `map_191`.

`version_variants` describe different values stored in sibling ROM datasets.
Battle-family conditions describe runtime selection among trainer records. The
two axes are not interchangeable: sibling merging requires matching family
capabilities and rules, while exact trainer records remain the units compared and
indexed by Pokémon appearances, items, locations, and other backlinks.
