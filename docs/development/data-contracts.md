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

Every dataset envelope contains a dataset name, game identity, schema version,
record count, source metadata, records, and a sorted `features` list. A feature
means the exact engine/profile combination supports that mechanic. Record-level
emptiness is separate: an empty list means the mechanic exists but this record
has no entries.

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
labeled as PokéDB-derived; exact mechanics and comparisons remain ROM-derived.

The normalized `types` archive records the selected chart, attacking and defending
type identities, exact multipliers, game identity, source kind, and provenance.
Profiles explicitly select an engine chart or provide validated overrides, so the
dataset never infers mechanics merely from displayed type names.

Trainer data keeps prize money distinct from AI battle items and victory items.
Calculated base prize money is serialized only when all generation-specific inputs
are exact, and the stored multiplier retains its ROM provenance. Unsupported or
unresolved payouts are absent rather than represented by an estimate.
